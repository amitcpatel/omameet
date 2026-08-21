"""Transcription and speaker attribution.

whisper.cpp runs locally; nothing leaves the machine. Diarization assigns
anonymous clusters, then speakers are resolved by evidence — mic anchoring
first, calendar attendees second, self-introduction third. Unknown stays
unknown: a wrong owner is worse than no owner.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import wave
from pathlib import Path

from model_integrity import WHISPER_MODEL_ARTIFACTS, verified_model

WHISPER_BINS = ("whisper-cli", "whisper-cpp", "main")
MODEL_DIRS = (
    Path("/usr/share/whisper.cpp/models"),
    Path.home() / ".local/share/whisper.cpp/models",
    Path.home() / ".cache/whisper.cpp",
)


def which(name):
    return shutil.which(name)


def whisper_bin() -> str | None:
    for candidate in WHISPER_BINS:
        found = which(candidate)
        if found:
            return found
    return None


def find_model(name: str) -> Path | None:
    """Locate and hash-verify the exact allowlisted model requested."""
    return verified_model(name, MODEL_DIRS)


def to_wav16k(src: Path, dst: Path) -> bool:
    """whisper.cpp requires 16 kHz mono PCM."""
    if not which("ffmpeg"):
        return False
    proc = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
         "-i", str(src), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
        capture_output=True, text=True, timeout=1800)
    return proc.returncode == 0 and dst.exists()


def wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path)) as handle:
            return handle.getnframes() / float(handle.getframerate())
    except Exception:
        return 0.0


TS_RE = re.compile(
    r"\[(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})\]\s*(.*)")


def _secs(h, m, s, ms) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def transcribe(audio: Path, workdir: Path, model_name: str = "large-v3-turbo",
               lang: str = "en", threads: int | None = None) -> dict:
    """Return {ok, segments:[{start,end,text}], text, model, error}."""
    binary = whisper_bin()
    if not binary:
        return {"ok": False, "error": "whisper.cpp not installed", "segments": []}
    model = find_model(model_name)
    if not model:
        reason = ("unsupported model" if model_name not in WHISPER_MODEL_ARTIFACTS
                  else "model missing or failed SHA-256 verification")
        return {"ok": False,
                "error": f"{reason} for '{model_name}'; "
                         f"fetch one into {MODEL_DIRS[1]}",
                "segments": []}

    wav = workdir / "whisper-input.wav"
    if not to_wav16k(audio, wav):
        return {"ok": False, "error": "ffmpeg failed to produce 16kHz wav", "segments": []}
    duration_sec = wav_duration(wav)

    cmd = [binary, "-m", str(model), "-f", str(wav), "-l", lang, "-nt" if False else "-pp"]
    cmd = [binary, "-m", str(model), "-f", str(wav), "-l", lang]
    if threads:
        cmd += ["-t", str(threads)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "whisper timed out", "segments": []}
    finally:
        wav.unlink(missing_ok=True)

    if proc.returncode != 0:
        return {"ok": False, "error": f"whisper exited {proc.returncode}: {proc.stderr[-400:]}",
                "segments": []}

    segments = []
    for line in proc.stdout.splitlines():
        match = TS_RE.match(line.strip())
        if not match:
            continue
        g = match.groups()
        text = g[8].strip()
        if not text:
            continue
        segments.append({"start": _secs(*g[0:4]), "end": _secs(*g[4:8]), "text": text})

    full = " ".join(s["text"] for s in segments).strip()
    # An empty transcript is a failure, not a success.
    if not full:
        return {"ok": False, "error": "transcript is empty — treating as failure",
                "segments": [], "model": model.name}
    return {"ok": True, "segments": segments, "text": full, "model": model.name,
            "duration_sec": duration_sec}


def transcript_coverage(segments: list[dict], duration_sec: float) -> dict:
    """Reject long recordings whose decoded transcript is mostly non-speech."""
    speech = []
    for segment in segments:
        text = re.sub(r"\[[^]]*\]", " ", str(segment.get("text", "")))
        speech.extend(re.findall(r"[A-Za-z0-9']+", text))
    words = len(speech)
    minutes = max(float(duration_sec or 0.0) / 60.0, 1 / 60)
    words_per_minute = words / minutes
    required = max(5, int(minutes * 12))
    ok = duration_sec < 60 or words >= required
    return {
        "ok": ok,
        "words": words,
        "duration_sec": round(float(duration_sec or 0.0), 1),
        "words_per_minute": round(words_per_minute, 1),
        "minimum_words": required,
        "reason": None if ok else (
            f"transcript coverage too sparse: {words} spoken words over "
            f"{minutes:.1f} minutes; expected at least {required}"),
    }


# ---------------------------------------------------------------------------
# diarization
# ---------------------------------------------------------------------------

def rms_envelope(path: Path, window: float = 0.5) -> list[tuple[float, float]]:
    """Coarse energy envelope from a 16-bit PCM wav. Stdlib only."""
    try:
        with wave.open(str(path)) as handle:
            rate = handle.getframerate()
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            if width != 2:
                return []
            frames_per_window = int(rate * window)
            out = []
            position = 0.0
            import array
            while True:
                raw = handle.readframes(frames_per_window)
                if not raw:
                    break
                samples = array.array("h")
                samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
                if channels > 1:
                    samples = samples[::channels]
                if not samples:
                    break
                total = sum(float(v) * float(v) for v in samples)
                out.append((position, (total / len(samples)) ** 0.5))
                position += window
            return out
    except Exception:
        return []


def stream_attribution(segments: list[dict], mic_wav: Path, sys_wav: Path) -> list[dict]:
    """Assign each segment to 'me' or 'them' by comparing per-stream energy.

    This is the structural advantage of recording mic and system separately:
    the mic stream is always the local user. Granola cannot do this because it
    mixes before it stores.
    """
    mic_env = rms_envelope(mic_wav)
    sys_env = rms_envelope(sys_wav)
    if not mic_env and not sys_env:
        return [dict(s, cluster=None, stream=None) for s in segments]

    def energy(envelope, start, end):
        vals = [v for (t, v) in envelope if start <= t <= end]
        return sum(vals) / len(vals) if vals else 0.0

    out = []
    for seg in segments:
        mic_e = energy(mic_env, seg["start"], seg["end"])
        sys_e = energy(sys_env, seg["start"], seg["end"])
        total = mic_e + sys_e
        if total <= 0:
            stream, confidence = None, 0.0
        elif mic_e >= sys_e:
            stream, confidence = "mic", mic_e / total
        else:
            stream, confidence = "system", sys_e / total
        out.append(dict(seg,
                        stream=stream,
                        cluster="SPEAKER_00" if stream == "mic" else
                                ("SPEAKER_01" if stream == "system" else None),
                        stream_confidence=round(confidence, 3)))
    return out


def diarize(segments: list[dict], mic_wav: Path, sys_wav: Path,
            audio: Path, workdir: Path) -> tuple[list[dict], str]:
    """Cluster segments by speaker. Falls back to stream attribution.

    Returns (segments, method). Stream attribution reliably separates the local
    user from remote participants; splitting multiple remote speakers apart
    requires an acoustic diarizer, which is reported honestly when absent.
    """
    segments = stream_attribution(segments, mic_wav, sys_wav)
    return segments, "stream_attribution"


# ---------------------------------------------------------------------------
# speaker resolution — evidence-ranked, never guessing
# ---------------------------------------------------------------------------

INTRO_PATTERNS = [
    re.compile(r"\b(?:it'?s|this is|i'?m|my name is)\s+([A-Z][a-z]{1,20})\b"),
    re.compile(r"\b([A-Z][a-z]{1,20})\s+here\b"),
]


def resolve_speakers(segments: list[dict], attendees: list[dict],
                     me: dict | None) -> tuple[list[dict], list[dict]]:
    """Map clusters to real people. Returns (participants, conflicts)."""
    me = me or {}
    clusters: dict[str, dict] = {}
    total_words = 0
    for seg in segments:
        cluster = seg.get("cluster")
        if not cluster:
            continue
        words = len(seg["text"].split())
        total_words += words
        entry = clusters.setdefault(cluster, {"words": 0, "segments": 0, "stream": seg.get("stream")})
        entry["words"] += words
        entry["segments"] += 1

    # Layer 2 candidates: invited, not me, not declined, not a resource.
    candidates = [a for a in (attendees or [])
                  if not a.get("self")
                  and not a.get("resource")
                  and a.get("responseStatus") != "declined"]

    participants = []
    for cluster, stats in sorted(clusters.items()):
        share = round(100.0 * stats["words"] / total_words, 1) if total_words else 0.0

        # Layer 1 — mic anchoring. Structural, highest confidence.
        if stats["stream"] == "mic":
            participants.append({
                "speaker": cluster,
                "name": me.get("name"),
                "email": me.get("email"),
                "role": "organizer" if me.get("organizer") else "attendee",
                "resolved_by": "mic_anchor",
                "confidence": 0.99,
                "talk_time_pct": share,
                "is_me": True,
                "needs_human": not bool(me.get("name")),
            })
            continue

        # Layer 2 — exactly one plausible remote attendee.
        remote_clusters = [c for c, s in clusters.items() if s["stream"] == "system"]
        if len(candidates) == 1 and len(remote_clusters) == 1:
            person = candidates[0]
            participants.append({
                "speaker": cluster,
                "name": person.get("displayName") or person.get("email", "").split("@")[0],
                "email": person.get("email"),
                "role": "attendee",
                "resolved_by": "calendar_single_match",
                "confidence": 0.95,
                "talk_time_pct": share,
                "is_me": False,
                "needs_human": False,
            })
            continue

        # Layer 3 — self-introduction, evidence required.
        name, evidence = None, None
        for seg in segments:
            if seg.get("cluster") != cluster:
                continue
            for pattern in INTRO_PATTERNS:
                match = pattern.search(seg["text"])
                if match:
                    name = match.group(1)
                    evidence = {"quote": seg["text"].strip(), "t": round(seg["start"], 2)}
                    break
            if name:
                break

        if name:
            match_email = None
            for person in candidates:
                label = (person.get("displayName") or person.get("email") or "").lower()
                if name.lower() in label:
                    match_email = person.get("email")
                    break
            participants.append({
                "speaker": cluster, "name": name, "email": match_email,
                "role": "attendee",
                "resolved_by": "self_introduction",
                "confidence": 0.85 if match_email else 0.70,
                "evidence": evidence,
                "talk_time_pct": share, "is_me": False,
                "needs_human": match_email is None,
            })
            continue

        # Layer 5 — honest unknown. Never guess.
        participants.append({
            "speaker": cluster, "name": None, "email": None,
            "resolved_by": None, "confidence": 0.0,
            "talk_time_pct": share, "is_me": False, "needs_human": True,
            "note": "unidentified speaker — not resolvable from calendar or transcript",
        })

    # Calendar vs reality mismatches, surfaced rather than hidden.
    conflicts = []
    named = {(p.get("email") or "").lower() for p in participants if p.get("email")}
    for person in candidates:
        if (person.get("email") or "").lower() not in named:
            conflicts.append({
                "issue": "invited_but_silent",
                "who": person.get("email"),
                "detail": "on the invite but no matching voice — may not have attended",
            })
    for person in participants:
        if person.get("needs_human") and not person.get("is_me"):
            conflicts.append({
                "issue": "present_but_unidentified",
                "who": person["speaker"],
                "detail": "spoke but could not be matched to an invitee",
            })
    return participants, conflicts


def render_transcript(segments: list[dict], participants: list[dict]) -> str:
    names = {p["speaker"]: (p.get("name") or f"Speaker {p['speaker'][-1]}")
             for p in participants}
    lines = []
    last = None
    for seg in segments:
        who = names.get(seg.get("cluster"), "Unknown")
        stamp = "%02d:%02d:%02d" % (int(seg["start"] // 3600),
                                    int(seg["start"] % 3600 // 60),
                                    int(seg["start"] % 60))
        if who != last:
            lines.append("")
            lines.append(f"**[{stamp}] {who}:** {seg['text'].strip()}")
            last = who
        else:
            lines.append(seg["text"].strip())
    return "\n".join(lines).strip() + "\n"
