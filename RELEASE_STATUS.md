# OmaMeet release status

Last updated: 2026-08-19

## Current state

- Product: **OmaMeet — AI Meeting Notes** (`acp.omameet`)
- Repository: <https://github.com/amitcpatel/omameet>
- Marketplace submission: <https://github.com/HANCORE-linux/omarchy-plugin-marketplace/issues/788>
- Submission state: open, structurally validated, awaiting requested QML hardening fix
- Current public release before this change: `v0.3.4` at `adac6f7`
- Prepared security release: `v0.3.5`

Do not open another marketplace submission. Continue with issue #788.

## Review history and fixes

The first maintainer finding was that the legacy `install-timers` command could
leave persistent user timers after uninstall. Version 0.3.2 removed that command,
the watchdog, and the timer installer entirely. The native Omarchy service is now
the sole automatic detector.

The second finding was that processing could automatically pass transcripts to
an installed Codex or Claude CLI without OmaMeet-specific consent. Version 0.3.3
addresses this by:

- disabling AI notes by default;
- removing automatic backend discovery;
- requiring `omameet-meetings ai enable BACKEND` with an explicit `codex`,
  `claude`, or `endpoint` choice;
- treating AI-disabled local transcription as a normal successful outcome;
- documenting that enabled backends may receive transcript text; and
- adding regression tests proving installed CLIs are not implicit consent and
  the disabled path never calls an AI backend.

The third finding was that transcript prompt injection could drive tools exposed
by the Codex or Claude agent CLIs. Version 0.3.4 removes the Codex CLI backend
because it has no tool-free execution mode, invokes Claude with an empty tool
set and all customization/MCP surfaces disabled, and requires HTTP endpoints to
honor `tool_choice: none` with no declared tools.

The fourth finding was that calendar-controlled strings were rendered with
QML's automatic text-format detection. Version 0.3.5 forces event titles,
calendar/account labels, and externally derived errors through
`Text.PlainText`. It adds a dedicated plain-text toggle for the shared control
that does not expose `textFormat`, and sanitizes calendar-derived bar tooltips
before they cross into the shared tooltip component.

## Verification

For v0.3.5:

- `omarchy plugin validate .` passes;
- all 106 unit and contract tests pass;
- Python source compiles;
- installer and removal scripts pass `bash -n`;
- `git diff --check` passes.

`qmllint` is not installed on the development machine. The changed QML is also
loaded in the running Omarchy Shell and checked for plugin-specific warnings.

## Remaining marketplace review

After v0.3.5 is published, edit and comment on issue #788 to re-run validation.
Confirm that validation reports v0.3.5 and the new commit. The deterministic
security baseline may continue to request manual review for the optional setup
scripts and transient `systemd-run --user` processing job; that flag is expected
and is not itself a new defect.

Marketplace approval and removal of the `needs-fixes` label remain maintainer
actions.

## Product principles

- Calendar, capture, and transcription remain local by default.
- Transcript text reaches AI only after an OmaMeet-specific opt-in.
- Calendar time alone never starts recording.
- Preserve private calendar URLs, recordings, transcripts, and notes.
- Prefer native Omarchy lifecycle behavior over persistent timers.
