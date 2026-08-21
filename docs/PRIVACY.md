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

AI optimization is disabled by default. Transcript text does not reach
Grok until the user explicitly enables AI in OmaScribe Settings. That action
persists OmaScribe-specific consent. When enabled and Omarchy's default agent
resolves to Grok, meeting transcript text and structured meeting context are sent
through the installed Grok CLI. Remote handling is governed by the user's
Grok/xAI account and terms.

Disable remote optimization at any time:

```bash
omascribe-meetings ai disable
```

Transcription continues locally and deterministic basic notes are still written.

## Agent restrictions

OmaScribe invokes Grok with:

- one turn;
- non-interactive permission mode;
- all tools denied;
- web search disabled;
- subagents disabled; and
- no explicit model override.

Prompts are passed through a mode-`0600` temporary file instead of process
arguments. Each call runs in a unique temporary working directory; OmaScribe
deletes that directory and its corresponding local Grok session bucket after
the process exits. This prevents local Grok conversation history from retaining
the transcript, but does not make claims about the cloud service's retention.

Every extraction and note prompt declares transcript, participant, calendar, and
structured-item content to be untrusted data whose embedded instructions must
not be followed. Unsupported default agents fail closed instead of falling back
to another provider.

## Untrusted calendar content

Calendar strings are rendered as plain text. Meeting links are restricted to
anchored Google Meet, Zoom, Microsoft Teams, and Webex hosts; lookalike domains
are rejected. External links are passed to `xdg-open` as argument arrays, not
through a shell command.

OmaScribe accepts calendar data only from Google Calendar through the user's
read-only OAuth grant. It does not support local or remote calendar feeds.

## Model supply chain

`fetch-model` accepts only `base.en` and `large-v3-turbo`, downloads from the
immutable whisper.cpp model revision recorded in the source, and verifies the
artifact's published SHA-256 before moving it into the model directory. Existing
cached models must also match the allowlisted digest before they are accepted.
Normal transcription performs the same verification immediately before use and
does not fall back to another model file.

## Deletion and uninstall

`uninstall.sh` removes only command links that point into this plugin. Plugin
removal does not delete settings, OAuth state, recordings, transcripts, or the
notes vault. This avoids accidental data loss; users may remove those locations
manually after reviewing their contents.
