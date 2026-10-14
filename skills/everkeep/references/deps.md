# Dependencies, toolchains and vulnerabilities

Read when `KEEP deps` or `KEEP vulns` has output to act on. Sources: [ecosystem APIs, scanners, EOL](../../../ai-docs/research/2026-10-13-ecosystem-apis-scanners-eol.md), [verification and recent changes](../../../ai-docs/research/2026-10-13-verification-and-recent-changes.md) (2026-10-13).

## Vulnerabilities

`KEEP vulns` reads the host's alerts (Dependabot, code scanning, secret scanning) and runs the neutral scanners on the local clone (or a throwaway one with `--clone`):

| Tool | Command | Exit codes |
|---|---|---|
| osv-scanner 2.x | `osv-scanner scan source -r --format json DIR` | 0 clean, 1 findings, 128 nothing to scan (not a failure) |
| npm | `npm audit --json`, `npm audit signatures` | 1 means findings |
| .NET | `dotnet package list --vulnerable --include-transitive --format json` | exits 0 with findings: parse the JSON |
| pip-audit | `pip-audit -f json` | top level `{"dependencies", "fixes"}` |

A missing scanner is reported with its install line (`winget install Google.OSVScanner`); pass it on. Never install a tool without the user's yes.

What to do with a finding:
- A patch or minor fix in a direct dependency: the same rules as a bot PR. Usually Dependabot's security update already opened one; if not, open an everkeep PR on a branch `everkeep/fix-<id>`, at most two open everkeep PRs per repo.
- A major, a transitive-only fix, or a dev-only tool: escalate with the advisory and whether shipped code is affected.
- Secret scanning alerts: escalate at once; the secret must be revoked at its provider whatever happens to the repo.
- Code scanning alerts: escalate unless the fix is trivial and in a low-tier repo.
- Switch on Dependabot alerts and security updates where off (allowed without asking, D11).

A withdrawn Dependabot alert answers 410 Gone (since 2026-10-13): it is withdrawn, not an error.

## Dependencies

`KEEP deps` lists outdated direct dependencies with the latest version's publish time from the registry (npm `time`, NuGet registration `published`, PyPI `upload_time`). Straightforward means: patch or minor, past the cooldown, the project's CI green, the lockfile diff clean. Those can become an everkeep PR that merges under the rules. Majors and anything breaking escalate as an issue or a draft PR with the evidence (changelog, breaking changes, what the repo uses).

Prefer letting the configured bot do it: a repo with Dependabot or Renovate configured gets the bump from the bot; everkeep's job there is the cooldown and groups in the bot's config (gaps), not a second PR.

## Toolchain floors (2026-10-13)

| Toolchain | Floor | Dates |
|---|---|---|
| Node | 22, 24, 26 | 20 is end of life; 24 enters maintenance 2026-10-20; 26 becomes LTS 2026-10-28 |
| .NET | 10 | 8 and 9 end 2026-11-10 |
| Unity | 6.3 LTS | 6.0 LTS ends October 2026 |
| GitHub Actions | node24 actions | node20 actions stopped running 2026-09-23 |

endoflife.date API v1 (`https://endoflife.date/api/v1/products/<product>/`) has current cycles; check it before quoting a date older than a month.

Related: builds on [prs.md](prs.md); see also [gaps.md](gaps.md).
