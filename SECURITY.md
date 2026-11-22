# Security

sync_relay makes no network calls: the hooks and the script read local files and write only to the handoff folder (see "Privacy" in [docs/how-it-works.md](docs/how-it-works.md)).

Report a vulnerability privately through the repository's private vulnerability reporting: [Report a vulnerability](https://github.com/Sync-Labs-team/sync_relay/security/advisories/new) (the Security tab). Please do not open a public issue for it.

In scope: a way around the lock that [docs/how-it-works.md](docs/how-it-works.md) does not list as a known limit, a write outside the handoff folder, a handoff delivered to the wrong session or user, a hook that crashes or blocks a session. Out of scope: turning the lock off on purpose (`SYNC_RELAY_MODE`, config). The lock keeps the model on task; it is not a sandbox. In Code Mode the `REPL` wrapper and `Poll` are allowed and each call inside it is checked by its real tool name; file or process access by the REPL's own JavaScript, without a tool call, is outside the lock (see [docs/how-it-works.md](docs/how-it-works.md)).

Known surface: on Claude Code the plugin answers `PreToolUse` with `permissionDecision: "allow"` for one call, the `Write` of the session's own handoff file. It requires the main session, a valid `CLAUDE_PID`, a `_req-<PID>.txt` marker at most 10 minutes old, a path equal to `<folder>/<name in the marker>` with no `..` and no NTFS alternate stream, a safe folder, a target that is not a link, and at most 8,000 characters of content. It applies in every mode, `off` included. The user's `deny` and `ask` rules still apply. A way to make that pre-approval cover any other write is in scope.

Supported: the latest release.
