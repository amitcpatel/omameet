# OmaScribe 0.5.2 review record

This file carries forward the independent pre-submission review performed
against 0.3.5 and records how its findings were handled through 0.4.2.

| Finding | Current disposition |
|---|---|
| Working tree differed from the tagged release | Resolved by versioning and committing the complete product reset as 0.4.0. |
| Lookalike Zoom/Webex domains accepted | Resolved with anchored host matching and regression tests. |
| Direct local calendar sources accepted | Removed in 0.5.2 with the complete non-Google calendar-feed subsystem. |
| Whisper model-name path traversal | Resolved with a strict model-name allowlist and regression test. |
| First-run AI consent | Resolved: AI defaults to disabled; enabling it persists OmaScribe-specific consent. Disabled processing performs local transcription and deterministic notes without invoking Grok. |
| Transcript exposed in process argv | Resolved: Grok receives a mode-`0600` `--prompt-file`; marker regression testing verifies transcript text is absent from argv. |
| Local Grok session retained transcript | Resolved: every call uses a unique temporary cwd and removes its exact local Grok session bucket afterward; marker regression testing verifies cleanup. |
| Private feed hosts and unsafe redirects | Removed in 0.5.2 with the complete non-Google calendar-feed subsystem. |
| AI disclosure omitted resolved agent/cloud transfer | Resolved: the enabled Panel description includes the resolved agent detail and states that transcript text is sent to its cloud service. |
| Mutable unverified Whisper model download | Resolved in 0.4.1: downloads are allowlisted, pinned to immutable upstream revision `5359861c739e955e79d9a303bcbc70fb988958b1`, and SHA-256 verified before cached or downloaded bytes are accepted. |
| Optional installer overwrote existing command paths | Resolved in 0.4.2: both destinations are preflighted before mutation; regular files and foreign symlinks fail closed, while links already owned by the same checkout are preserved. |
| Calendar-feed DNS validation was separate from consumption | Removed in 0.5.2 with the complete non-Google calendar-feed subsystem; no feed network path remains. |
| Normal transcription accepted unverified or fallback models | Resolved in 0.5.1: fetch and transcription share one artifact allowlist; normal transcription hashes the exact requested model and rejects missing, tampered, unsupported, and fallback files before launching Whisper. |
| Agent tools could process untrusted transcript instructions | Preserved: Grok remains constrained to one turn with tools denied, web search disabled, and subagents disabled. Every AI prompt labels meeting content as untrusted data. |

## Preserved safeguards

- Calendar-controlled text is rendered as plain text.
- Audio is retained whenever transcription or extraction fails.
- Plugin automation is owned by `Service.qml`; no persistent watchdog or timer
  installation is required.
- OAuth tokens remain in the system keyring and configuration/state files use
  private directories or explicit `0600` permissions where sensitive.

## 0.5.2 review gate

All listed safeguards remain implemented. The exact 0.5.2 tagged commit must
pass marketplace validation and manual review before listing.
