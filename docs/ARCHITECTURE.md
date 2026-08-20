# Architecture

OmaMeet is a native Omarchy shell plugin with two entry points:

- `BarWidget.qml` provides the bar icon, hover status, and panel entry.
- `Service.qml` runs the detector while the plugin is enabled.

`Panel.qml` owns the calendar UI, Record/Stop controls, settings, and helper
processes. It resolves helpers by absolute path inside the plugin directory, so
the UI does not depend on an installation hook or the user's `PATH`.

## Data flow

1. `bin/omameet-calendar` reads Google Calendar using read-only OAuth access.
2. `Service.qml` periodically invokes `omameet-meetings tick`.
3. Calendar time supplies context; microphone use by a known meeting app is the
   automatic recording trigger. Calendar presence alone never starts capture.
4. `ffmpeg` captures microphone and monitor audio into a meeting session.
5. Manual Stop or the detector's stop condition launches processing in a
   transient user service.
6. `lib/transcribe.py` invokes local `whisper-cli`.
7. `lib/extract.py` extracts verified structured outcomes and renders notes.
8. `lib/vault.py` writes the meeting folder and audit metadata.
9. Source audio is removed only after the pipeline reports complete success,
   unless `retainAudio` is enabled.

## AI resolution

The configured backend is `omarchy`, not a hard-coded model. At processing time
OmaMeet runs `omarchy-default-agent`. Version 0.4.0 supports Grok and deliberately
fails closed for unsupported agents. Grok is invoked for a single turn with
tools denied, web search disabled, subagents disabled, and no model override.

## Runtime ownership

The detector belongs to `Service.qml` and stops when the plugin is disabled.
Long transcription jobs use self-cleaning transient `systemd-run --user
--collect` services so they are not killed with a detector tick. OmaMeet does
not require persistent timers or watchdog services.

## Main locations

| Purpose | Location |
|---|---|
| Plugin | `~/.config/omarchy/plugins/acp.omameet/` |
| Meeting configuration | `~/.config/omarchy-meetings/config.json` |
| Meeting runtime state/audio | `~/.local/state/omarchy-meetings/` |
| Google OAuth client | `~/.config/omarchy-calendar/client_secret.json` |
| Google account/calendar state | `~/.local/state/omarchy-calendar/` |
| Default notes vault | `~/Projects/Knowledge/Meetings/` |
