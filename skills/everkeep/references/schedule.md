# The optional scheduled run

Read before creating any schedule or running everkeep headless. Decision D2: no schedule until the live rollout ends; then a weekly run of the selection `routine` (bot PRs and alerts only). Research: [ecosystem APIs, scanners, EOL](../../../ai-docs/research/2026-10-13-ecosystem-apis-scanners-eol.md) section 6.

## Why it is locked down

`claude -p` shows no trust dialog. Started inside a repository, it runs that repository's settings hooks and connects its `.mcp.json` servers without asking. A scheduled run also reads hostile PR text with nobody watching. So a headless run:

- starts in `~/.everkeep`, never inside a repository;
- loads only user settings and disables every hook;
- connects no MCP server;
- has only the tools it needs, with Bash narrowed to keep.py, git and gh;
- has no web tools;
- never asks (`dontAsk`), so anything outside the allow-list is refused rather than prompted.

## The invocation

    claude -p "<prompt: run everkeep on the selection routine, learning mode per the overlay, then write the digest>" \
      --setting-sources user \
      --settings '{"disableAllHooks":true}' \
      --strict-mcp-config \
      --tools "Bash,Read,Grep,Glob,Write" \
      --allowedTools "Bash(python *keep.py*)" "Bash(git *)" "Bash(gh *)" \
      --permission-mode dontAsk

Test the exact command by hand, from `~/.everkeep`, before creating any schedule, and check the flags against the current Claude Code docs first: they change between releases.

## Scheduling it

Windows: a scheduled task that runs the command weekly from `~/.everkeep`, like repo-traffic's task. macOS and Linux: cron or a launchd/systemd timer. Never a cloud schedule for private repos whose CI runs on the user's own machine.

The digest is the output; escalations land on the host's review list, so nothing else needs to notify.

Related: builds on [safety.md](safety.md).
