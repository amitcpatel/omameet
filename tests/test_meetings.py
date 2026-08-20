#!/usr/bin/env python3
"""Tests for OmaScribe. Standard library only (unittest)."""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
import urllib.parse
import urllib.request
from unittest.mock import patch
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELPER = HERE.parent / "bin" / "omascribe-meetings"
QML_DIR = HERE.parent


def load_helper():
    spec = importlib.util.spec_from_loader(
        "omarchy_meetings",
        importlib.machinery.SourceFileLoader("omarchy_meetings", str(HELPER)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ThemeComplianceTest(unittest.TestCase):
    """The plugin must follow the active Omarchy theme. No hardcoded values."""

    HEX = __import__("re").compile(r'"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})"')
    NAMED = __import__("re").compile(r'\bcolor:\s*"(?!transparent)[a-z]+"')

    @staticmethod
    def qml_files():
        return [p for p in QML_DIR.glob("*.qml") if not p.name.startswith("._")]

    def test_no_hardcoded_hex_colours(self):
        offenders = []
        for qml in self.qml_files():
            for n, line in enumerate(qml.read_text().splitlines(), 1):
                if self.HEX.search(line):
                    offenders.append(f"{qml.name}:{n}: {line.strip()}")
        self.assertEqual(offenders, [], "hardcoded hex colours break theming:\n" + "\n".join(offenders))

    def test_no_named_colours(self):
        offenders = []
        for qml in self.qml_files():
            for n, line in enumerate(qml.read_text().splitlines(), 1):
                if self.NAMED.search(line):
                    offenders.append(f"{qml.name}:{n}: {line.strip()}")
        self.assertEqual(offenders, [], "named colours break theming:\n" + "\n".join(offenders))

    def test_uses_theme_singletons(self):
        panel = (QML_DIR / "Panel.qml").read_text()
        for token in ("Color.popups", "Style.font", "Style.spacing", "Style.cornerRadius"):
            self.assertIn(token, panel, f"Panel.qml should use {token}")

    def test_recording_indicator_uses_urgent(self):
        """The ● indicator must use the theme's alert colour, not literal red."""
        self.assertIn("Color.urgent", (QML_DIR / "Panel.qml").read_text())

    def test_no_shadowing_of_builtin_qml_properties(self):
        """QML Item/PanelWindow already define `state`, `data`, `children`, etc.

        Regression: declaring `readonly property string state` shadowed the
        built-in, broke the binding chain, and the widget silently failed to
        present — no error in any log.
        """
        reserved = ("state", "data", "children", "resources", "parent",
                    "visible", "opacity", "enabled")
        offenders = []
        for qml in self.qml_files():
            for n, line in enumerate(qml.read_text().splitlines(), 1):
                m = re.match(r"\s*(?:readonly\s+)?property\s+\w+\s+(\w+)\s*:", line)
                if m and m.group(1) in reserved:
                    offenders.append(f"{qml.name}:{n}: shadows '{m.group(1)}'")
        self.assertEqual(offenders, [],
                         "do not shadow built-in QML properties:\n" + "\n".join(offenders))

    def test_bar_widget_glyph_is_never_empty(self):
        """An empty glyph renders as an invisible gap with NO error logged.

        Regression: raw UTF-8 Nerd Font glyphs were stripped in transit, leaving
        `text: root.recording ? "" : ""`. The widget loaded fine and drew nothing,
        so the bar simply had a hole in it and every log was clean.
        """
        source = (QML_DIR / "BarWidget.qml").read_text()
        line = [l for l in source.splitlines()
                if "text:" in l and "root.recording" in l]
        self.assertTrue(line, "BarWidget must set text from the recording state")
        self.assertNotIn('""', line[0],
                         "empty glyph string renders an invisible widget")
        self.assertIn("\\u", line[0],
                      "use \\uXXXX escapes, not raw UTF-8 glyphs (strippable in transit)")

    def test_bar_widget_signals_recording_via_active(self):
        """BarIconButton colours itself from `active`; assigning `color` is fatal.

        Regression: `color:` on BarIconButton produced
        'Cannot assign to non-existent property "color"' and the widget silently
        never rendered — the bar looked fine, the icon was simply absent.
        """
        source = (QML_DIR / "BarWidget.qml").read_text()
        self.assertIn("active: root.recording", source)
        self.assertNotIn("color:", source,
                         "BarIconButton has no color property; use active/activeColor")

    def test_bar_widget_does_not_write_button_opacity(self):
        """WidgetButton owns opacity; writing it destroys its visibility binding."""
        source = (QML_DIR / "BarWidget.qml").read_text()
        self.assertNotRegex(
            source,
            r'(?:target\s*:\s*button[\s\S]{0,120}property\s*:\s*"opacity"|button\.opacity\s*=)',
            "do not animate or assign BarIconButton.opacity; WidgetButton owns that binding",
        )

    def test_meetings_popup_uses_shell_panel_contract(self):
        """A raw PanelWindow can become 'opened' while painting no popup."""
        source = (QML_DIR / "Panel.qml").read_text()
        self.assertRegex(source, r"(?m)^Panel\s*\{")
        self.assertNotRegex(source, r"(?m)^PanelWindow\s*\{")
        self.assertIn("root.controller.show()", source)
        self.assertIn("root.controller.hide()", source)

    def test_calendar_join_starts_capture_before_opening_url(self):
        source = (QML_DIR / "Panel.qml").read_text()
        self.assertIn('function joinMeeting(event)', source)
        self.assertIn('meetingsHelper, "join"', source)
        self.assertIn('onClicked: root.joinMeeting(modelData)', source)

    def test_panel_exposes_ad_hoc_recording_control(self):
        source = (QML_DIR / "Panel.qml").read_text()
        self.assertIn('command: [root.meetingsHelper, "record", "start"]', source)
        self.assertIn('command: [root.meetingsHelper, "record", "stop"]', source)
        self.assertIn('function toggleAdHocRecording()', source)
        self.assertIn('onClicked: root.toggleAdHocRecording()', source)
        icon_line = next(line for line in source.splitlines()
                         if 'text: root.recording ?' in line and '\\uf04d' in line)
        self.assertIn('"\\uf111  Record"', icon_line)
        self.assertIn('"\\uf04d  Stop"', icon_line)

    def test_settings_use_omarchy_default_ai(self):
        source = (QML_DIR / "Panel.qml").read_text()
        self.assertIn('text: "\\uf013"', source)
        self.assertIn('command: [root.meetingsHelper, "ai", "status", "--json"]', source)
        self.assertIn('command: [root.meetingsHelper, "ai", "enable", "--json"]', source)
        self.assertIn('command: [root.meetingsHelper, "ai", "disable", "--json"]', source)
        self.assertIn("Transcript text is sent to that cloud service", source)
        self.assertIn("Enable to consent", source)
        self.assertIn("root.aiDetail", source)
        self.assertNotIn("iCalendar subscription", source)
        self.assertNotIn("Right-click for settings", source)
        self.assertIn('return "No events"', source)

    def test_calendar_controlled_text_is_always_plain_text(self):
        """Calendar HTML must never be interpreted inside omarchy-shell."""
        panel = (QML_DIR / "Panel.qml").read_text()
        external_bindings = (
            "text: modelData.accountLabel",
            'text: modelData.title + "  ·  " + modelData.calendarLabel',
            "text: modelData.title",
            'text: root.timeRange(modelData) + "  ·  " + modelData.calendarLabel',
            'text: root.timeRange(modelData) + "  " + modelData.title',
            "text: root.errorText",
        )
        for binding in external_bindings:
            line = next((line for line in panel.splitlines() if binding in line), "")
            self.assertIn("textFormat: Text.PlainText", line,
                          f"untrusted QML binding lacks PlainText: {binding}")

        toggle = (QML_DIR / "PlainTextToggle.qml").read_text()
        self.assertGreaterEqual(toggle.count("textFormat: Text.PlainText"), 2)
        self.assertIn("PlainTextToggle {", panel)

    def test_calendar_titles_are_sanitized_before_shared_tooltip(self):
        panel = (QML_DIR / "Panel.qml").read_text()
        self.assertIn("function safeTooltipText(value)", panel)
        self.assertRegex(panel, r"readonly property string tooltip:\s*safeTooltipText\(")


class UrlInstallTest(unittest.TestCase):
    """`omarchy plugin add <git-url>` runs NO install hooks.

    Anything that assumes install.sh ran — a PATH symlink, a chmod — is broken
    for every user who installs the documented way.
    """

    def qml_files(self):
        return [p for p in QML_DIR.glob("*.qml") if not p.name.startswith("._")]

    def test_qml_never_calls_helper_by_bare_name(self):
        offenders = []
        for qml in self.qml_files():
            for n, line in enumerate(qml.read_text().splitlines(), 1):
                if '"omascribe-meetings"' in line and "resolvedUrl" not in line:
                    offenders.append(f"{qml.name}:{n}: {line.strip()}")
        self.assertEqual(offenders, [],
                         "QML must resolve the helper by absolute path, not PATH:\n"
                         + "\n".join(offenders))

    def test_qml_resolves_helper_from_plugin_dir(self):
        users = [q for q in self.qml_files()
                 if "Process" in q.read_text() and "command:" in q.read_text()]
        self.assertTrue(users, "expected at least one QML file to run the helper")
        for qml in users:
            self.assertIn('Qt.resolvedUrl("bin/omascribe-', qml.read_text(),
                          f"{qml.name} must resolve the helper from the plugin dir")

    def test_helper_is_executable(self):
        """git preserves the exec bit; without it the widget cannot run."""
        self.assertTrue(os.access(HELPER, os.X_OK),
                        "bin/omascribe-meetings must be committed executable (git mode 100755)")

    def test_helper_has_shebang(self):
        self.assertTrue(HELPER.read_text().startswith("#!/usr/bin/env python3"))


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((QML_DIR / "manifest.json").read_text())

    def test_schema_version(self):
        self.assertEqual(self.manifest["schemaVersion"], 1)

    def test_id_not_reserved(self):
        self.assertFalse(self.manifest["id"].startswith("omarchy."),
                         "the omarchy. namespace is reserved")

    def test_entry_point_per_kind(self):
        kinds = self.manifest["kinds"]
        entries = self.manifest["entryPoints"]
        mapping = {"service": "service", "bar-widget": "barWidget"}
        for kind in kinds:
            key = mapping[kind]
            self.assertIn(key, entries, f"missing entry point for {kind}")
            self.assertTrue((QML_DIR / entries[key]).exists(),
                            f"entry point file missing: {entries[key]}")

    def test_no_symlinks_in_tree(self):
        """omarchy plugin validate rejects symlinks anywhere inside the folder."""
        offenders = [str(p) for p in QML_DIR.rglob("*") if p.is_symlink()]
        self.assertEqual(offenders, [], f"symlinks break validate: {offenders}")


class HelperTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_helper()

    def test_stdlib_only(self):
        """No third-party imports — matches acp.calendar discipline."""
        source = HELPER.read_text()
        banned = ("import requests", "import yaml", "import numpy", "from google", "import httpx")
        for b in banned:
            self.assertNotIn(b, source, f"third-party dependency found: {b}")

    def test_retain_audio_defaults_false(self):
        self.assertFalse(self.mod.DEFAULT_CONFIG["retainAudio"])

    def test_auto_record_unplanned_defaults_false(self):
        """Silently recording is worse than missing a meeting."""
        self.assertFalse(self.mod.DEFAULT_CONFIG["detection"]["autoRecordUnplanned"])

    def test_meeting_app_exit_has_a_grace_period(self):
        self.assertEqual(self.mod.DEFAULT_CONFIG["capture"]["appExitGraceSec"], 90)
        source = HELPER.read_text()
        self.assertIn('sess["capture_client_seen_at"]', source)
        self.assertIn('reason = "app_exit"', source)

    def test_calendar_time_never_starts_recording_by_itself(self):
        source = HELPER.read_text()
        tick = source.split("def cmd_tick", 1)[1].split("\n\ndef ", 1)[0]
        self.assertNotIn("start:calendar", tick)
        self.assertLess(tick.index("meeting_app_active(cfg)"),
                        tick.index('start_recording(cfg, event.get("title")'))

    def test_calendar_context_must_match_microphone_app(self):
        import autopilot
        meet = {"joinUrl": "https://meet.google.com/abc-defg-hij"}
        zoom = {"joinUrl": "https://example.zoom.us/j/123"}
        teams = {"joinUrl": "https://teams.microsoft.com/l/meetup-join/123"}
        self.assertTrue(autopilot.event_matches_capture_app(meet, "chrome"))
        self.assertFalse(autopilot.event_matches_capture_app(zoom, "chrome"))
        self.assertTrue(autopilot.event_matches_capture_app(zoom, "zoom"))
        self.assertTrue(autopilot.event_matches_capture_app(teams, "teams-for-linux"))
        self.assertFalse(autopilot.event_matches_capture_app(
            {"joinUrl": "https://evilzoom.us/call"}, "zoom"))

    def test_join_reminder_uses_persistent_omarchy_click_action(self):
        source = HELPER.read_text()
        self.assertIn('which("omarchy-notification-send")', source)
        self.assertIn('"--exec", action', source)
        self.assertIn('"join-reminder", help=argparse.SUPPRESS', source)

    def test_capture_backend_is_ffmpeg_not_pw_record(self):
        """pw-record writes correctly-sized files full of silence."""
        self.assertEqual(self.mod.DEFAULT_CONFIG["audio"]["backend"], "ffmpeg-pulse")
        self.assertNotIn("pw-record", HELPER.read_text().split("Design rules")[-1][:200])

    def test_transcription_defaults_local(self):
        self.assertEqual(self.mod.DEFAULT_CONFIG["transcription"]["backend"], "local")

    def test_ai_notes_require_omascribe_specific_consent(self):
        self.assertEqual(self.mod.DEFAULT_CONFIG["llm"]["backend"], "disabled")

    def test_processing_lock_is_exclusive(self):
        """Two processors must never race and overwrite audio audit evidence."""
        with tempfile.TemporaryDirectory() as tmp:
            first = self.mod.acquire_process_lock(Path(tmp))
            try:
                with self.assertRaises(RuntimeError):
                    self.mod.acquire_process_lock(Path(tmp))
            finally:
                first.close()

    def test_deep_merge_preserves_defaults(self):
        merged = self.mod.deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"b": 9}})
        self.assertEqual(merged, {"a": {"b": 9, "c": 2}})

    def test_qualifies_skips_all_day(self):
        cfg = self.mod.DEFAULT_CONFIG
        ok, reason = self.mod.qualifies({"allDay": True, "title": "x"}, cfg)
        self.assertFalse(ok)
        self.assertEqual(reason, "all-day")

    def test_qualifies_skips_blocklisted_title(self):
        cfg = self.mod.DEFAULT_CONFIG
        ok, reason = self.mod.qualifies({"title": "Focus time", "joinUrl": "https://x"}, cfg)
        self.assertFalse(ok)
        self.assertIn("Focus", reason)

    def test_qualifies_requires_link(self):
        cfg = self.mod.DEFAULT_CONFIG
        ok, reason = self.mod.qualifies({"title": "Sync", "joinUrl": ""}, cfg)
        self.assertFalse(ok)
        self.assertEqual(reason, "no video link")

    def test_qualifies_skips_short_meetings(self):
        cfg = self.mod.DEFAULT_CONFIG
        ev = {"title": "Sync", "joinUrl": "https://meet.google.com/x",
              "start": "2026-08-21T14:00:00-04:00", "end": "2026-08-21T14:05:00-04:00"}
        ok, reason = self.mod.qualifies(ev, cfg)
        self.assertFalse(ok)
        self.assertIn("shorter", reason)

    def test_qualifies_accepts_real_meeting(self):
        cfg = self.mod.DEFAULT_CONFIG
        ev = {"title": "Ayon Infra Review", "joinUrl": "https://meet.google.com/x",
              "start": "2026-08-21T14:00:00-04:00", "end": "2026-08-21T15:00:00-04:00"}
        ok, reason = self.mod.qualifies(ev, cfg)
        self.assertTrue(ok, reason)

    def test_silence_floor_is_strict(self):
        self.assertLessEqual(self.mod.SILENCE_FLOOR_DB, -80.0)


class CliTest(unittest.TestCase):
    def run_cli(self, *args, env=None):
        e = dict(os.environ)
        e.update(env or {})
        return subprocess.run([sys.executable, str(HELPER), *args],
                              capture_output=True, text=True, env=e, timeout=60)

    def test_version_json(self):
        r = self.run_cli("version", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["name"], "omascribe")
        self.assertEqual(json.loads(r.stdout)["version"], "0.5.1")

    def test_fetch_model_rejects_path_traversal(self):
        r = self.run_cli("fetch-model", "../evil", "--json")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("invalid model name", r.stderr)

    def test_fetch_model_uses_pinned_revision_and_verifies_sha256(self):
        mod = load_helper()
        payload = b"verified whisper model"
        digest = __import__("hashlib").sha256(payload).hexdigest()
        urls = []
        with tempfile.TemporaryDirectory() as directory:
            def download(url, destination):
                urls.append(url)
                Path(destination).write_bytes(payload)

            with patch.object(mod.Path, "home", return_value=Path(directory)), \
                    patch.object(mod, "WHISPER_MODEL_ARTIFACTS", {"test": digest}), \
                    patch.object(urllib.request, "urlretrieve", side_effect=download):
                mod.cmd_fetch_model(types.SimpleNamespace(model="test", json=True))
            output = Path(directory) / ".local/share/whisper.cpp/models/ggml-test.bin"
            self.assertEqual(output.read_bytes(), payload)
        self.assertEqual(len(urls), 1)
        self.assertIn(f"/resolve/{mod.WHISPER_MODEL_REVISION}/", urls[0])
        self.assertNotIn("/resolve/main/", urls[0])

    def test_fetch_model_rejects_and_removes_tampered_download(self):
        mod = load_helper()
        expected = __import__("hashlib").sha256(b"expected").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            def download(_url, destination):
                Path(destination).write_bytes(b"tampered")

            with patch.object(mod.Path, "home", return_value=Path(directory)), \
                    patch.object(mod, "WHISPER_MODEL_ARTIFACTS", {"test": expected}), \
                    patch.object(urllib.request, "urlretrieve", side_effect=download), \
                    patch.object(mod, "fail", side_effect=RuntimeError("rejected")):
                with self.assertRaisesRegex(RuntimeError, "rejected"):
                    mod.cmd_fetch_model(types.SimpleNamespace(model="test", json=True))
            model_dir = Path(directory) / ".local/share/whisper.cpp/models"
            self.assertFalse((model_dir / "ggml-test.bin").exists())
            self.assertFalse((model_dir / "ggml-test.part").exists())

    def test_invalid_model_name_does_not_raise_desktop_notification(self):
        source = HELPER.read_text()
        branch = source.split('if not re.fullmatch(r"[A-Za-z0-9._-]+", name):', 1)[1].split("\n", 2)[0:2]
        self.assertIn("notify_user=False", "\n".join(branch))

    def test_status_json_is_parseable(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli("status", "--json", env={"XDG_STATE_HOME": d})
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(r.stdout)
            self.assertIn("recording", data)

    def test_config_shows_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli("config", env={"XDG_CONFIG_HOME": d, "XDG_STATE_HOME": d})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(json.loads(r.stdout)["retainAudio"])
            self.assertEqual(json.loads(r.stdout)["llm"]["backend"], "disabled")

    def test_ai_enable_persists_explicit_consent(self):
        mod = load_helper()
        with tempfile.TemporaryDirectory() as d:
            original_file = mod.CONFIG_FILE
            original_dir = mod.CONFIG_DIR
            original_resolve = mod.resolve_llm
            mod.CONFIG_DIR = Path(d)
            mod.CONFIG_FILE = Path(d) / "config.json"
            mod.resolve_llm = lambda _cfg=None: ("omarchy:grok", "Omarchy default agent: Grok")
            try:
                mod.cmd_ai(types.SimpleNamespace(action="enable", json=True))
                saved = json.loads(mod.CONFIG_FILE.read_text())
            finally:
                mod.CONFIG_FILE = original_file
                mod.CONFIG_DIR = original_dir
                mod.resolve_llm = original_resolve
            self.assertEqual(saved["llm"]["backend"], "omarchy")

    def test_process_uses_local_notes_until_consent_is_enabled(self):
        mod = load_helper()
        seen = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recording = root / "recording"
            recording.mkdir()
            (recording / "mixed.opus").write_bytes(b"audio")
            (recording / "session.json").write_text(json.dumps({
                "title": "Consent test", "started": "2026-08-19T10:00:00-04:00"
            }))
            transcribe = types.SimpleNamespace(
                transcribe=lambda *_args: {"ok": True, "segments": [], "model": "test"},
                diarize=lambda *_args: ([], "test"),
                resolve_speakers=lambda *_args: ([], []),
                render_transcript=lambda *_args: "marker transcript")

            def extract_local(_text, _participants, _meeting, backend):
                seen.append(("extract", backend))
                return {"commitments": [], "decisions": [], "uncertain": [],
                        "llm": {"backend": None}, "passes": {"note": "local"}}

            def notes_local(_meeting, _participants, _extracted, _text, backend):
                seen.append(("notes", backend))
                return "## Notes\n\n_Local processing._\n"

            extract = types.SimpleNamespace(extract=extract_local, write_notes=notes_local)
            vault = types.SimpleNamespace(write_meeting=lambda *_args: {
                "ok": True, "dir": str(root / "vault"), "audio_deleted": True,
                "audio_retained": False, "extraction_ok": True})
            originals = {name: sys.modules.get(name) for name in ("transcribe", "extract", "vault")}
            original_config, original_silent, original_notify = mod.config, mod.is_silent, mod.notify
            original_lock = mod.acquire_process_lock
            sys.modules.update({"transcribe": transcribe, "extract": extract, "vault": vault})
            mod.config = lambda: mod.deep_merge(mod.DEFAULT_CONFIG, {"vault": {"path": str(root / "vault")}})
            mod.is_silent = lambda _path: False
            mod.notify = lambda *_args, **_kwargs: None
            mod.acquire_process_lock = lambda _path: types.SimpleNamespace(close=lambda: None)
            try:
                mod.cmd_process(types.SimpleNamespace(path=str(recording), json=True))
            finally:
                mod.config, mod.is_silent, mod.notify = original_config, original_silent, original_notify
                mod.acquire_process_lock = original_lock
                for name, value in originals.items():
                    if value is None:
                        sys.modules.pop(name, None)
                    else:
                        sys.modules[name] = value
        self.assertEqual(seen, [("extract", "disabled"), ("notes", "disabled")])

    def test_ai_rejects_backend_argument(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli("ai", "enable", "claude",
                             env={"XDG_CONFIG_HOME": d, "XDG_STATE_HOME": d})
            self.assertNotEqual(r.returncode, 0)

    def test_stop_without_session_fails_loud(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli("record", "stop", env={"XDG_STATE_HOME": d})
            self.assertNotEqual(r.returncode, 0, "stopping with no session must fail loud")

    def test_manual_stop_launches_processing(self):
        """The panel's Stop button must complete the vault workflow."""
        source = HELPER.read_text()
        stop_branch = source.split('elif args.action == "stop":', 1)[1].split(
            "\n\ndef ", 1)[0]
        self.assertIn('launch_processing(sess["dir"])', stop_branch,
                      "manual stop captured audio but never wrote Obsidian notes")

    def test_processing_escapes_tick_systemd_cgroup(self):
        source = HELPER.read_text()
        launch = source.split("def launch_processing", 1)[1].split("\n\ndef ", 1)[0]
        self.assertIn('"systemd-run", "--user"', launch)
        tick = source.split("def cmd_tick", 1)[1].split("\n\ndef ", 1)[0]
        self.assertIn('launch_processing(stopped["dir"])', tick)

    def test_pause_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"XDG_STATE_HOME": d}
            self.run_cli("pause", env=env)
            r = self.run_cli("status", "--json", env=env)
            self.assertTrue(json.loads(r.stdout)["paused"])
            self.run_cli("pause", "--off", env=env)
            r = self.run_cli("status", "--json", env=env)
            self.assertFalse(json.loads(r.stdout)["paused"])


class AudioRetentionTest(unittest.TestCase):
    """Deletion is irreversible. It must require the WHOLE chain to succeed."""

    def setUp(self):
        sys.path.insert(0, str(QML_DIR / "lib"))
        import vault
        self.vault = vault

    def _write(self, tmp, extracted, retain=False):
        root = Path(tmp)
        audio = root / "mixed.opus"
        audio.write_bytes(b"x" * 64)
        meeting = {"title": "T", "actual": {"start": "2026-08-16T10:00:00-04:00"},
                   "scheduled": {}}
        return self.vault.write_meeting(
            root / "vault", meeting, [], [], extracted,
            "**[00:00:00] A:** hello there\n", "## Summary\n\nx\n",
            [audio], retain), audio

    def test_audio_kept_when_extraction_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, audio = self._write(tmp, {"error": "llm unavailable"})
            self.assertTrue(audio.exists(), "audio MUST be kept when extraction fails")
            self.assertFalse(res["verified"])
            self.assertTrue(res["audio_retained"])

    def test_audio_deleted_only_on_full_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, audio = self._write(tmp, {"commitments": [], "decisions": []})
            self.assertFalse(audio.exists(), "audio should be deleted after full success")
            self.assertTrue(res["verified"])

    def test_ai_disabled_is_successful_local_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            extracted = {"commitments": [], "decisions": [],
                         "llm": {"backend": None},
                         "passes": {"note": "AI extraction skipped by user preference"}}
            res, audio = self._write(tmp, extracted)
            self.assertTrue(res["verified"])
            self.assertFalse(audio.exists())

    def test_retain_audio_flag_overrides_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, audio = self._write(tmp, {"commitments": []}, retain=True)
            self.assertTrue(audio.exists(), "retainAudio must prevent deletion")

    def test_contract_records_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, _ = self._write(tmp, {"error": "boom"})
            contract = json.loads((Path(res["dir"]) / "meeting.json").read_text())
            self.assertFalse(contract["verification"]["safe_to_delete_audio"])
            self.assertEqual(contract["verification"]["extraction_error"], "boom")

    def test_ad_hoc_meetings_on_same_day_get_distinct_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "mixed.opus"
            audio.write_bytes(b"x" * 64)
            common = {"title": "[ad-hoc] recording", "scheduled": {}}
            results = []
            for stamp in ("10:00:00", "11:00:00"):
                audio.write_bytes(b"x" * 64)
                meeting = {**common,
                           "event_id": "adhoc_2026-08-16-" + stamp.replace(":", ""),
                           "actual": {"start": f"2026-08-16T{stamp}-04:00"}}
                results.append(self.vault.write_meeting(
                    root / "vault", meeting, [], [], {"commitments": []},
                    "transcript\n", "## Summary\n\nTest\n", [audio], True)["dir"])
            self.assertNotEqual(results[0], results[1])


class ExtractionTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(QML_DIR / "lib"))
        import extract
        self.e = extract

    def test_never_invents_due_date(self):
        from datetime import datetime
        value, conf = self.e.resolve_due("", datetime(2026, 8, 16).astimezone())
        self.assertIsNone(value)
        self.assertEqual(conf, 0.0)

    def test_resolves_relative_weekday(self):
        from datetime import datetime
        value, conf = self.e.resolve_due("by Friday", datetime(2026, 8, 17).astimezone())
        self.assertEqual(value, "2026-08-21")
        self.assertGreater(conf, 0.5)

    def test_resolves_tomorrow(self):
        from datetime import datetime
        value, _ = self.e.resolve_due("tomorrow", datetime(2026, 8, 16).astimezone())
        self.assertEqual(value, "2026-08-17")

    def test_confidence_thresholds_are_gated(self):
        self.assertEqual(self.e.AUTO_THRESHOLD, 0.85)
        self.assertEqual(self.e.REVIEW_THRESHOLD, 0.60)

    def test_disabled_ai_never_calls_backend(self):
        original = self.e.call_llm
        self.e.call_llm = lambda *_args, **_kwargs: self.fail("AI backend was called")
        try:
            result = self.e.extract("private transcript", [], {}, "disabled")
        finally:
            self.e.call_llm = original
        self.assertNotIn("error", result)
        self.assertIsNone(result["llm"]["backend"])
        self.assertIn("skipped", result["passes"]["note"])

    def test_installed_cli_is_not_implicit_consent(self):
        original_which = self.e.which
        self.e.which = lambda _name: "/usr/bin/fake"
        try:
            backend, _ = self.e.resolve_backend("disabled")
        finally:
            self.e.which = original_which
        self.assertIsNone(backend)

    def test_grok_backend_disables_tools_web_and_subagents(self):
        calls = []
        original_run = self.e.subprocess.run
        original_which = self.e.which
        original_home = os.environ.get("HOME")
        self.e.which = lambda name: "/usr/bin/grok" if name == "grok" else None

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            prompt_path = Path(command[command.index("--prompt-file") + 1])
            self.assertEqual(prompt_path.read_text(), "marker transcript: do not persist")
            self.assertEqual(prompt_path.stat().st_mode & 0o777, 0o600)
            session_key = urllib.parse.quote(kwargs["cwd"], safe="")
            session = Path(os.environ["HOME"]) / ".grok/sessions" / session_key / "session-id"
            session.mkdir(parents=True)
            (session / "chat_history.jsonl").write_text("marker transcript: do not persist")
            return subprocess.CompletedProcess(command, 0, "[]", "")

        with tempfile.TemporaryDirectory() as home:
            os.environ["HOME"] = home
            self.e.subprocess.run = fake_run
            try:
                ok, _ = self.e.call_llm("marker transcript: do not persist", "omarchy:grok")
            finally:
                self.e.subprocess.run = original_run
                self.e.which = original_which
                if original_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = original_home
            self.assertEqual(list((Path(home) / ".grok/sessions").glob("**/*")), [])
        self.assertTrue(ok)
        command = calls[0][0]
        self.assertNotIn("marker transcript: do not persist", command)
        self.assertNotIn("--single", command)
        self.assertIn("--prompt-file", command)
        self.assertIn("--deny", command)
        self.assertEqual(command[command.index("--deny") + 1], "*")
        self.assertIn("--no-subagents", command)
        self.assertIn("--disable-web-search", command)
        self.assertEqual(command[command.index("--max-turns") + 1], "1")
        self.assertNotIn("--model", command)

    def test_transcript_prompt_marks_input_as_untrusted(self):
        source = (QML_DIR / "lib" / "extract.py").read_text()
        self.assertIn("untrusted data", source)

    def test_parses_fenced_json(self):
        parsed = self.e.parse_json_block('sure!\n```json\n[{"a":1}]\n```\nthanks')
        self.assertEqual(parsed, [{"a": 1}])

    def test_parses_bare_json_array(self):
        self.assertEqual(self.e.parse_json_block('noise [{"a":2}] tail'), [{"a": 2}])

    def test_notes_prompt_matches_obsidian_granola_structure(self):
        self.assertIn("## Notes", self.e.NOTES)
        self.assertIn("### <descriptive topic heading>", self.e.NOTES)
        self.assertIn("## Action Items", self.e.NOTES)
        self.assertIn("## Next Steps", self.e.NOTES)

    def test_notes_fallback_uses_vault_action_item_format(self):
        original = self.e.call_llm
        self.e.call_llm = lambda *_args: (False, "")
        try:
            notes = self.e.write_notes(
                {"title": "Test"}, [], {
                    "commitments": [{
                        "text": "Send the report",
                        "owner": {"name": "Amit"},
                        "due": {"value": "2026-08-21"},
                    }],
                    "decisions": [], "risks": [], "questions": [],
                }, "transcript")
        finally:
            self.e.call_llm = original
        self.assertTrue(notes.startswith("## Notes"))
        self.assertIn("- [ ] Amit → Send the report 📅 2026-08-21", notes)


class ModelIntegrityTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(QML_DIR / "lib"))
        import model_integrity
        import transcribe
        self.integrity = model_integrity
        self.transcribe = transcribe

    def test_normal_transcription_accepts_only_hash_verified_exact_model(self):
        payload = b"reviewed model bytes"
        digest = __import__("hashlib").sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            model_dir = Path(directory)
            expected = model_dir / "ggml-test.bin"
            expected.write_bytes(payload)
            fallback = model_dir / "ggml-other.bin"
            fallback.write_bytes(payload)
            with patch.object(self.integrity, "WHISPER_MODEL_ARTIFACTS", {"test": digest}), \
                    patch.object(self.transcribe, "WHISPER_MODEL_ARTIFACTS", {"test": digest}), \
                    patch.object(self.transcribe, "MODEL_DIRS", (model_dir,)):
                self.assertEqual(expected, self.transcribe.find_model("test"))
                expected.write_bytes(b"tampered")
                self.assertIsNone(self.transcribe.find_model("test"))
                self.assertIsNone(self.transcribe.find_model("other"))

    def test_tampered_model_never_reaches_whisper_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "ggml-test.bin"
            model.write_bytes(b"tampered")
            with patch.object(self.integrity, "WHISPER_MODEL_ARTIFACTS", {
                        "test": __import__("hashlib").sha256(b"expected").hexdigest()}), \
                    patch.object(self.transcribe, "WHISPER_MODEL_ARTIFACTS", {"test": "expected"}), \
                    patch.object(self.transcribe, "MODEL_DIRS", (root, root)), \
                    patch.object(self.transcribe, "whisper_bin", return_value="whisper-cli"), \
                    patch.object(self.transcribe.subprocess, "run") as run:
                result = self.transcribe.transcribe(root / "audio.opus", root, "test")
            self.assertFalse(result["ok"])
            self.assertIn("SHA-256", result["error"])
            run.assert_not_called()


class SpeakerResolutionTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(QML_DIR / "lib"))
        import transcribe
        self.t = transcribe

    def segs(self):
        return [
            {"start": 0, "end": 2, "text": "Hello there", "cluster": "SPEAKER_00", "stream": "mic"},
            {"start": 2, "end": 5, "text": "Hi, it's Sidd here", "cluster": "SPEAKER_01", "stream": "system"},
        ]

    def test_mic_anchors_me_with_top_confidence(self):
        parts, _ = self.t.resolve_speakers(
            self.segs(), [], {"name": "Amit Patel", "email": "a@b.com", "organizer": True})
        me = [p for p in parts if p["is_me"]][0]
        self.assertEqual(me["resolved_by"], "mic_anchor")
        self.assertEqual(me["confidence"], 0.99)

    def test_single_attendee_resolves_remote(self):
        attendees = [{"email": "sidd@ayon.com", "displayName": "Sidd"}]
        parts, _ = self.t.resolve_speakers(
            self.segs(), attendees, {"name": "Amit", "email": "a@b.com"})
        remote = [p for p in parts if not p["is_me"]][0]
        self.assertEqual(remote["email"], "sidd@ayon.com")
        self.assertEqual(remote["resolved_by"], "calendar_single_match")

    def test_unknown_speaker_never_guessed(self):
        segs = [{"start": 0, "end": 3, "text": "some words here",
                 "cluster": "SPEAKER_01", "stream": "system"},
                {"start": 3, "end": 6, "text": "more words",
                 "cluster": "SPEAKER_02", "stream": "system"}]
        parts, conflicts = self.t.resolve_speakers(segs, [], {"name": "Amit"})
        unknown = [p for p in parts if p["name"] is None]
        self.assertTrue(unknown, "unidentified speakers must stay unnamed")
        for p in unknown:
            self.assertTrue(p["needs_human"])
            self.assertEqual(p["confidence"], 0.0)

    def test_invited_but_silent_is_flagged(self):
        attendees = [{"email": "ghost@ayon.com", "displayName": "Ghost"},
                     {"email": "other@ayon.com", "displayName": "Other"}]
        _, conflicts = self.t.resolve_speakers(self.segs(), attendees, {"name": "Amit"})
        issues = {c["issue"] for c in conflicts}
        self.assertIn("invited_but_silent", issues)

    def test_talk_time_percentages(self):
        parts, _ = self.t.resolve_speakers(self.segs(), [], {"name": "Amit"})
        self.assertAlmostEqual(sum(p["talk_time_pct"] for p in parts), 100.0, places=0)


class CalendarCapabilityTest(unittest.TestCase):
    """Distinguish a real capability gap from an empty calendar."""

    def setUp(self):
        self.mod = load_helper()

    def test_detects_patched_calendar(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "omascribe-calendar"
            path.write_text('def attendees(event):\n    return []\n'
                            '.. "attendees": attendees(event),\n')
            self.assertTrue(self.mod.supports_attendees(str(path)))

    def test_detects_unpatched_calendar(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "omascribe-calendar"
            path.write_text('def normalize(e):\n    return {"id": e["id"]}\n')
            self.assertFalse(self.mod.supports_attendees(str(path)))

    def test_missing_file_is_not_capable(self):
        self.assertFalse(self.mod.supports_attendees("/nonexistent/omascribe-calendar"))


class AutopilotTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(QML_DIR / "lib"))
        import autopilot
        self.a = autopilot

    def cfg(self):
        mod = load_helper()
        return mod.DEFAULT_CONFIG

    def qualifies(self, event, cfg):
        return load_helper().qualifies(event, cfg)

    def test_arms_before_start(self):
        from datetime import datetime, timedelta
        now = datetime.now().astimezone()
        start = now + timedelta(minutes=3)      # inside the 5 min lookahead
        event = {"title": "Sync", "joinUrl": "https://meet.google.com/x",
                 "start": start.isoformat(),
                 "end": (start + timedelta(hours=1)).isoformat()}
        self.assertIsNotNone(
            self.a.due_event([event], self.cfg(), self.qualifies, now))

    def test_ignores_far_future_meeting(self):
        from datetime import datetime, timedelta
        now = datetime.now().astimezone()
        start = now + timedelta(hours=3)
        event = {"title": "Sync", "joinUrl": "https://meet.google.com/x",
                 "start": start.isoformat(),
                 "end": (start + timedelta(hours=1)).isoformat()}
        self.assertIsNone(
            self.a.due_event([event], self.cfg(), self.qualifies, now))

    def test_reminds_five_minutes_before_meeting(self):
        from datetime import datetime, timedelta
        now = datetime.now().astimezone()
        start = now + timedelta(minutes=4)
        event = {"id": "reminder-1", "title": "Sync",
                 "joinUrl": "https://meet.google.com/x",
                 "start": start.isoformat(),
                 "end": (start + timedelta(hours=1)).isoformat()}
        self.assertEqual(
            self.a.reminder_events([event], self.cfg(), self.qualifies, now), [event])

    def test_does_not_remind_too_early_or_after_start(self):
        from datetime import datetime, timedelta
        now = datetime.now().astimezone()
        events = []
        for offset in (-1, 6):
            start = now + timedelta(minutes=offset)
            events.append({"id": str(offset), "title": "Sync",
                           "joinUrl": "https://meet.google.com/x",
                           "start": start.isoformat(),
                           "end": (start + timedelta(hours=1)).isoformat()})
        self.assertEqual(
            self.a.reminder_events(events, self.cfg(), self.qualifies, now), [])

    def test_stays_armed_for_late_start(self):
        """A meeting that began 20 minutes ago must still be captured."""
        from datetime import datetime, timedelta
        now = datetime.now().astimezone()
        start = now - timedelta(minutes=20)
        event = {"title": "Sync", "joinUrl": "https://meet.google.com/x",
                 "start": start.isoformat(),
                 "end": (start + timedelta(hours=1)).isoformat()}
        self.assertIsNotNone(
            self.a.due_event([event], self.cfg(), self.qualifies, now))

    def test_claim_lock_is_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            self.assertTrue(self.a.claim(state, "evt1", "p7um-xps"))
            self.assertFalse(self.a.claim(state, "evt1", "p7um-studio"),
                             "a second host must not claim the same meeting")
            self.assertTrue(self.a.claim(state, "evt1", "p7um-xps"),
                            "the owning host may reclaim after a restart")

    def test_claim_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            self.a.claim(state, "evt2", "host-a")
            self.a.release(state, "evt2")
            self.assertTrue(self.a.claim(state, "evt2", "host-b"))

    def test_sleep_gap_detected(self):
        from datetime import datetime, timedelta
        now = datetime.now().astimezone()
        self.assertTrue(self.a.slept_since(now - timedelta(hours=2), now, 60))
        self.assertFalse(self.a.slept_since(now - timedelta(seconds=61), now, 60))
        self.assertFalse(self.a.slept_since(None, now, 60))


class AutopilotCliTest(unittest.TestCase):
    def run_cli(self, *args, env=None):
        e = dict(os.environ)
        e.update(env or {})
        return subprocess.run([sys.executable, str(HELPER), *args],
                              capture_output=True, text=True, env=e, timeout=120)

    def test_tick_is_idempotent_when_idle(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"XDG_STATE_HOME": d, "XDG_CONFIG_HOME": d}
            for _ in range(2):
                r = self.run_cli("tick", "--json", env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(json.loads(r.stdout)["state"], ("idle", "paused"))

    def test_tick_respects_pause(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"XDG_STATE_HOME": d, "XDG_CONFIG_HOME": d}
            self.run_cli("pause", env=env)
            r = self.run_cli("tick", "--json", env=env)
            self.assertEqual(json.loads(r.stdout)["state"], "paused")

    def test_legacy_watchdog_and_timer_installer_are_not_exposed(self):
        help_text = self.run_cli("--help").stdout
        self.assertNotIn("watchdog", help_text)
        self.assertNotIn("install-timers", help_text)

    def test_commitments_overdue_exits_nonzero_when_found(self):
        """A cron needs a non-zero exit to raise an alert."""
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault" / "2026-01-01-test"
            vault.mkdir(parents=True)
            (vault / "meeting.json").write_text(json.dumps({
                "meeting": {"id": "t", "title": "T"},
                "commitments": [{"id": "cmt_0001", "status": "open",
                                 "owner": {"name": "Sidd"}, "text": "send deck",
                                 "due": {"value": "2020-01-01"}}],
            }))
            cfgdir = Path(d) / "config" / "omascribe"
            cfgdir.mkdir(parents=True)
            (cfgdir / "config.json").write_text(json.dumps(
                {"vault": {"path": str(Path(d) / "vault")}}))
            r = self.run_cli("commitments", "--overdue", "--json",
                             env={"XDG_CONFIG_HOME": str(Path(d) / "config"),
                                  "XDG_STATE_HOME": d})
            self.assertEqual(r.returncode, 2)
            self.assertEqual(json.loads(r.stdout)["count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
