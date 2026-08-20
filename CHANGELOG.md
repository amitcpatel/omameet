# Changelog

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
- Required persisted OmaMeet-specific consent before sending transcripts to AI.
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
