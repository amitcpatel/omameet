# Changelog

## 0.5.4 — capture the meeting application and verify transcript coverage

- Resolve active input and output routes for known meeting applications through
  PulseAudio/PipeWire instead of assuming their devices match system defaults.
- Open explicit meeting links first, briefly wait for Chrome or the meeting app
  to expose both routes, and record route provenance or fallback status in the
  session and meeting contract.
- Reject long transcripts below a conservative spoken-word coverage floor,
  persist the coverage result, notify urgently, and retain all source audio.
- Runtime-verify Pulse monitor capture through Opus and the allowlisted
  `large-v3-turbo` model in addition to 127 behavioral tests.

## 0.5.3 — make requested AI notes part of pipeline success

- Treat an enabled AI notes pass as successful only when it returns non-empty
  notes; persist its exact error, exit nonzero, notify urgently, and retain audio
  when it fails.
- Clarify that Grok must use only supplied context and must not inspect files or
  call tools, preventing an unnecessary second turn while preserving the
  one-turn and tool-denial safeguards.
- Add `regenerate-notes FOLDER` to retry notes safely from an existing saved
  transcript when source audio is unavailable.

## 0.5.2 — Google Calendar only

- Remove the entire optional iCalendar subsystem: feed storage, local and remote
  source handling, parser and recurrence expansion, agenda merging, preference
  branches, CLI commands, network code, and associated tests.
- Add a regression proving the removed runtime symbols and `source` command are
  unavailable. OmaScribe now accepts calendar data only through Google Calendar
  using the user's read-only OAuth grant.

## 0.5.1 — bind network and model validation to consumption

- Eliminate iCalendar DNS-rebinding exposure by connecting to the exact public
  IP address validated for each request and same-origin redirect while retaining
  TLS certificate and hostname verification.
- Require every model used by normal transcription to match the shared
  allowlisted SHA-256 digest; remove arbitrary GGML fallback selection.
- Add behavioral regressions proving the validated IP reaches the socket and a
  tampered or unrequested model never reaches the Whisper process.

## 0.5.0 — renamed to OmaScribe

- Rename the product, plugin ID, repository, commands, runtime namespaces, UI,
  and documentation from OmaMeet to OmaScribe to avoid colliding with the
  independently published `dorneles.omameet` plugin.
- Preserve local-development settings, recordings, calendar state, and Google
  OAuth access through a non-destructive migration path.
- Retain every security safeguard reviewed for the 0.4.2 submission.

## 0.4.2 — non-destructive optional installer

- Refuse to overwrite regular files or foreign symlinks at either optional command-link destination.
- Preflight both command destinations before creating either link, preventing partial installation on conflict.
- Preserve and accept command links that already resolve to the same checkout.
- Add behavioral installer and uninstaller regression coverage with an isolated `HOME`.

## 0.4.1 — verified model artifacts

- Pinned Whisper model downloads to immutable upstream revision
  `5359861c739e955e79d9a303bcbc70fb988958b1`.
- Restricted downloads to `base.en` and `large-v3-turbo`.
- Verify published SHA-256 values before accepting cached or downloaded models.

## 0.4.0 — personal-first rebuild

- Made Google Calendar through the user's GCP OAuth project the primary path.
- Restored labelled ad-hoc Record/Stop controls and processing after Stop.
- Added a gear-based settings view and a two-level calendar header.
- Changed bar hover text to the next meeting or `No events`.
- Replaced Claude/endpoint configuration with `omarchy-default-agent` resolution.
- Added constrained single-turn Grok note optimization.
- Required persisted application-specific consent before sending transcripts to AI.
- Removed transcripts from Grok argv and cleaned ephemeral local session state.
- Rejected private calendar-feed hosts and cross-origin redirects.
- Added explicit prompt-injection boundaries for untrusted meeting content.
- Hardened meeting-domain matching and Whisper model-name validation.
- Expanded release, privacy, architecture, and recovery documentation.

## 0.3.5

- Forced calendar-controlled text to render as plain text.

## 0.3.4

- Removed the Codex backend and constrained the previous Claude integration.

## 0.3.3

- Added explicit AI opt-in for the 0.3.x provider model.

## 0.3.2

- Removed persistent watchdog/timer installation from the plugin lifecycle.
