# sync_relay

One plugin for Claude Code and Codex: keeps the main session delegating, hands a session over to a fresh one, and warns at the switch point. On Claude Code it also adds the `/relay` command, a fixed button `sync_relay auto: on/off` (pt-BR: `ligado/desligado`) and a status line (`sync_relay: auto off · 45k of 150k`). Codex ignores that part (the mod).

```sh
claude plugin marketplace add sync-labs-team/plugins
claude plugin install sync-relay@sync-labs
```

Codex (not tested in a real session):

```sh
codex plugin marketplace add sync-labs-team/plugins
codex plugin add sync-relay@sync-labs
```

Needs Python 3.9 or newer as `python3`. Codex runs the hooks only after you approve them with `/hooks`.

| Command (Claude Code) | What it does |
|---|---|
| `relay` (the whole message) | Writes the handoff; then `/clear` (Codex: `/new`). |
| `/relay` | Writes the handoff and opens the new session now. |
| `/relay auto` | Turns the automatic switch on or off. Remembered between sessions. |
| `/relay button` | Shows or hides the button. Remembered between sessions. The status line stays. |
| `/relay status` | Lock mode and its origin, auto, context, switch point and its origin, handoff folder. |
| `/relay off`, `/relay remind`, `/relay on` | The lock for THIS session only, no restart. Without the mod, and on Codex, type the whole message `relay off`, `relay remind` or `relay on`. |

The mod uses the Claude Code mods API (early access, can change). With it active, set `"stop_warning": false` in the config so you do not get two warnings.

On Claude Code the plugin pre-approves one `Write`: the session's own handoff file, under strict conditions. Your `deny` and `ask` rules still apply.

The technical name is `sync-relay` (kebab-case), installed from the Sync Labs catalog `sync-labs`; the product keeps `sync_relay`.

Everything else is in the [repository README](../../README.md) ([pt-BR](../../README.pt-BR.md), [es](../../README.es.md)) and in [docs/](../../docs).
