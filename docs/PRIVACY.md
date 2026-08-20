# Privacy and security boundaries

## What stays local

- Audio capture
- Whisper transcription
- Calendar caches and preferences
- Meeting metadata and structured extraction records
- Obsidian-compatible notes and retained recovery audio

Google Calendar data is fetched from Google's API using the user's OAuth grant.
The requested scope is read-only. Refresh tokens are stored through the system
keyring rather than embedded in plugin configuration.

## When transcript text may leave the machine

AI optimization is enabled by default in 0.4.0. When enabled and Omarchy's
default agent resolves to Grok, meeting transcript text and structured meeting
context are sent through the installed Grok CLI. The behavior and retention of
that remote service are governed by the user's Grok/xAI account and terms.

Disable remote optimization at any time:

```bash
omameet-meetings ai disable
```

Transcription continues locally and deterministic basic notes are still written.

## Agent restrictions

OmaMeet invokes Grok with:

- one turn;
- non-interactive permission mode;
- all tools denied;
- web search disabled;
- subagents disabled; and
- no explicit model override.

Every extraction and note prompt declares transcript, participant, calendar, and
structured-item content to be untrusted data whose embedded instructions must
not be followed. Unsupported default agents fail closed instead of falling back
to another provider.

## Untrusted calendar content

Calendar strings are rendered as plain text. Meeting links are restricted to
anchored Google Meet, Zoom, Microsoft Teams, and Webex hosts; lookalike domains
are rejected. External links are passed to `xdg-open` as argument arrays, not
through a shell command.

## Deletion and uninstall

`uninstall.sh` removes only command links that point into this plugin. Plugin
removal does not delete settings, OAuth state, recordings, transcripts, or the
notes vault. This avoids accidental data loss; users may remove those locations
manually after reviewing their contents.
