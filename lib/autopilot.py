"""Autopilot: decide when to record, without a human touching anything.

Microphone activity is the automatic trigger. Calendar and window state add
context, and a reconciler catches misses.

  1. audio activity       supported meeting app actively using the microphone
  2. calendar poll        context only; never starts recording by itself
  3. window class         confirmation only, never a trigger on its own
  4. manual               always available

Silence is worse than a miss, so unplanned calls prompt by default.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path


def which(name):
    return shutil.which(name)


def run(cmd, timeout=15):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, "", ""


# ---------------------------------------------------------------------------
# trigger 2 — audio activity
# ---------------------------------------------------------------------------

def active_capture_clients() -> list[str]:
    """Applications currently holding a microphone capture stream.

    A running capture stream is the strongest available signal that a call is
    in progress, and it is independent of any calendar.
    """
    names: list[str] = []
    code, out, _ = run(["pactl", "-f", "json", "list", "source-outputs"])
    if code == 0 and out.strip():
        try:
            for entry in json.loads(out):
                props = entry.get("properties", {}) or {}
                name = (props.get("application.process.binary")
                        or props.get("application.name") or "").lower()
                if not name:
                    continue
                if entry.get("corked") is True:
                    continue        # stream open but not actually capturing
                names.append(name)
            return names
        except ValueError:
            pass

    # Fallback for older pactl without JSON output.
    code, out, _ = run(["pactl", "list", "source-outputs"])
    if code == 0:
        for match in re.finditer(r'application\.process\.binary = "([^"]+)"', out):
            names.append(match.group(1).lower())
    return names


def meeting_app_active(cfg: dict) -> tuple[bool, str | None]:
    detection = cfg["detection"]
    if not detection.get("audioActivity", True):
        return False, None
    known = [a.lower() for a in detection.get("knownMeetingApps", [])]
    denied = [a.lower() for a in detection.get("appDenylist", [])]
    for client in active_capture_clients():
        if any(d and d in client for d in denied):
            continue
        if any(k and k in client for k in known):
            return True, client
    return False, None


def event_matches_capture_app(event: dict, app: str | None) -> bool:
    """Use calendar metadata only when its platform agrees with the mic owner.

    Browser microphone activity can be any tab. Restrict browser correlation to
    Google Meet so an overlapping Zoom/Teams calendar event cannot mislabel an
    unrelated Meet call.
    """
    client = (app or "").lower()
    host = (urllib.parse.urlparse(event.get("joinUrl") or "").hostname or "").lower()
    if any(name in client for name in ("chrome", "chromium", "brave", "firefox", "edge")):
        return host == "meet.google.com"
    if "zoom" in client:
        return host == "zoom.us" or host.endswith(".zoom.us")
    if "teams" in client:
        return host == "teams.microsoft.com"
    return False


# ---------------------------------------------------------------------------
# trigger 3 — window class, confirmation only
# ---------------------------------------------------------------------------

def active_window_class() -> str | None:
    if not which("hyprctl"):
        return None
    code, out, _ = run(["hyprctl", "-j", "activewindow"])
    if code != 0 or not out.strip():
        return None
    try:
        return (json.loads(out).get("class") or "").lower() or None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# trigger 1 — calendar
# ---------------------------------------------------------------------------

def due_event(events: list[dict], cfg, qualifies, now: datetime) -> dict | None:
    """The event that can label an active call; never a recording trigger alone."""
    lookahead = timedelta(seconds=cfg["capture"]["lookaheadSec"])
    for event in events:
        ok, _ = qualifies(event, cfg)
        if not ok:
            continue
        try:
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event["end"])
        except (KeyError, ValueError):
            continue
        # Arm early, and stay armed through the scheduled end so a meeting
        # that starts late is still captured.
        if start - lookahead <= now <= end:
            return event
    return None


def reminder_events(events: list[dict], cfg, qualifies, now: datetime) -> list[dict]:
    """Qualifying meetings beginning inside the configured reminder window."""
    minutes = int(cfg.get("notify", {}).get("joinReminderMin", 5))
    window = timedelta(minutes=max(1, minutes))
    output = []
    for event in events:
        ok, _ = qualifies(event, cfg)
        if not ok:
            continue
        try:
            start = datetime.fromisoformat(event["start"])
        except (KeyError, ValueError):
            continue
        if now <= start <= now + window:
            output.append(event)
    return output


# ---------------------------------------------------------------------------
# silence-based auto-stop
# ---------------------------------------------------------------------------

def tail_is_silent(path: Path, seconds: int, floor_db: float = -60.0) -> bool:
    """True when the last `seconds` of a growing capture contain no speech."""
    if not which("ffmpeg") or not path.exists():
        return False
    duration = probe_duration(path)
    if duration is None or duration < seconds + 5:
        return False
    start = max(0.0, duration - seconds)
    code, _, err = run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-ss", str(start), "-t", str(seconds),
         "-i", str(path), "-af", "volumedetect", "-f", "null", "/dev/null"], timeout=120)
    if code != 0:
        return False
    for line in err.splitlines():
        if "max_volume:" in line:
            try:
                return float(line.split("max_volume:")[1].strip().split()[0]) <= floor_db
            except (IndexError, ValueError):
                return False
    return False


def probe_duration(path: Path) -> float | None:
    if not which("ffprobe"):
        return None
    code, out, _ = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], timeout=60)
    try:
        return float(out.strip()) if code == 0 else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# multi-host claim lock — the XPS and the Studio must not both record
# ---------------------------------------------------------------------------

def claim(state_dir: Path, event_id: str, host: str, ttl_sec: int = 7200) -> bool:
    """Best-effort exclusive claim on an event, via atomic create."""
    claims = state_dir / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", event_id or "adhoc")[:120]
    path = claims / f"{safe}.json"
    payload = json.dumps({"host": host, "at": datetime.now().astimezone().isoformat()})
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(payload)
        return True
    except FileExistsError:
        existing = {}
        try:
            existing = json.loads(path.read_text())
        except (OSError, ValueError):
            pass
        if existing.get("host") == host:
            return True                     # our own claim, e.g. after a restart
        try:
            age = datetime.now().astimezone() - datetime.fromisoformat(existing["at"])
            if age.total_seconds() > ttl_sec:
                path.write_text(payload)    # stale claim from a dead host
                return True
        except (KeyError, ValueError):
            pass
        return False
    except OSError:
        return True                          # never block recording on lock trouble


def release(state_dir: Path, event_id: str) -> None:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", event_id or "adhoc")[:120]
    (state_dir / "claims" / f"{safe}.json").unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# wake-from-sleep catch-up
# ---------------------------------------------------------------------------

def slept_since(last_tick: datetime | None, now: datetime, interval: int) -> bool:
    """A gap far larger than the poll interval means the host was asleep."""
    if last_tick is None:
        return False
    return (now - last_tick).total_seconds() > max(interval * 4, 300)
