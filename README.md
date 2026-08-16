# OmaMeet

OmaMeet is one native Omarchy Shell plugin for the whole meeting lifecycle:
calendar, one-click joining, automatic audio capture, local transcription,
AI summaries, action items, and Obsidian notes.

## How it works

- The themed day view aggregates multiple Google Calendar accounts.
- Clicking **Join** starts capture before opening Google Meet, Zoom, Teams, or Webex.
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
./install.sh
omameet-calendar account add
```

Right-click the bar widget to manage accounts, calendar visibility, and event
priority. Middle-click refreshes the agenda.

## Validate

```bash
omarchy plugin validate .
python3 -m unittest discover -s tests -v
```

## Privacy

Calendar data, credentials, raw audio, transcripts, and notes remain on this
machine unless the configured Obsidian vault syncs them. Automatic recording
must be used in accordance with the consent laws and policies that apply to the
meeting participants.
