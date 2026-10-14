# Learnings: everkeep

Procedural lessons for [SKILL.md](SKILL.md). Research findings live in [RESEARCH.md](RESEARCH.md); every change is logged in [CHANGELOG.md](CHANGELOG.md); test runs in [TESTS.md](TESTS.md); state in `evergreen.json`. Format and write-time gate: MAINTENANCE.md (LEARNINGS-FORMAT). Retired entries go to LEARNINGS-ARCHIVE.md with a reason.

Write an entry the moment a real signal happens: a user correction, the same error twice, a discovered workaround, an environment fact, a stated preference, a failed test or a failure in use. Check existing entries first, by meaning (`evergreen.py search "<the lesson>" --kinds learnings` finds near-duplicates in every registered unit): add / update / retire / none. Trigger and Hypothesis are required. Promote after three confirmations; retire when harmful > helpful.

## Active

### L-001 · 2026-10-13 · `dependabot-trailing-full-stop`: Dependabot's "Bumps [x] from A to B." ends with a full stop
- Trigger: first live run; actions/upload-artifact parsed as version "7.0.2." and the release lookup failed, so two clean pin bumps escalated as "not found on its registry".
- Hypothesis: the body sentence ends with a period that the version character class accepts.
- Rule: strip trailing full stops from parsed versions (`classify.parse_bot`); test `test_parse_strips_trailing_full_stop_and_maps_dotnet_sdk`.
- Evidence: live `keep.py prs` on CachingServiceWithAOPSupport, 2026-10-13
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-13

### L-002 · 2026-10-13 · `package-name-is-not-ownership`: a package name in a repo's files proves nothing until the registry says the user owns it
- Trigger: resolving the whole account: a private game repo's package.json named `phaser-project-template`, a name unpublished on npm since 2021 by someone else; an F# library (`.fsproj`) was missed; template and fixture folders read as ecosystems.
- Hypothesis: repos copy templates, keep tooling package.json files and hold fixtures; only the registry knows what is published and by whom.
- Rule: candidates from files are kept only when the registry has them (npm: has versions; NuGet: search owners) and, with `registry_accounts` set, one of the user's accounts owns them; skip templates/fixtures/evals/examples/tests/docs folders.
- Evidence: `keep.py scope resolve --all` on the live account; tests `test_registry_ownership`, `test_package_filter_means_publishes_there`
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-13

### L-003 · 2026-10-13 · `npm-audit-dev-only`: npm audit findings are usually dev tooling; say how many ship
- Trigger: the three-repo dry run reported "npm audit 10" on an npm package; all ten were in the linter's dependency chain.
- Hypothesis: modern packages have zero runtime dependencies; audit counts dev dependencies too.
- Rule: run `npm audit --omit=dev` as well and report shipped versus dev-only; flag a local clone that is behind origin, since its lockfile may be stale.
- Evidence: `keep.py vulns --repo replace-string-at-position`, 2026-10-13
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-13

<!-- Example (delete once you have a real entry):
### L-001 · 2026-10-13 · One-line lesson in plain words
- Trigger: what happened, with dates or counts
- Hypothesis: why
- Rule: the shortest instruction that prevents the trigger
- Evidence: C-20261013-1, T-20261013-1, confirmed 2026-10-13
- Scope: skill | repo:<slug> | env:<name> | global
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-13
-->
