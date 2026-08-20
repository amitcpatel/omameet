# OmaMeet 0.4.0 review record

This file carries forward the independent pre-submission review performed
against 0.3.5 and records how its findings were handled in 0.4.0.

| Finding | 0.4.0 disposition |
|---|---|
| Working tree differed from the tagged release | Resolved by versioning and committing the complete product reset as 0.4.0. |
| Lookalike Zoom/Webex domains accepted | Resolved with anchored host matching and regression tests. |
| Direct `file://` calendar sources accepted | Resolved; users must provide an explicit local `.ics` path. |
| Whisper model-name path traversal | Resolved with a strict model-name allowlist and regression test. |
| First-run AI consent | Resolved: AI defaults to disabled; enabling it persists OmaMeet-specific consent. Disabled processing performs local transcription and deterministic notes without invoking Grok. |
| Transcript exposed in process argv | Resolved: Grok receives a mode-`0600` `--prompt-file`; marker regression testing verifies transcript text is absent from argv. |
| Local Grok session retained transcript | Resolved: every call uses a unique temporary cwd and removes its exact local Grok session bucket afterward; marker regression testing verifies cleanup. |
| Private feed hosts and unsafe redirects | Resolved: remote feeds reject private, loopback, link-local, reserved, multicast, and unspecified addresses; redirects cannot change HTTPS origin. |
| AI disclosure omitted resolved agent/cloud transfer | Resolved: the enabled Panel description includes the resolved agent detail and states that transcript text is sent to its cloud service. |
| Agent tools could process untrusted transcript instructions | Preserved: Grok remains constrained to one turn with tools denied, web search disabled, and subagents disabled. Every AI prompt labels meeting content as untrusted data. |

## Preserved safeguards

- Calendar-controlled text is rendered as plain text.
- Audio is retained whenever transcription or extraction fails.
- Plugin automation is owned by `Service.qml`; no persistent watchdog or timer
  installation is required.
- OAuth tokens remain in the system keyring and configuration/state files use
  private directories or explicit `0600` permissions where sensitive.

## Remaining review gate

All listed fixes are implemented locally and require an independent review of
the final commit. Do not create `v0.4.0` or re-trigger the marketplace until that
exact commit passes review.
