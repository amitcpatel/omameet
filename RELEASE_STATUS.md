# OmaScribe 0.5.3 release status

## Product direction

OmaScribe 0.5.3 is the personal-first, opinionated Omarchy meeting assistant:

- Google Calendar through the user's GCP OAuth project.
- Scheduled and ad-hoc recording from the shell panel.
- Local Whisper transcription.
- Note optimization through the AI agent selected by Omarchy; Grok is the
  currently supported default agent.
- Obsidian-compatible notes and structured meeting records.

## Changes since 0.3.5

- Restored the labelled Record/Stop control and processing after manual stop.
- Added a dedicated settings view and simplified the calendar header.
- Removed the entire non-Google calendar-feed subsystem, including its hidden
  CLI, storage, parsing, network, agenda, and preference paths.
- Replaced Claude/endpoint selection with dynamic `omarchy-default-agent`
  resolution.
- Constrained Grok to one turn with tools denied, web search disabled, and
  subagents disabled.
- Required explicit persisted consent before any transcript reaches Grok.
- Moved Grok prompts from argv to private temporary files and removed ephemeral
  local Grok session state after each call.
- Pinned the two supported Whisper model artifacts to an immutable upstream
  revision and verify their published SHA-256 values before use.
- Hash-verify the exact allowlisted model before every normal transcription and
  reject arbitrary fallback GGML files.
- Make requested AI notes part of pipeline success: failures are persisted and
  reported, audio is retained, and saved transcripts have an explicit retry path.
- Marked transcripts and meeting metadata as untrusted data in every AI pass.
- Fixed lookalike meeting-domain acceptance and model-name path traversal.
- Removed stale persistent timer units from the development machine; runtime
  automation remains owned by the plugin service.

## Release checks

Before tagging or marketplace submission, require:

```bash
python -m unittest discover -s tests -v
python -m py_compile bin/omascribe-calendar bin/omascribe-meetings lib/*.py
bash -n install.sh uninstall.sh
omarchy plugin validate .
git diff --check
```

The marketplace submission and a `v0.5.3` tag must reference the same
validated commit. Earlier OmaMeet tags remain historical and are not marketplace
submission candidates.
