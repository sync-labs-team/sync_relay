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
| `allowed_tools` | `[]` | Extra tools the main session may use, for example `"mcp__server__tool"`. Added to the built-in list of orchestration tools. This is the only way to let an MCP tool through: there is no guessing from the name. Example: `["mcp__plugin_syncgate_syncgate__syncgate_status"]`. |
| `allow_reads` | `true` | `false` turns off `read_commands` and the `Read` exception (not the repository file). |
| `read_commands` | the seed below | Patterns of Bash commands the locked main session may run. See "What the lock lets through". |
| `read_max_kb` | `64` | `cat`, `head`, `tail` and `Read` of a file over this many KB are not let through. |
| `read_max_lines` | `200` | `Read` with a `limit` up to this many lines is let through whatever the file size. |
| `codex_interactive_originators` | `["codex-tui", "codex_work_desktop"]` | Codex originators counted as interactive sessions. |
| `routing` | see below | `routing.<layer>.<claude or codex>` with `agent`, `model`, `effort`. `"model": null` passes no model, so the subagent inherits the session's. |

Default folder for handoffs:

- Windows: `%LOCALAPPDATA%\sync_relay\handoffs`
- macOS and Linux: `$XDG_STATE_HOME/sync_relay/handoffs`, or `~/.local/state/sync_relay/handoffs`

## What the lock lets through

The locked main session may still do small, harmless reads. What counts is **your** list, not a rule in the code. The seed is the default of `read_commands`; it is a starting point, so adjust it to your context (replace the list, add to it, or set `"read_commands": []` to keep only what you put yourself). `"allow_reads": false` turns the whole thing off.

The seed:

```json
"read_commands": [
  "git status", "git status *", "git log", "git log *",
  "git diff --stat", "git diff --stat *", "git diff --name-only", "git diff --name-only *",
  "git branch", "git branch --show-current", "ls", "ls *", "pwd", "cat *", "head *", "tail *", "git --version",
  "!-o", "!--ou*", "!-f*", "!-F*", "!-[!-]*f*", "!-[!-]*F*", "!--follow*"
]
```

How a pattern reads (the whole command, token by token, split on spaces):

- a token is matched like a shell glob (`*`, `?`, `[...]`), case-sensitive;
- `*` alone is one word; as the last token (after other tokens) it is one or more words, so `ls *` needs an argument and `ls` is listed on its own;
- `!x` is a veto: the command is refused when any argument matches `x`. The seed vetoes the flags that write a file (`-o`, `--output`) or never end (`-f`, `-F`, `--follow`, also inside `-nf`). A consequence: `ls -F` is refused too. Veto entries only apply to `read_commands`, not to the repository file;
- the FIRST word of a pattern is always literal (no `*`, `?`, `[`): a pattern with a wildcard there (`* status`, `[a-z]* *`) is ignored, with a notice at session start. It would free any program. This holds for `read_commands` and for the repository file.

The seed has no pattern with a wildcard in the first word, so nothing like `rm status` gets through. Add your own commands one by one (`docker ps`, `cargo xtask ci *`).

The one fixed rule is structural and holds for `read_commands` and for the repository file: the whole command must be ONE simple command. A command with any of `|`, `;`, `&` (so also `&&`, `||` and a trailing `&`), `<`, `>`, a backtick, `$` (so `$(`), `(`, `)`, a line break, `'`, `"`, `\`, `~`, `*`, `?`, `[`, `]`, `{` or `}` is refused, even inside quotes (there is no quote parsing, on purpose: after this check the split on spaces is exact, so a veto cannot be hidden by quotes or a backslash). A side effect: `HEAD~1` and quoted names are refused. `cat`, `head` and `tail` also need at least one file argument, and EVERY argument that is not an option must be an existing regular file (resolved from the hook's working directory; a device, a folder, a link to a device, a missing path or a path Python cannot see is refused) of at most `read_max_kb` KB. The number after `-n` or `-c` is not a file. `head -c N` with N above `read_max_kb` x 1024 is refused. On Windows write paths with `/`: a backslash is refused.

`Read` is let through when the file is at most `read_max_kb` KB (or does not exist), or when the call has a `limit` of at most `read_max_lines`.

MCP tools are not let through by any heuristic: only by `allowed_tools`.

### One repository: `.claude/sync_relay.json`

Put this in the working directory or in a parent up to the git root (without a git repository, only the working directory counts):

```json
{ "allowed_commands": ["cargo xtask ci", "cargo xtask ci *"] }
```

Same pattern format (first word literal) and same structural rule, whole command, no `!` entries. The file only loosens: it lets these Bash commands through in the main session and can never tighten anything. You are told before any command runs: at session start the plugin lists the patterns the file frees (`sync_relay: <repo>/.claude/sync_relay.json lets the main session run: `cargo xtask ci`, ...`), and again at the first release if the working directory moves to another repository with a different file (one notice per file and session). A broken file is ignored. It works even with `"allow_reads": false`. Nothing here replaces Claude Code's own permission prompts: the plugin only stops denying. Do not trust a file from a repository you do not trust: a pattern like `curl *` is yours to approve.

## Session mode

`/relay off`, `/relay remind` and `/relay on` (with the mod) or, without the mod and on Codex, the whole message `relay off`, `relay remind` or `relay on` (case ignored, a leading `/` allowed) set the lock for the open session only, with no restart. It comes from your own message or command, never from a model tool call. Claude Code, however, also runs `UserPromptSubmit` hooks for scheduled prompts (`/loop`, `CronCreate`, `ScheduleWakeup`), for a background subagent reporting back and for a message from another session, and the hook input has no field that tells them apart from a typed prompt (checked in the hooks reference, 2026-11-22). So a scheduled prompt that says `relay off` would be taken as yours. The way out is not shown to the model (the denial text does not mention it; the hint goes only to you, at session start), but this is not a barrier. Order of precedence: session mode, then `SYNC_RELAY_MODE`, then the config file.

The mode is a small file `_modo-<key>.txt` in the handoff folder. The key is `p<CLAUDE_PID>` on Claude Code (the process: it survives `/clear`, the session id does not), else `s<session id>`; on Codex it is the session id. A new Claude Code process (`SessionStart` with `startup`) deletes the mode file of its own key first, so a reused PID never inherits an old `off`. Files older than 7 days are cleaned with the other plugin files. `/relay status` shows where the current mode comes from.

## Delegation table

| Layer | Claude Code | Codex |
|---|---|---|
| `lookup` | `Explore`, haiku, low | `explorer`, low |
| `judgment` | `general-purpose`, sonnet, medium | `explorer`, medium |
| `build` | `general-purpose`, sonnet, medium | `worker`, medium |
| `hard` | `general-purpose`, opus, high | `worker`, high |
| `plan` | `general-purpose`, opus, xhigh | `worker`, high |

## Environment variables

They win over the file, but not over a mode you set with `/relay off|remind|on` in the open session.

| Variable | Values |
|---|---|
| `SYNC_RELAY_MODE` | `off`, `remind`, `enforce`, `force`. `force` treats every session as interactive; for testing. |
| `SYNC_RELAY_LANG` | `auto`, `en`, `pt-BR` |
| `SYNC_RELAY_CONFIG` | Path of another config file. |
| `SYNC_RELAY_AUTO` | `1` or `0`. Claude Code only, one session. |
| `SYNC_RELAY_THRESHOLD` | `150k` or `150000`. Claude Code only, one session. |

The names `SYNCLABS_RELAY_MODE`, `SYNCLABS_RELAY_LANG`, `SYNCLABS_RELAY_CONFIG`, `SYNCLABS_RELAY_THRESHOLD` and `SYNCLABS_RELAY_AUTO` (and the old band names) still work when the `SYNC_RELAY_*` one is not set. You get one notice per session that they go away in 0.4.0.

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
