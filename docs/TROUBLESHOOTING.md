# Troubleshooting and recovery

## Health check

```bash
omascribe-meetings doctor --json
omascribe-meetings status --json
omascribe-meetings ai status --json
```

Without optional command links, prefix commands with
`~/.config/omarchy/plugins/acp.omascribe/bin/`.

## Panel still shows an older UI

First rescan plugins:

```bash
omarchy-shell shell rescanPlugins
```

If an open panel instance survives hot reload, fully recreate it:

```bash
omarchy plugin disable acp.omascribe
omarchy restart shell
omarchy plugin enable acp.omascribe
```

## AI is unavailable

Check the selected Omarchy agent and OmaScribe's resolution:

```bash
omarchy-default-agent
omascribe-meetings ai status --json
```

Version 0.5.4 supports Grok. An unsupported or unavailable selected agent fails
closed; local transcription still runs, and basic notes are written.

When enabled AI notes fail after a transcript is saved, OmaScribe records the
backend error and reports partial processing. Retry without source audio using:

```bash
omascribe-meetings regenerate-notes /path/to/meeting-folder
```

## Recording captured silence

Run `omascribe-meetings doctor --json` and inspect the reported PulseAudio source,
sink monitor, `ffmpeg`, and `whisper-cli` checks. A silence failure retains the
recording directory under `~/.local/state/omascribe/recordings/` rather
than deleting evidence needed for recovery.

## Processing failed

The desktop notification and command output identify the meeting directory.
Inspect its session metadata and retained audio, fix the failing dependency, then
run the process command against that directory:

```bash
omascribe-meetings process /absolute/path/to/recording-directory --json
```

## Google Calendar will not connect

Confirm that the Google Calendar API is enabled, the OAuth client type is
Desktop, and the downloaded file exists at
`~/.config/omascribe-calendar/client_secret.json` with mode `0600`. Then click
**Add Google** again and complete browser authorization.

## Logs

```bash
journalctl --user --since "30 minutes ago" --no-pager | grep -i omascribe
```

Avoid sharing logs or meeting folders publicly without reviewing them for names,
calendar details, transcript content, and access tokens.
