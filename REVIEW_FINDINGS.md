# OmaMeet 0.4.0 review record

This file carries forward the independent pre-submission review performed
against 0.3.5 and records how its findings were handled in 0.4.0.

| Finding | 0.4.0 disposition |
|---|---|
| Working tree differed from the tagged release | Resolved by versioning and committing the complete product reset as 0.4.0. |
| Lookalike Zoom/Webex domains accepted | Resolved with anchored host matching and regression tests. |
| Direct `file://` calendar sources accepted | Resolved; users must provide an explicit local `.ics` path. |
| Whisper model-name path traversal | Resolved with a strict model-name allowlist and regression test. |
| Agent tools could process untrusted transcript instructions | Grok is constrained to one turn with tools denied, web search disabled, and subagents disabled. Every AI prompt labels meeting content as untrusted data. |

## Preserved safeguards

- Calendar-controlled text is rendered as plain text.
- Audio is retained whenever transcription or extraction fails.
- Plugin automation is owned by `Service.qml`; no persistent watchdog or timer
  installation is required.
- OAuth tokens remain in the system keyring and configuration/state files use
  private directories or explicit `0600` permissions where sensitive.

## Remaining review gate

Run an independent review against the exact pushed 0.4.0 commit before creating
the `v0.4.0` tag or re-triggering the Omarchy marketplace submission.
