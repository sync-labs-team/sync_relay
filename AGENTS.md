# sync_relay: notes for coding agents

If you are a coding agent (Claude Code, Codex or any other) working in this repository or using sync_relay on someone's machine, you can help it get better by reporting what you see.

## Report through issues

Repository: https://github.com/Sync-Labs-team/sync_relay

- **Bugs.** When sync_relay misbehaves (a tool denied that should pass, a handoff not delivered or delivered to the wrong session, a wrong switch point, a hook that fails), draft an issue with what you ran, what you expected, what happened (the exact output), the plugin version, the CLI and its version, the operating system, and the shortest steps that reproduce it.
- **Ideas.** When something could be simpler or more useful, draft an issue with the situation, what would have helped and why.
- **Do not open pull requests.** Outside pull requests are not accepted; use an issue. See CONTRIBUTING.md.

## Before you publish

Issues are public and go out under the user's GitHub account.

1. Search the existing issues first (`gh issue list --repo Sync-Labs-team/sync_relay --state all --search "<terms>"`). If one covers it, add what is new as a comment.
2. Remove secrets, tokens, private paths, client names, project data and handoff text from everything you paste. Use neutral placeholders (`alice`, `example.com`).
3. Show the user the draft and open the issue only after the user approves.
4. Security problems go through the private advisory in SECURITY.md, never a public issue.
