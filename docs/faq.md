# FAQ

## The hooks are slow on Windows. Why, and how do I fix it?

The hooks call `python3`. On Windows that name is often the Microsoft Store shortcut, which adds start-up time to every call. Measured: a median of 196 ms per `PreToolUse` call with the shortcut, and 115.6 ms against 25.5 ms for the interpreter alone with real Python from python.org. Install Python 3.9 or newer from python.org and make sure `python3` on the PATH resolves to it, not to the shortcut. Check with `python3 --version` and `where python3`. On Windows, Claude Code runs the hooks through Git Bash.

If there is no `python3` at all, the hooks fail on every event with a non-blocking error and the plugin does nothing. The CLI keeps working (the hooks fail open).

## Why is the command `/relay`?

`/relay` is a Claude Code command (part of the plugin's mod), named after the plugin so it does not clash with the commands you already have. On Codex, type the word `relay` as the whole message: it does the same (then `/clear` on Claude Code or `/new` on Codex).

## Does it work on Codex?

The plugin installs on Codex 0.170.0 and its hook was run directly, without a model, and denied a tool as expected. It was not tested in a real Codex session: the lock, the context warning and the handoff have not been seen working there. Codex also skips a plugin hook until you approve it: open the TUI, run `/hooks` and approve the sync_relay hooks. Until then nothing happens, and in `codex exec` the hooks are skipped silently.

## Why `sync-relay` in the install command and `sync_relay` everywhere else?

The manifest name has to be kebab-case for the claude.ai marketplace sync and for `claude plugin validate --strict`, so the plugin and the marketplace are `sync-relay`. The product, the repository, the messages, the button, the `SYNC_RELAY_*` variables, the folders and the script keep `sync_relay`. The one visible difference is the prefix Claude Code draws on the status line: `sync-relay:`.

## How do I turn it off?

- One session, no restart: type `/relay off` (Claude Code with the mod), or the whole message `relay off` (any setup, Codex too). `relay remind` keeps only the reminder, `relay on` brings the lock back. It lasts for that open session only and survives `/clear`.
- One session, from outside: start the CLI with `SYNC_RELAY_MODE=off`.
- For good: `"mode": "off"` (or `"remind"`) in the config file.
- Remove it. Claude Code: `claude plugin uninstall sync-relay@sync-relay`. Codex: `codex plugin remove sync-relay@sync-relay`.

It is one plugin now: a single uninstall removes the hooks and the mod.

## How do I upgrade from 0.1.x?

The product was renamed in 0.2.0 and the two plugins became one: it is not an update, it is a reinstall (steps in [CHANGELOG.md](../CHANGELOG.md), "Upgrading from 0.1.x"). From 0.2.0 to 0.2.1 it is a reinstall too, because the technical name is now `sync-relay` (steps in "Upgrading from 0.2.0"). For 0.1.0, what changed for you is in [CHANGELOG.md](../CHANGELOG.md), section "Upgrading from 0.1.0": `/handoff`, `handoff` and `passagem` stop working (use the word `relay`, or `/relay` on Claude Code), and the old `threshold`, `limiar`, `botao` and `padrao` subcommands are gone (`/relay button` still exists).

## A tool was denied in my main session. Is that a bug?

No. The main session only orchestrates, and the denial text says so. Ask the model to delegate, add the tool to `allowed_tools` if you want it always allowed, or turn the lock off for the session with `/relay off` (or `relay off`).

Harmless commands are let through by a list you control: `read_commands` in the config (a small seed, `git status`, `ls`, `cat` of a small file...), `read_max_kb` and `read_max_lines` for sizes, and `.claude/sync_relay.json` per repository (for example `{"allowed_commands": ["cargo xtask ci", "cargo xtask ci *"]}`). The seed is a starting point, not a rule: adjust it to your context. The fixed rules: the whole command is one simple command with no `|`, `;`, `&`, redirection, backtick, `$`, quote, backslash or glob; the first word of a pattern is literal; `cat`, `head` and `tail` only on an existing regular file within the size limit. Whatever does not fit goes through `/relay off` or `/relay remind`. See [configuration.md](configuration.md#what-the-lock-lets-through).

## Why did my subagent's result never come back?

Claude Code sends every Bash that runs over about 180 s to the background. A subagent that does not wait for the end notice finishes with nothing, and its result is lost. The plugin now tells the main session to wait for the notice and return the final result, and holds a subagent that tries to finish while a background shell or monitor task is running (at most twice, and never a second time in the same stop). Limits: the task list belongs to the whole session, so any running shell holds it, a subagent in `claude -p` is never held, and the plugin cannot make a command finish sooner. For a long job, give it to the subagent with the instruction to wait for the notice.

## Where do my handoffs live, and can I delete them?

In a folder under your user profile ([configuration.md](configuration.md) has the path). You can delete the files; the plugin removes its own old ones after 7 days. Nothing goes to your repository.

## How do I ask something or report a problem?

Open an issue with the form that fits. See [CONTRIBUTING.md](../CONTRIBUTING.md).
