# OmaMeet 0.4.0 release status

## Product direction

OmaMeet 0.4.0 is the personal-first, opinionated Omarchy meeting assistant:

- Google Calendar through the user's GCP OAuth project.
- Scheduled and ad-hoc recording from the shell panel.
- Local Whisper transcription.
- Note optimization through the AI agent selected by Omarchy; Grok is the
  currently supported default agent.
- Obsidian-compatible notes and structured meeting records.

## Changes since 0.3.5

- Restored the labelled Record/Stop control and processing after manual stop.
- Added a dedicated settings view and simplified the calendar header.
- Removed iCalendar subscription setup from the product UI.
- Replaced Claude/endpoint selection with dynamic `omarchy-default-agent`
  resolution.
- Constrained Grok to one turn with tools denied, web search disabled, and
  subagents disabled.
- Marked transcripts and meeting metadata as untrusted data in every AI pass.
- Fixed lookalike meeting-domain acceptance and model-name path traversal.
- Removed stale persistent timer units from the development machine; runtime
  automation remains owned by the plugin service.

## Release checks

Before tagging or marketplace submission, require:

```bash
python -m unittest discover -s tests -v
python -m py_compile bin/omameet-calendar bin/omameet-meetings lib/*.py
bash -n install.sh uninstall.sh
omarchy plugin validate .
git diff --check
```

The 0.4.0 commit may be pushed for review, but marketplace resubmission and a
`v0.4.0` tag should wait for an independent review of the exact pushed commit.
