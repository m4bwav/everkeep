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

### L-004 · 2026-10-14 · `nuget-group-body-says-updated`: Dependabot's NuGet group PRs say "Updated [x](url) from A to B."
- Trigger: single-repo run on IsImageUrlDotNet: the after-fix outlook for #17 listed "could not read which versions this bot PR changes"; the parser knew "Updates `x`" (npm groups) and "Bumps [x]" but not NuGet's "Updated [x]", so no release was looked up and the cooldown was never checked for NuGet group PRs.
- Hypothesis: each Dependabot ecosystem words its body differently; the all-repo run never showed it because the `fix` row wins before the update list matters.
- Rule: parse "Updated [x](url) from A to B" too (`classify._UPDATES`); test `test_parse_nuget_group_body_says_updated`. When adding an ecosystem, read one real PR body for it first.
- Evidence: `keep.py prs show IsImageUrlDotNet#17`, 2026-10-14
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-14

### L-005 · 2026-10-14 · `nuget-lock-targets-fix-verified`: the dropped-sections fix works, and the PR still escalates afterwards
- Trigger: IsImageUrlDotNet#17 (NUnit3TestAdapter 6.3.0 to 6.3.1) failed restore with NU1004 on all three OSes. In a throwaway worktree on Windows, `dotnet restore --force-evaluate` put the net48 and win-x86 sections back in all three test lockfiles; `dotnet restore --locked-mode`, the build and every test (net10.0 and net48) passed. The same patch bump also adds Microsoft.TestPlatform.AdapterUtilities and moves Microsoft.Testing.Platform 2.3.3 to 2.4.1, so the PR stays `escalate` once fixed.
- Hypothesis: Dependabot's NuGet updater restores on Linux, where the win-x86 runtime sections cannot resolve; the new transitive package is real, not an artefact of the dropped sections.
- Rule: a `fix` item now carries `fix_recipe` and `after_fix` (`classify.FIX_RECIPES`, `fix_recipe`); the verdict comment names the fix and says up front whether it will still go to the maintainer. NU1004's text lists the two framework sets the wrong way round ("Lock file target frameworks: net10.0,net48. Project target frameworks net10.0" for a lockfile that lost net48); trust the diff, not the wording. `dotnet restore` on Windows writes CRLF lockfiles; Git's text=auto normalises them, so the src lockfile showing as modified with no diff is harmless.
- Evidence: `gh run view 38321815538 --log-failed`; local restore, build and tests, 2026-10-14; test `test_nuget_lockfile_fix_names_the_recipe_and_the_class_after_it`
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-14

### L-006 · 2026-10-14 · `deps-respect-the-repos-own-holds`: unlisted versions, dependabot ignores and exact pins are not bump candidates
- Trigger: `keep.py deps` on IsImageUrlDotNet called FSharp.Core 6.0.7 to 11.0.100 a major bump "published 1900-01-01": 11.0.100 is unlisted on nuget.org (the flat container lists unlisted versions; nuget.org dates them 1900-01-01), and the repo ignores FSharp.Core in dependabot.yml on purpose (the package's declared floor). The golden test's exact pins (`[1.0.2]`, the last published 1.x) read as bumps of unknown size; `$(TargetFramework)` read as a target framework.
- Hypothesis: maintainers record deliberate holds in dependabot.yml and in exact-version brackets; a tool that ignores them nags about decisions already made.
- Rule: skip unlisted NuGet versions; list dependabot `ignore` entries and `[x.y.z]` pins under "Held by the repo's own choice", never as outdated; skip MSBuild property values. Test `test_unlisted_nuget_version_is_never_latest`.
- Evidence: `keep.py deps --repo IsImageUrlDotNet` before and after, 2026-10-14
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-14

### L-007 · 2026-10-14 · `read-comments-before-posting`: read the dry run's comment text before --apply
- Trigger: the act dry run showed only "would verdict: create verdict comment"; reading the bodies before posting caught the false "could not read which versions" reason (L-004) and the same lockfile finding repeated three times.
- Hypothesis: public text is the one output nobody reviews after the fact.
- Rule: `act` without `--apply` writes `<plan>.comments.md` with every body word for word; read it before `--apply`. Reasons repeated across lockfiles collapse to one line with a file count (`util.collapse_reasons`), in comments, tables and the digest.
- Evidence: IsImageUrlDotNet run, 2026-10-14
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-14

### L-008 · 2026-10-14 · `fsproj-is-a-package-project`: F# projects pack too
- Trigger: gaps reported "icon: gap" on IsImageUrlDotNet, whose `.fsproj` sets PackageIcon; only `.csproj` and Directory.Build.props were read. Same blind spot as L-002's missed F# library.
- Hypothesis: C#-first assumptions leak into every .NET check.
- Rule: any .NET check reads `.csproj`, `.fsproj` and `.vbproj`, `src/` first. Also: `prs show` and `state` take a bare repo name like `--repo` does (`scope.repo_id`).
- Evidence: `keep.py gaps --repo IsImageUrlDotNet`, 2026-10-14
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-14

<!-- Example (delete once you have a real entry):
### L-001 · 2026-10-13 · One-line lesson in plain words
- Trigger: what happened, with dates or counts
- Hypothesis: why
- Rule: the shortest instruction that prevents the trigger
- Evidence: C-20261013-1, T-20261013-1, confirmed 2026-10-13
- Scope: skill | repo:<slug> | env:<name> | global
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-13
-->
