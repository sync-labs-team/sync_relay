# Changelog

## 0.1.2

Fixes after publishing 0.1.1
- The band's status line no longer repeats the product name in its text (`auto off · 45k of 150k`, `measuring`, `switching…`). Claude Code already puts the plugin name in front of a mod's status line, so 0.1.1 showed `synclabs-relay-band: Sync_Relay · auto off · …`.
- `SendFeedback` is allowed in the main session. It only drafts a report on your machine and sends nothing. The other coordination tools (`ListAgents`, `TaskStop`, `PushNotification`, the `Cron*` tools, `ScheduleWakeup`, plan mode, `AskUserQuestion`, `ToolSearch`, `Skill`, `SendMessage`, `Agent`, `Task*`, `TodoWrite`) were already allowed. `Monitor` (runs a command), `WebFetch`, `WebSearch` and `Artifact` stay locked.
- Docs: `/relay` is a command of the band; typing `relay` as the whole message works with or without the band.

Tests: 87 for the core, 182 for the band.

Upgrading from 0.1.1
- Update both plugins (`claude plugin marketplace update synclabs-relay`, then `claude plugin update synclabs-relay` and `claude plugin update synclabs-relay-band@synclabs-relay`), then restart Claude Code. Nothing is stored under a new key in this release.
- If you only run the core, `relay` (no slash) is the way to switch; `/relay` exists only with the band installed.

## 0.1.1

Safe switch
- The core waits for a subagent that has not reported back before asking for the handoff, and the `Stop` warning waits too (it reads `background_tasks`).
- The handoff carries what `/clear` does not keep: the `/goal` (word for word), scheduled tasks (id, schedule, prompt, from `CronList`) and background commands or agents still running. Measured in `claude -p` 2.1.329: `/clear` drops the goal, keeps scheduled tasks and keeps background work running.
- When a handoff is given back after a failed delivery, its marker comes back with it.
- The band does not start its countdown while an agent is alive.

Switch point and commands
- The switch point is `floor + min(D, 0.8 x (C - floor))`: `D` is `threshold_tokens` (150,000 by default), `floor` the tokens of the session's first response (measured: everything the CLI loaded at the start, not a file), `C` the CLI's auto-compaction point (Claude Code: `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, `autoCompactWindow`, then the model's window; Codex: `model_auto_compact_token_limit`). Examples with a floor of 30k: Claude 1M, 180k; Claude 200K, 166k; Codex with a limit of 120k, 102k.
- The band command is `/relay` (`auto`, `button`, `status`); any other argument prints the usage. Typing `relay` as the whole message does the same as `/relay`.
- New status line next to the statusLine: `Sync_Relay · auto off · 45k of 150k` (also `measuring`, `switching…`), and a fixed button `Sync_Relay auto: on/off`. `/relay button` hides only the button. `/relay button` and `/relay auto` are remembered between sessions. `/relay status` also shows whether the button is visible or hidden. New config keys `button` (default `true`) and `auto` (optional; without it auto starts off); they only count while the band's store has no value.

Code Mode
- Code Mode: the `REPL` wrapper and `Poll` (which waits for its result or a background agent's) are allowed in the main session; calls inside it are still checked by name.

Docs
- README in English, Portuguese (pt-BR) and Spanish; `docs/` with configuration, how it works and FAQ; `CONTRIBUTING.md`, `AGENTS.md` and issue forms. Contributions are by issue only.

Tests: 86 for the core, 182 for the band.

Upgrading from 0.1.0
- `/handoff`, `handoff` and `passagem` stop working. Use `relay` (with the band installed, `/relay` too).
- The `threshold`, `limiar` and `botao` subcommands are gone. Set `threshold_tokens` and `button` in the config file.
- A threshold you stored with the old command in the band's state is ignored. Set `threshold_tokens` in the config file if you want one.
- The switch point now depends on the model's window, so it can differ from the old fixed growth. `/relay status` shows it and where it comes from.
- There is a new status line.

## 0.1.0

First release. Both plugins are at 0.1.0.

Core (`synclabs-relay`, Claude Code and Codex)
- Lock: `PreToolUse` denies work tools in the main interactive session; subagents and automation (`claude -p`, `codex exec`) pass. Modes `enforce` (default), `remind`, `off`.
- Delegation table injected at `SessionStart`, built from the config (`routing`), with a report-size request and a `SubagentStop` hook that asks once for a shorter report.
- Handoff: the word `handoff` (or `passagem`, with or without `/`) asks the model to write the state of the work to a file; the next session in the same directory, in either CLI, receives it. The core is the only part that delivers it. Files live in a per-user folder, are taken once and expire after 30 minutes for delivery.
- Claude Code delivery: the marker `_req-<PID>.txt` holds the file name `<slug>-<8hex>.md`; an empty marker means canceled and delivers nothing. Without `CLAUDE_PID`, `/clear` delivers the only `<slug>-<8hex>.md` under 30 minutes old, and nothing when there are two or more. A handoff taken and then hit by an error before printing is renamed back.
- File names: `<readable part>-<h8>` (the last 60 characters of the lowercase path, then the FNV-1a 32-bit hash of the normalized directory), so directories like `my_app` and `my-app` never share a handoff. Claude Code adds `-<8 characters of the session id>`.
- The routing table is cut to fit what the handoff leaves under 9,000 characters; the handoff is never cut for it.
- `handoff_dir` follows one rule in the core and the band: `~` expands, Windows needs a drive or a network path, macOS and Linux a leading `/`, no `..` segment. `lang` is read the same way in both (case-insensitive, `pt`, `pt-*`, `en`, `en-*`).
- On macOS and Linux the default handoff folder is set to `0700` when the plugin uses it; a folder you configure in `handoff_dir` keeps its permissions. A folder of another user is refused.
- The Codex hook command reads `PLUGIN_ROOT` and falls back to `CLAUDE_PLUGIN_ROOT`.
- Cleanup after 7 days: `_req-N.txt`, `_detect-*.flag` and `_trace-<8hex>.md` in any folder; the handoff `.md` files (and `.usada.md`) only in the default folder, so a folder you configured never loses a note of yours.
- Permission: on Claude Code the core pre-approves only the `Write` of the session's own handoff file (main session, valid `CLAUDE_PID`, marker at most 10 minutes old, exact path, safe folder, target not a link, at most 8,000 characters), in every mode. `deny` and `ask` rules still apply.
- Context warning at `Stop`, when the context grew `threshold_tokens` over the session start.
- Config in one JSON file, English and pt-BR messages, no network calls.

Band (`synclabs-relay-band`, Claude Code only, optional)
- Banner and button that trigger the switch, an automatic mode (off by default) with a 15 s countdown, and the `/handoff` command (`auto`, `button`, `threshold`). The button sends `handoff` to the prompt and depends on the core for writing and delivery. Cancel empties the marker and withdraws the request. The success toast is "Handoff saved; new session opened.", which does not claim delivery.

Changed from the earlier local setup
- `/passagem` no longer exists as a command. Typing the word `passagem` still works, with or without `/`. The command is now `/handoff`, registered by the band.

Tests: 76 for the core, 161 for the band.

Codex support is untested in 0.1.0
- The plugin installs on Codex 0.170.0 and its hook command was run directly, without a model, and denied a tool as expected. It was not tested in a real Codex session: that the lock and the context warning work after you approve the hooks in `/hooks`, and that `handoff` followed by `/new` delivers the file, has not been seen. Tests are planned for the next version.

Install
- Installing from the GitHub repository was confirmed at publication, on Claude Code 2.1.329 and Codex 0.170.0. Installing from a local clone was run too.
