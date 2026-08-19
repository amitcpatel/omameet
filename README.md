# OmaMeet — AI Meeting Notes

OmaMeet puts your day on the Omarchy bar: a fast, private calendar with
one-click meeting joins and optional local recording, transcription, and
AI-generated notes.

It is useful before any meeting automation is configured. Add a private
iCalendar subscription, see the day at a glance, and join Google Meet, Zoom,
Teams, or Webex without opening a calendar tab.

## Why it belongs in Omarchy

- It turns the bar into a calm, native day planner instead of another web app.
- It follows the active Omarchy theme and shell panel behavior.
- Calendar subscriptions work without a Google Cloud project or OAuth consent
  screen.
- Calendar reads, audio capture, and transcription happen locally. Cloud AI is
  optional and explicit.
- Calendar time never starts a recording. Automatic capture requires a known
  meeting application to be actively using the microphone.

## Install

OmaMeet requires Omarchy 4 (Quattro).

```bash
omarchy plugin add https://github.com/amitcpatel/omameet.git --enable
```

The widget appears on the right side of the bar. Left-click opens the day,
middle-click refreshes it, and right-click opens calendar settings.

No setup script or background timer is required for the calendar. The enabled
Omarchy service handles refreshes, reminders, and meeting detection.

## Add a calendar without Google Cloud

Right-click the OmaMeet icon and paste a private iCalendar subscription URL.
You can find this URL in most calendar products under names such as **Secret
address in iCal format**, **Private calendar URL**, or **Subscribe**.

OmaMeet accepts `https://`, `webcal://`, and local `.ics` files. It supports
timed and all-day events, folded fields, time zones, exclusions, additional
dates, and common daily, weekly, monthly, and yearly recurrence rules.

You can also add a source from the command line after enabling the optional
command links described below:

```bash
omameet-calendar source add 'https://example.com/private/calendar.ics' --name Personal
omameet-calendar source list
omameet-calendar source remove SOURCE_ID
```

Subscription URLs often contain a secret token. OmaMeet stores them in
`~/.local/state/omarchy-calendar/feeds.json` with mode `600`, never displays
them in the UI or `source list`, and only accepts encrypted remote URLs.

## Optional Google Calendar connection

The iCalendar path is recommended for the simplest read-only setup. Connect the
Google Calendar API only if you need multiple Google calendars with attendee
metadata and per-calendar controls.

1. In Google Cloud, create a project and enable **Google Calendar API**.
2. Configure an OAuth consent screen and add `openid`, `email`, and
   `https://www.googleapis.com/auth/calendar.readonly`.
3. Create a **Desktop app** OAuth client.
4. Save its JSON with private permissions:

   ```bash
   mkdir -p ~/.config/omarchy-calendar
   install -m 600 ~/Downloads/client_secret_*.json \
     ~/.config/omarchy-calendar/client_secret.json
   ```

5. Run `omameet-calendar account add`, or click **Google** in OmaMeet's
   calendar settings.

OAuth uses PKCE and a temporary loopback redirect. Refresh tokens live in the
desktop keyring through `secret-tool`; calendar access is read-only.

## Optional AI meeting notes

Calendar and joining features need only Python 3.11+. Meeting capture adds:

- `ffmpeg`, `ffprobe`, `pactl`, and `pw-cli`;
- `whisper-cli` or `whisper-cpp` plus a local model;
- one notes backend: authenticated Codex CLI, Claude CLI, or an
  OpenAI-compatible `/chat/completions` endpoint.

The plugin store intentionally does not run install hooks. To add convenient
command links, run the repository's safe setup script:

```bash
~/.config/omarchy/plugins/acp.omameet/install.sh
omameet-meetings config --init
omameet-meetings fetch-model base.en
omameet-meetings doctor --json
```

Set the output directory in `~/.config/omarchy-meetings/config.json`:

```json
{
  "vault": {
    "path": "~/Documents/Meeting Notes"
  }
}
```

The destination can be an Obsidian vault, ordinary directory, Dropbox folder,
Syncthing folder, or Git repository. Each meeting gets its own directory with:

- `notes.md` — AI-generated notes, decisions, action items, next steps, and risks;
- `transcript.md` — timestamped transcript;
- `meeting.json` — structured facts and processing evidence.

Audio is deleted only after transcription, extraction, and output writes are
verified. A failed run retains its recording for recovery.

### Recording behavior

- Clicking **Join** starts capture before opening the meeting URL.
- Automatic capture requires a supported meeting app to own an active
  microphone stream; a scheduled event alone is never enough.
- Calendar context is attached only when its meeting platform matches the
  active app.
- Unplanned calls prompt by default. Set `detection.autoRecordUnplanned` to
  `true` only if that behavior and local consent rules are appropriate.
- Capture ends 90 seconds after the app releases the microphone. Five minutes
  of silence is the fallback.

Recording consent remains the user's responsibility.

Useful controls:

```bash
omameet-meetings status --json
omameet-meetings record start --title "Meeting"
omameet-meetings record stop
omameet-meetings pause
omameet-meetings pause --off
omameet-meetings audit --json
```

### AI backend

OmaMeet selects `OMAI_LLM_ENDPOINT`, then an authenticated Codex CLI, then the
Claude CLI. For a compatible endpoint:

```bash
export OMAI_LLM_ENDPOINT="http://127.0.0.1:11434/v1"
export OMAI_LLM_MODEL="your-model-name"
export OMAI_LLM_API_KEY="optional-bearer-token"
```

Without a notes backend, OmaMeet keeps the recording and transcript so they can
be processed later.

## Privacy and security

- Plugins run unsandboxed with your user permissions. Review the source before
  enabling any Omarchy plugin.
- Never commit OAuth credentials, private calendar URLs, recordings,
  transcripts, or generated notes.
- Calendar data, capture, and transcription stay local.
- Transcript text leaves the machine only when you configure a cloud notes
  backend. Files sync only when you choose a synced output directory.
- Use recording features in accordance with participant consent, workplace
  policy, and applicable law.

## Remove

```bash
~/.config/omarchy/plugins/acp.omameet/uninstall.sh
omarchy plugin remove acp.omameet
```

Removal keeps settings, calendar sources, recordings, and notes. Delete
`~/.config/omarchy-calendar`, `~/.local/state/omarchy-calendar`,
`~/.config/omarchy-meetings`, and `~/.local/state/omarchy-meetings` yourself
only if you also want to erase that data.

## Development and release checks

```bash
omarchy plugin validate .
qmllint -I "$OMARCHY_PATH/shell" BarWidget.qml Panel.qml Service.qml
python3 -m unittest discover -s tests -v
```

OmaMeet is MIT licensed. Version 0.3.2 removes the legacy timer installer and
watchdog notification; the native Omarchy service is the only automatic detector.
