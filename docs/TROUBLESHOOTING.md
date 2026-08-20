# Troubleshooting and recovery

## Health check

```bash
omameet-meetings doctor --json
omameet-meetings status --json
omameet-meetings ai status --json
```

Without optional command links, prefix commands with
`~/.config/omarchy/plugins/acp.omameet/bin/`.

## Panel still shows an older UI

First rescan plugins:

```bash
omarchy-shell shell rescanPlugins
```

If an open panel instance survives hot reload, fully recreate it:

```bash
omarchy plugin disable acp.omameet
omarchy restart shell
omarchy plugin enable acp.omameet
```

## AI is unavailable

Check the selected Omarchy agent and OmaMeet's resolution:

```bash
omarchy-default-agent
omameet-meetings ai status --json
```

Version 0.4.0 supports Grok. An unsupported or unavailable selected agent fails
closed; local transcription still runs, and basic notes are written.

## Recording captured silence

Run `omameet-meetings doctor --json` and inspect the reported PulseAudio source,
sink monitor, `ffmpeg`, and `whisper-cli` checks. A silence failure retains the
recording directory under `~/.local/state/omarchy-meetings/recordings/` rather
than deleting evidence needed for recovery.

## Processing failed

The desktop notification and command output identify the meeting directory.
Inspect its session metadata and retained audio, fix the failing dependency, then
run the process command against that directory:

```bash
omameet-meetings process /absolute/path/to/recording-directory --json
```

## Google Calendar will not connect

Confirm that the Google Calendar API is enabled, the OAuth client type is
Desktop, and the downloaded file exists at
`~/.config/omarchy-calendar/client_secret.json` with mode `0600`. Then click
**Add Google** again and complete browser authorization.

## Logs

```bash
journalctl --user --since "30 minutes ago" --no-pager | grep -i omameet
```

Avoid sharing logs or meeting folders publicly without reviewing them for names,
calendar details, transcript content, and access tokens.
