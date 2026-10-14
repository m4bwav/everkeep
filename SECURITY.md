# Security policy

## Reporting a problem

Open an issue or a pull request and I'll take a look. A pull request with the fix is the quickest route.

You can also report privately: open the repository's **Security** tab and choose **Report a vulnerability**.

This is a one-person project with no bug bounty and no response deadline. I'll reply when I can and say what I plan to do. Good-faith testing on your own copy is welcome.

## Supported versions

Only the latest release on the default branch gets fixes.

## Scope

The skill's instructions and its CLI run on your machine with your agent's permissions and your `gh` login, and the CLI can merge, close, label and comment on pull requests when run with `--apply`. In scope: anything that leads the agent or the CLI to act beyond what the skill says it does. That includes text planted in a pull request, issue, commit or package page that steers the agent (prompt injection), a way to get a merge or close past the guards, a public comment that leaks text from another repository, and running code from a pull request branch. Out of scope: bugs in the agent tool itself (Claude Code, Copilot, Codex, Cursor) or in GitHub; report those to their makers.
