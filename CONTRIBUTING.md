# Contributing

sync_relay takes contributions as issues. Pull requests from outside are not accepted: pull request creation is restricted to collaborators of the repository. A good report does more for the project than a patch we could not merge.

## Open an issue

Use the form that fits at [Issues > New issue](https://github.com/Sync-Labs-team/sync_relay/issues/new/choose):

- Bug: something broke or behaved in a way the docs do not explain.
- Feature: something that would make the plugin simpler, faster or more useful.
- Question: how to do something, or why it works the way it does. There is no Discussions tab; questions are issues too.

Search the existing issues first. If one covers it, add what is new as a comment.

## What makes a good issue

- Plugin version (`claude plugin list` or `codex plugin list`) and whether you use Claude Code or Codex.
- CLI and its version (`claude --version`, `codex --version`).
- Operating system. Only Windows has been tested, so reports from macOS and Linux are welcome.
- The steps, as short as you can make them, what you expected and what happened, with the exact output.
- `/relay status` output when the problem is about the switch point or the lock.
- Nothing private: no tokens, secrets, client or project names, machine paths with your user name, or handoff text. Use placeholders such as `alice` and `example.com`.

## Scope

In scope: the lock and the delegation table, the handoff and its delivery, the switch point, the mod (`/relay`, button, status line), the Codex hooks, the docs.

Out of scope: a sandbox (the lock keeps the model on task, it is not a security boundary), network features (the plugin makes no network calls and will not), and support for CLIs other than Claude Code and Codex.

Security problems are not issues: see [SECURITY.md](SECURITY.md).
