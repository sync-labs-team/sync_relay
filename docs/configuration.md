# Configuration

One JSON file for both CLIs. The plugin looks for it here, first match wins:

1. the path in `SYNC_RELAY_CONFIG`
2. `$XDG_CONFIG_HOME/sync_relay/config.json`
3. Windows: `%APPDATA%\sync_relay\config.json`
4. `~/.config/sync_relay/config.json`

A missing file, invalid JSON, a wrong type or an unknown key is ignored and the default applies, with no error. A UTF-8 BOM is fine. Your values override the defaults key by key; inside `routing`, layer by layer and CLI by CLI.

## Keys

| Key | Default | What it does |
|---|---|---|
| `mode` | `"enforce"` | `enforce` denies work tools in the main session. `remind` only reminds. `off` turns off the lock and the reminders; the handoff still works. |
| `lang` | `"auto"` | `auto`, `en` or `pt-BR`. Case does not matter: `pt`, `pt-BR`, `pt_BR` and `pt-*` mean pt-BR; `en`, `en-*` and `en_*` mean English. `SYNC_RELAY_LANG` wins only when it is one of these. `auto` reads `LC_ALL`, `LC_MESSAGES`, `LANG`, then the system locale (the band reads only the system locale): `pt` is pt-BR, everything else is English. |
| `threshold_tokens` | `150000` (when absent) | The `D` in the switch point rule (see [how-it-works.md](how-it-works.md)). Must be above 0. The mod accepts 5,000 to 900,000. |
| `button` | `true` | Show the fixed button `sync_relay auto: on/off` (Claude Code). `/relay button` changes it and is remembered between sessions; the config value only counts while that choice is not stored. The status line is always shown. |
| `auto` | `false` (when absent) | Optional. Start with the automatic switch on (Claude Code). Without it, auto starts off. `/relay auto` is remembered between sessions and wins over this key; the config value only counts while nothing is stored. `SYNC_RELAY_AUTO` (one session) wins over both. |
| `handoff_dir` | `""` | Absolute folder for handoffs. Empty means the default (below). `~` at the start means your home folder. Windows needs a drive (`C:\` or `C:/`) or a network path (`\\server\share`); macOS and Linux need a leading `/`. A relative path, a path with a `..` segment, or a folder the plugin cannot use falls back to the default. The core and the band apply the same rule. On macOS and Linux the plugin does not change the permissions of a folder you configure. |
| `stop_warning` | `true` | The Claude Code `Stop` warning. Set it to `false` on Claude Code, since the mod shows its own status. |
| `report_max_chars` | `4000` | Longest subagent report. Longer ones are sent back once for a shorter version. `0` turns the limit off. |
| `allowed_tools` | `[]` | Extra tools the main session may use, for example `"mcp__server__tool"`. Added to the built-in list of orchestration tools. |
| `codex_interactive_originators` | `["codex-tui", "codex_work_desktop"]` | Codex originators counted as interactive sessions. |
| `routing` | see below | `routing.<layer>.<claude or codex>` with `agent`, `model`, `effort`. `"model": null` passes no model, so the subagent inherits the session's. |

Default folder for handoffs:

- Windows: `%LOCALAPPDATA%\sync_relay\handoffs`
- macOS and Linux: `$XDG_STATE_HOME/sync_relay/handoffs`, or `~/.local/state/sync_relay/handoffs`

## Delegation table

| Layer | Claude Code | Codex |
|---|---|---|
| `lookup` | `Explore`, haiku, low | `explorer`, low |
| `judgment` | `general-purpose`, sonnet, medium | `explorer`, medium |
| `build` | `general-purpose`, sonnet, medium | `worker`, medium |
| `hard` | `general-purpose`, opus, high | `worker`, high |
| `plan` | `general-purpose`, opus, xhigh | `worker`, high |

## Environment variables

They win over the file.

| Variable | Values |
|---|---|
| `SYNC_RELAY_MODE` | `off`, `remind`, `enforce`, `force`. `force` treats every session as interactive; for testing. |
| `SYNC_RELAY_LANG` | `auto`, `en`, `pt-BR` |
| `SYNC_RELAY_CONFIG` | Path of another config file. |
| `SYNC_RELAY_AUTO` | `1` or `0`. Claude Code only, one session. |
| `SYNC_RELAY_THRESHOLD` | `150k` or `150000`. Claude Code only, one session. |

The switch point also reads, from Claude Code: `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, `autoCompactWindow` in its settings, `CLAUDE_CODE_DISABLE_1M_CONTEXT` and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`; from Codex: `model_auto_compact_token_limit` in `config.toml`.

## Example

A fictional user:

```json
{
  "lang": "en",
  "threshold_tokens": 120000,
  "stop_warning": false,
  "allowed_tools": ["mcp__notes__search"],
  "routing": {
    "build": {
      "claude": { "agent": "general-purpose", "model": "haiku", "effort": "medium" },
      "codex": { "agent": "worker", "model": "my-model-id", "effort": "medium" }
    }
  }
}
```

Saved as `C:\Users\alice\AppData\Roaming\sync_relay\config.json` on Windows or `~/.config/sync_relay/config.json` elsewhere. Model ids on the Codex side are yours; the plugin ships none.
