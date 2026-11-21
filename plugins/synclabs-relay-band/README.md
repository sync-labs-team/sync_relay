# Sync_Relay band (synclabs-relay-band)

Optional, Claude Code only. Adds the `/relay` command, a fixed button `Sync_Relay auto: on/off` (pt-BR: `ligado/desligado`) and a status line (`synclabs-relay-band: auto off · 45k of 150k`). The band only triggers the switch; the handoff is written and delivered by the core plugin `synclabs-relay`, which this plugin depends on.

```sh
claude plugin install synclabs-relay-band@synclabs-relay
```

| Command | What it does |
|---|---|
| `/relay` | Writes the handoff and opens the new session now. |
| `/relay auto` | Turns the automatic switch on or off. Remembered between sessions. |
| `/relay button` | Shows or hides the button. Remembered between sessions. The status line stays. |
| `/relay status` | Lock mode, auto, context, switch point and its origin, handoff folder. |

Uses the Claude Code mods API (early access, can change). With the band installed, set `"stop_warning": false` in the config so you do not get two warnings.

Everything else is in the [repository README](../../README.md) ([pt-BR](../../README.pt-BR.md), [es](../../README.es.md)) and in [docs/](../../docs).
