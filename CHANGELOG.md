# Changelog

## 0.2.1

Fixes asked for by someone who used it (a session that ran a repository's CI)
- Lock mode per session, no restart. `/relay off`, `/relay remind` and `/relay on` (the mod) or, without the mod and on Codex, the whole message `relay off`, `relay remind` or `relay on` (case ignored, a leading `/` allowed). Only the user types it (a scheduled prompt cannot be told apart, see SECURITY.md). It lasts for the open session: stored in a file named `_modo-<key>.txt` in the handoff folder, keyed by `CLAUDE_PID` on Claude Code (the id changes on `/clear`, the process does not) and by the session id on Codex, and it survives `/clear`. Precedence: session mode, then `SYNC_RELAY_MODE`, then the config. A hint on how to do it is shown to the user at session start, never to the model. `/relay status` shows where the mode comes from.
- Reads on the main session are let through by a list you control. New config keys: `allow_reads` (default `true`), `read_commands` (patterns of the whole command; the seed is explicit commands only: `git status`, `git log`, `git diff --stat`, `git diff --name-only`, `git branch`, `git --version`, `ls`, `pwd`, `cat`, `head`, `tail`, with vetoes for flags that write a file or never end), `read_max_kb` (64) and `read_max_lines` (200). The seed is a starting point: replace, extend or empty it. The fixed rules: the command must be ONE simple command, with no `|`, `;`, `&`, `<`, `>`, backtick, `$`, parentheses, line break, quote, backslash, `~` or glob character (so a veto cannot be hidden by quoting); the FIRST word of every pattern is literal (a wildcard there is ignored, with a notice); `cat`, `head` and `tail` only on an existing regular file of at most `read_max_kb` (device, folder, missing path refused; `head -c N` above the limit refused). `Read` is let through for a file up to `read_max_kb` or with a `limit` up to `read_max_lines`. MCP tools stay on `allowed_tools` only (for example `mcp__plugin_syncgate_syncgate__syncgate_status`).
- Per repository: `.claude/sync_relay.json` in the working directory or a parent up to the git root, `{"allowed_commands": ["cargo xtask ci", "cargo xtask ci *"]}`. Same patterns, same structural rule. It only loosens, a broken file is ignored, and you are told what it frees at session start (and again if the working directory moves to another repository with another file).
- Security review fixes: the seed no longer has `* status` / `* --version` (they ran `rm status`, `bash status`...); a new process reusing a PID no longer inherits `relay off` (`SessionStart` `startup` deletes the old mode file); the hint on how to turn the lock off goes only to the user (`systemMessage`), no longer to the model. Documented limits: the lock is not a sandbox (a subagent can write the mode file), a scheduled prompt cannot be told apart from a typed one in `UserPromptSubmit`, `Read` with a small `limit` reads any file, `SubagentStop` holds a subagent at most twice.
- A subagent no longer vanishes while a background task runs. `SubagentStop` reads `background_tasks`: with a `shell` or `monitor` task still running it answers `block` and asks the subagent to wait for the end notice and send the final report (respects `stop_hook_active`, at most 2 holds per subagent). The delegation table has one more line about commands over about 180 s going to the background. Documented limit in docs/faq.md.
- Technical name in kebab-case. The `name` of the plugin (both `plugin.json`) and of the marketplace (both catalogs) is now `sync-relay`, so `claude plugin validate --strict` passes clean and the claude.ai marketplace sync can validate it. It is published in the Sync Labs catalog, `sync-labs` (repository `Sync-Labs-team/plugins`): `claude plugin marketplace add sync-labs-team/plugins` and `claude plugin install sync-relay@sync-labs`, or `codex plugin marketplace add sync-labs-team/plugins` and `codex plugin add sync-relay@sync-labs`. Unchanged: the product name and brand `sync_relay` (texts, messages, the button label), the repository `Sync-Labs-team/sync_relay`, the `SYNC_RELAY_*` variables, the `sync_relay` config and handoff folders and `scripts/sync_relay.py`. Claude Code draws `sync-relay:` in front of the status line now. What the mod stores per plugin name (the remembered `/relay auto` and `/relay button`) may start from the defaults once.
- `SYNCLABS_RELAY_MODE`, `_LANG`, `_CONFIG`, `_THRESHOLD` and `_AUTO` work again when the `SYNC_RELAY_*` name is not set, with one notice per session that they go away in 0.4.0. (0.2.0 said the old names were not read; that broke anyone who had set them.)

Tests: 129 for the hooks and script, 189 for the mod.

Upgrading from 0.2.0 (the technical name changed, so it is a reinstall; restart the CLI after):
1. Claude Code: `claude plugin uninstall sync_relay@sync_relay`, `claude plugin marketplace remove sync_relay`, `claude plugin marketplace add sync-labs-team/plugins`, `claude plugin install sync-relay@sync-labs`.
2. Codex: `codex plugin remove sync_relay@sync_relay`, `codex plugin marketplace remove sync_relay`, `codex plugin marketplace add sync-labs-team/plugins`, `codex plugin add sync-relay@sync-labs` (approve the hooks again in `/hooks`).
3. Your config and handoff folders are the same. The remembered `/relay auto` and `/relay button` may start from the defaults once.

If you want the old behavior of denying every Bash and Read, set `"allow_reads": false`.

## 0.2.0

Rename and one plugin (breaking)
- The product is now `sync_relay` (lowercase, with an underscore) everywhere: plugin, marketplace, script (`scripts/sync_relay.py`), environment variables, config and handoff folders, visible texts (`sync_relay: ...` in messages, the button `sync_relay auto: on/off`, pt-BR `ligado/desligado`) and the repository URL, `https://github.com/Sync-Labs-team/sync_relay`.
- The core and the band are one plugin now. On Claude Code it carries the hooks and the mod (`/relay`, the button, the status line); Codex ignores the mod. There is no `-band` plugin and no dependency between plugins.
- `claude plugin validate` accepts the name but warns that it is not kebab-case, so `--strict` no longer passes clean, and the claude.ai marketplace sync does not accept the name. Installing from the GitHub marketplace in the CLIs is not affected.
- Environment variables: `SYNCLABS_RELAY_MODE`, `_LANG`, `_CONFIG` became `SYNC_RELAY_MODE`, `SYNC_RELAY_LANG`, `SYNC_RELAY_CONFIG`; `SYNCLABS_RELAY_BAND_AUTO` and `_BAND_THRESHOLD` became `SYNC_RELAY_AUTO` and `SYNC_RELAY_THRESHOLD`. The old names are not read.
- Folders: config in `%APPDATA%\sync_relay\config.json` (macOS and Linux: `$XDG_CONFIG_HOME/sync_relay/config.json`, or `~/.config/sync_relay/`), handoffs in `%LOCALAPPDATA%\sync_relay\handoffs` (`$XDG_STATE_HOME/sync_relay/handoffs`, or `~/.local/state/sync_relay/handoffs`). On first use, if the new config does not exist and the old `synclabs-relay` one does, it is copied (the old one is left in place). Old handoffs are not moved.

Tests: 90 for the hooks and script, 182 for the mod.

Upgrading from 0.1.x
1. Remove the old plugins: `claude plugin uninstall synclabs-relay-band@synclabs-relay`, then `claude plugin uninstall synclabs-relay@synclabs-relay`, then `claude plugin marketplace remove synclabs-relay`. On Codex: `codex plugin remove synclabs-relay@synclabs-relay` and `codex plugin marketplace remove synclabs-relay`.
2. Install the new one: `claude plugin marketplace add Sync-Labs-team/sync_relay` and `claude plugin install sync_relay@sync_relay` (Codex: `codex plugin marketplace add Sync-Labs-team/sync_relay`, `codex plugin add sync_relay@sync_relay`; approve the hooks again in `/hooks`). Restart the CLI.
3. Rename any `SYNCLABS_RELAY_*` variable you set to the `SYNC_RELAY_*` name above.
4. Your config is copied on first use. Delete the old `synclabs-relay` folders when you like. The remembered `/relay auto` and `/relay button` choices are stored per plugin name and may start from the defaults again.


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
