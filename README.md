# OmaMeet

OmaMeet is one native Omarchy Shell plugin for the whole meeting lifecycle:
calendar, one-click joining, automatic audio capture, local transcription,
AI summaries, action items, and Obsidian notes.

It combines the calendar and meeting-recorder workflows into a single bar
widget: see what is next, join it, capture it, and find the finished notes in
Obsidian without moving files by hand.

## How it works

- The themed day view aggregates multiple Google Calendar accounts.
- Clicking **Join** starts capture before opening Google Meet, Zoom, Teams, or Webex.
- Five minutes before a qualifying meeting, OmaMeet shows a one-time desktop
  notification labeled **JOIN ›**. Omarchy notifications use the whole card as
  the action: clicking it starts capture and opens the meeting URL.
- The background service also catches qualifying scheduled and unplanned calls.
- After a recognized meeting app stops capturing the microphone for 90 seconds,
  OmaMeet stops and processes the recording. Five minutes of silence is the
  fallback.
- `notes.md`, `transcript.md`, and `meeting.json` are written to the configured
  Obsidian Meetings folder.

The bar uses a calendar-check icon when idle and the theme's urgent recording
indicator while capture is active.

## Requirements

- Omarchy 4+
- Python 3.11+
- `ffmpeg`, `pactl`, and `whisper-cli`
- `secret-tool` from `libsecret`
- Google OAuth Desktop client with Calendar API enabled
- A configured Codex CLI for AI extraction (or another supported backend)

OmaMeet currently reuses the proven local state from its predecessors so an
upgrade does not lose accounts, preferences, or recordings:

- Calendar credentials and preferences: `~/.config/omarchy-calendar` and
  `~/.local/state/omarchy-calendar`
- Capture configuration and state: `~/.config/omarchy-meetings` and
  `~/.local/state/omarchy-meetings`

Place the Google OAuth JSON at
`~/.config/omarchy-calendar/client_secret.json` and protect it with mode 600.

## Install

```bash
git clone https://github.com/amitcpatel/omameet.git
cd omameet
./install.sh
omameet-calendar account add
```

Right-click the bar widget to manage accounts, calendar visibility, and event
priority. Middle-click refreshes the agenda.

The installer adds and enables `acp.omameet`, exposes the two command-line
helpers in `~/.local/bin`, and keeps the plugin linked to the checked-out
repository. Install the background automation with:

```bash
omameet-meetings install-timers
```

## Configure

Initialize and inspect the effective meeting configuration:

```bash
omameet-meetings config --init
omameet-meetings config --json
omameet-meetings doctor --json
```

Meeting settings live in `~/.config/omarchy-meetings/config.json`. Set
`vault.path` to the Meetings folder inside the Obsidian vault open on the
machine. For example:

```json
{
  "vault": {
    "path": "~/Documents/Projects/Knowledge/Meetings"
  },
  "notify": {
    "desktop": true,
    "joinReminderMin": 5
  }
}
```

Values omitted from this file retain their built-in defaults.

## Automation

OmaMeet checks the agenda and active meeting applications every 15 seconds.
Scheduled meetings with supported join URLs can start automatically. It also
recognizes active Zoom, Google Meet, Microsoft Teams, and Webex calls from the
desktop audio/window signals. Clicking **Join** in the panel or reminder starts
recording before the URL is opened.

When the meeting application stops publishing its microphone stream, OmaMeet
waits 90 seconds before stopping. A five-minute silence limit is the safety
fallback. The completed recording is then transcribed, summarized, and written
to Obsidian. Recording consent remains the user's responsibility.

Useful controls:

```bash
omameet-meetings status --json
omameet-meetings pause
omameet-meetings pause --off
omameet-meetings record start --title "Meeting"
omameet-meetings record stop
omameet-meetings next --json
```

## Obsidian output

Each meeting receives its own timestamped directory under `vault.path`:

- `notes.md` — summary, decisions, action items, and follow-ups
- `transcript.md` — the raw transcript
- `meeting.json` — structured meeting data for automation and querying

Audio is deleted only after the transcript, extraction, and vault write are
verified. If AI extraction fails, OmaMeet preserves both the transcript and the
audio so the meeting can be processed again.

## Validate

```bash
omarchy plugin validate .
python3 -m unittest discover -s tests -v
```

For an installed copy, `omameet-meetings doctor --json` verifies the audio
devices, transcription model, AI backend, calendar access, and vault path.

## Release status

Version 0.2.0 is the first combined OmaMeet release. The repository contains
the Omarchy manifest, bar widget, panel, background service, installer, meeting
and calendar helpers, processing libraries, and automated tests required to
publish the plugin. No OAuth secrets, recordings, transcripts, or vault notes
belong in this repository.

## Privacy

Calendar data, credentials, raw audio, transcripts, and notes remain on this
machine unless the configured Obsidian vault syncs them. Automatic recording
must be used in accordance with the consent laws and policies that apply to the
meeting participants.
