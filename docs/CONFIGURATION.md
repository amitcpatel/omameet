# Configuration and command reference

Meeting configuration is JSON at
`~/.config/omascribe/config.json`. Missing keys inherit defaults, so a
minimal file may override only the values that differ.

```json
{
  "vault": {"path": "~/Projects/Knowledge/Meetings"},
  "retainAudio": false,
  "llm": {"backend": "disabled"}
}
```

## Important settings

| Key | Default | Meaning |
|---|---:|---|
| `vault.path` | `~/Projects/Knowledge/Meetings` | Meeting-note destination |
| `retainAudio` | `false` | Keep source audio after complete success |
| `minFreeDiskMB` | `2048` | Refuse capture below this free-space floor |
| `transcription.backend` | `local` | Local transcription path |
| `transcription.model` | `large-v3-turbo` | Preferred Whisper model name |
| `transcription.lang` | `en` | Transcription language |
| `llm.backend` | `disabled` | No cloud transcript processing until explicitly enabled |
| `notify.desktop` | `true` | Meeting lifecycle notifications |
| `notify.joinReminderMin` | `5` | Pre-meeting join reminder |
| `detection.calendarPoll` | `true` | Use calendar events as meeting context |
| `detection.audioActivity` | `true` | Detect known apps using the microphone |
| `detection.autoRecordUnplanned` | `false` | Automatically capture unplanned calls |
| `capture.lookaheadSec` | `300` | Calendar lookahead window |
| `capture.requireLink` | `true` | Require a recognized meeting link |
| `capture.minDurationMin` | `10` | Ignore shorter scheduled events |
| `capture.silenceStopSec` | `300` | Stop after sustained silence |
| `capture.appExitGraceSec` | `90` | Grace period after a meeting app exits |

The panel's plugin-level refresh and detector intervals are stored by the
Omarchy shell from `manifest.json`; they are separate from the meeting JSON.

## Commands

| Command | Purpose |
|---|---|
| `status --json` | Current recording/session state |
| `doctor --json` | Dependency, audio, calendar, vault, and AI checks |
| `config` | Print the merged effective configuration |
| `record start` | Start an ad-hoc recording |
| `record stop` | Stop and launch processing |
| `process DIR --json` | Process or retry a recording directory |
| `regenerate-notes DIR --json` | Retry AI notes from a saved meeting transcript |
| `ai status --json` | Show selected and resolved AI backend |
| `ai enable` / `ai disable` | Toggle AI note optimization |
| `pause` / `resume` | Pause or resume automatic detection |
| `next` | Show upcoming meeting decisions |
| `commitments` | Query extracted commitments |
| `fetch-model NAME` | Download and SHA-256 verify `base.en` or `large-v3-turbo` from a pinned revision |
| `version --json` | Print the installed OmaScribe version |

Run `omascribe-meetings --help` and the relevant subcommand help for the complete
machine-readable CLI surface.

`ai enable` records OmaScribe-specific consent by setting `llm.backend` to
`omarchy`. `ai disable` revokes that consent and returns it to `disabled`.

## Recording policy

Calendar events are context, not an automatic trigger by themselves. Automatic
capture requires matching microphone activity from a known meeting application.
Ad-hoc recording always requires the explicit Record action unless
`detection.autoRecordUnplanned` is deliberately enabled.
