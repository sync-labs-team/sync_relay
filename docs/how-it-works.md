# How it works

## The lock

On `PreToolUse`, the main interactive session is denied any tool that is not on the free list: the orchestration tools (`Agent`, `SendMessage`, `AskUserQuestion`, `ToolSearch`, `Skill`, the task tools, plan mode, and on Codex `spawn_agent`, `wait`, `send_input`, `update_plan` and similar). Add more with `allowed_tools`.

The lock lets a few things through by your own list: Bash commands that match `read_commands` (a seed of harmless reads, one simple command with no shell metacharacter, quote, backslash or glob, first word literal; `cat`, `head` and `tail` only on a regular file within the size limit), `Read` of a small file or with a small `limit`, and the commands of the repository's `.claude/sync_relay.json`. What it frees and how to change it: [configuration.md](configuration.md#what-the-lock-lets-through). The user can also turn the lock off, or to a reminder, for the open session alone (`/relay off`, `/relay remind`, `/relay on`, or the same words typed as the whole message): the mode is stored per Claude Code process (`CLAUDE_PID`) or Codex session id, survives `/clear`, and wins over `SYNC_RELAY_MODE` and the config.

What counts as the main interactive session:

- Claude Code: the process was not started by `claude -p` or the SDK (`CLAUDE_CODE_ENTRYPOINT` does not start with `sdk`), and the call carries no `agent_id`.
- Codex: the rollout header names an interactive originator (`codex-tui`, `codex_work_desktop` by default) and the session is not a subagent.

If the plugin cannot tell, it does not block: it prints one message per session and carries on (fail open). The lock keeps the model on task; it is not a sandbox.

Code Mode (`CLAUDE_CODE_EXPERIMENTAL_CODE_MODE=1`): the `REPL` wrapper and `Poll` (waiting for its result) are on the free list. Each tool call inside it fires its own `PreToolUse` under the real tool name (`Read`, `Bash`, `Agent`...) and is judged like any other call, so `Read` is still denied and `Agent` still passes. Known limits: if the JavaScript of the REPL reads files or starts processes without calling a tool, that is outside the lock (the official documentation does not describe it); and because the plugin fails open, a hook failure in Code Mode means the inner call runs (Claude Code's default there, unless `onFailure` is `block`).

## The delegation table

When a main session starts, resumes, clears or compacts, the plugin injects a table of five layers (look up, technical judgment, build, hard debugging, plan), rendered from the config. The defaults are in [configuration.md](configuration.md). The table also asks subagents for a short report; a longer one (over `report_max_chars`) is sent back once by the `SubagentStop` hook. One more line tells the main session that Claude Code sends every Bash over about 180 s to the background, so it must wait for the end notice and return the final result, never only a partial one.

The `SubagentStop` hook also holds a subagent that tries to finish while a background shell or monitor task of the session is still running (`background_tasks` in the hook input; measured with `claude -p` 2.1.330, which lists the subagent itself as a `subagent` task and its `sleep` as a `shell` task, both `running`). It answers `block` with a reason asking it to wait for the end notice and then send the final report. It respects `stop_hook_active` and holds the same subagent at most twice. Subagents that run in parallel do not hold each other, and in `claude -p` it does nothing.

## The handoff

1. `relay` (the whole message; on Codex `/relay` is not a command) or `/relay` on Claude Code.
2. The hook tells the model to write the state to a Markdown file of at most 8,000 characters, in your language: your request, state, decisions, where everything is, what does not carry over by itself, numbered next steps, risks. On Claude Code the model writes it itself; on Codex it delegates the write to a subagent that inherits the context.
3. You start the new session: `/clear` in Claude Code, `/new` in Codex. On Claude Code with `/relay`, it does that for you.
4. The `SessionStart` hook of the new session puts the file in its context.

Delivery rules:

- Claude Code after `/clear`: the file named in the marker `_req-<PID>.txt` of this same process (`<PID>` is `CLAUDE_PID`), otherwise the one Codex wrote for the same directory. An empty marker means the switch was canceled and nothing is delivered. Without `CLAUDE_PID`, `/clear` delivers the only `<slug>-<8hex>.md` of the directory under 30 minutes old; with two or more, nothing.
- A new Claude Code window: only a Codex handoff for the same directory.
- Codex: the newest handoff for the same directory, including those written by Claude Code.
- A handoff older than 30 minutes is ignored. Each file is taken once (renamed to `*.usada.md`). If an error happens after a session took a file and before the text is printed, the file is renamed back and the marker is put back.
- The context a session start receives is at most 9,000 characters. The handoff goes in first and is never cut for anything else; the delegation table gets what is left.

File names are `<readable part>-<h8>`, plus `-<first 8 characters of the session id>` on Claude Code. The readable part is the working directory in lowercase with every run of other characters turned into `-`, the last 60 characters. `h8` is the FNV-1a 32-bit hash of the UTF-8 bytes of the directory, so `my_app`, `my-app` and `My App` get different files.

### Permission for the handoff write

On Claude Code, the plugin pre-approves one tool call: the `Write` of the session's own handoff file. All of these must hold: the main session; a valid `CLAUDE_PID` and a `_req-<PID>.txt` marker at most 10 minutes old; the path equals `<folder>/<name in the marker>`, with no `..` and no NTFS alternate stream; the folder is safe and the target is not a link; at most 8,000 characters. It applies in every mode. Your `deny` and `ask` rules still apply. Any other write follows the normal permission flow.

## The switch point

The switch is due when the context reaches:

```
floor + min(D, 0.8 x (C - floor))
```

- `D` is `threshold_tokens` from the config, 150,000 when absent.
- `floor` is the token count of the session's first response. It is measured, not read from a file: it is everything the CLI loaded at the start (system prompt, tool definitions, MCP servers, skills, memory, and files such as CLAUDE.md and AGENTS.md).
- `C` is the CLI's auto-compaction point. Claude Code: `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, else `autoCompactWindow` in settings, else the model's window (1M: 967k; 200K: 200k; `CLAUDE_CODE_DISABLE_1M_CONTEXT` forces 200K); `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` can lower it. Codex: `model_auto_compact_token_limit` in `config.toml`; absent means no ceiling and `D` applies alone.

With a floor of 30k: Claude on a 1M window switches at 180k; Claude on 200K at 166k; Codex with a limit of 120k at 102k. `/relay status` shows the current number and where `C` came from. The `Stop` hook warns; the mod shows the same point in its status line and, with auto on, switches by itself.

## The safe switch

- The switch waits for a subagent that has not reported back. The mod does not start counting while an agent is alive, and the `Stop` warning waits for the turn the report brings. A background shell command does not hold it, since a server may never end.
- The handoff carries what `/clear` does not keep intact. Measured in `claude -p` 2.1.329: `/clear` drops an active `/goal`, keeps scheduled tasks (`CronList`) and keeps background work running, with its notices arriving in the new session. So the file holds the goal's condition word for word, each scheduled task (id, schedule, prompt, so the new session does not create it twice) and each background command or agent still running (id, what it does, output file).
- If the handoff comes back from a failed delivery, the marker comes back with it, so the next `/clear` still gets it.

## Does the switch pay off?

This section is an estimate from our measurements, with the caveats below.

Measured (Claude Code 2.1.328, `claude -p`, 7 runs, haiku and opus): a new session does not start from zero. A prefix of about 70,000 tokens (system prompt, tools, CLAUDE.md, memory) came mostly from cache, but irregularly: between 0 and about 68,000 tokens were written to cache on the first message. The write was 0 tokens in 2 of the 7 runs, about 31,000 in 2 and between 48,000 and 68,000 in the other 3. We did not find out why it varies.

Estimated, on assumed multipliers (cache read 0.1x, cache write 1 hour 2x, output 5x; we did not check them against a price list): with the switch at 150,000 tokens, the cost of the handoff and of opening the new session is paid back in about 10 turns when the cache is warm and about 27 when it is cold. At a 100,000 limit the same estimate gives about 24 to about 70 turns, which is why the default is 150,000 and why we do not recommend a limit under about 100,000. The estimate does not count the other reason to hand over, that very long contexts get worse; we did not measure that.

Hook cost, measured: 50 `PreToolUse` calls through Git Bash on Windows, with `python3` being the Microsoft Store shortcut, took a median of 196 ms each (90th percentile 225 ms). Measuring only the interpreter: 115.6 ms through the shortcut against 25.5 ms with Python from python.org. Other systems were not measured.

## Privacy

- No network calls, in any hook or script.
- The hooks read the transcript (Claude Code) or the rollout (Codex) of the current session, only for token counts, the model id (Claude Code) and, on Codex, `originator` and `source` in the first line. They never print or store the rest.
- The handoff file holds what the model wrote about your work, which may include client or project details. It stays in a folder under your own user profile, never in your repository. On macOS and Linux the plugin keeps the default folder at mode `0700`; a folder you set in `handoff_dir` keeps its permissions. The plugin refuses a folder that is a symlink or belongs to another user.
- Files older than 7 days are deleted when a session starts, only with names the plugin writes: `_req-N.txt`, `_detect-*.flag`, `_trace-<8hex>.md`, `_modo-*.txt`, `_repo-*.flag`, `_alias-*.flag` and `_sub-*.n` in any folder; the handoff `.md` files only in the default folder.
- The mod keeps a small trace file per session in the handoff folder (`_trace-<id8>.md`: events and timing, the last 200 lines, never the handoff text).

## Known limits

- Codex support is untested: the plugin installs and its hook was checked without a model, but the lock, the warning and the handoff have not been seen working in a real Codex session. Codex runs plugin hooks only after you approve them in `/hooks`; unapproved hooks fail silently.
- The lock depends on signals the CLIs do not document (`CLAUDE_CODE_ENTRYPOINT`, `agent_id`, the Codex `originator` and `source`). A CLI update can change them. If the plugin cannot read the signal, the lock is off for that session; if `agent_id` disappears, subagents would be denied: set `SYNC_RELAY_MODE=off` until the plugin is updated.
- Claude Code handoffs in a directory can be read by Codex for 30 minutes.
- The background-task hold cannot tell whose task it is: `background_tasks` is scoped to the whole session, so a shell the main session started also holds a finishing subagent, at most twice. Whether the subagent then really waits for the notice and resumes was not measured in an interactive session.
- A command is checked as text, not run: a program that writes or deletes by itself is as safe as your list. The first word of every pattern is literal and the seed names only read commands, but a command you add (`docker *`) is yours.
- The lock keeps the model on course; it is not a sandbox. A subagent is free to write files, including the mode file (`_modo-*.txt`) and the repository file, and the lock cannot tell. A scheduled prompt (`/loop`, `CronCreate`, `ScheduleWakeup`) reaches `UserPromptSubmit` like a typed one, and the hook input does not say which is which, so `relay off` in a scheduled prompt turns the lock off (the hint on how is shown to you only, never to the model).
- `Read` with a `limit` up to `read_max_lines` reads any file, as a subagent would. Accepted.
- `SubagentStop` can hold a subagent for a task of the main session, at most twice. Accepted.
- A `handoff_dir` that passes the rule but cannot be used (a link or a junction) is not noticed by the mod: the script falls back to the default folder and the two look at different folders. Use a plain folder of your own.
- The mod uses the Claude Code mods API, which is in early access and can change. It sees agents only, not background shell commands; the handoff file carries those.
- Only Windows was tested.
