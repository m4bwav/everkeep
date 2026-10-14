# Changelog: everkeep

Every change to [SKILL.md](SKILL.md) and its companions, newest first, each with the reason. Reasons cite findings in [RESEARCH.md](RESEARCH.md) (`R-`), lessons in [LEARNINGS.md](LEARNINGS.md) (`L-`), and test runs in [TESTS.md](TESTS.md) (`T-`). State in `evergreen.json`. Protocol: MAINTENANCE.md.

Entry shape: `### C-YYYYMMDD-n · date · one-line summary`, then `because:` (IDs or "user request"), `files:` (file and section), and a sentence on what changed. Cite section headings, not line numbers.

### C-20261014-1 · 2026-10-14 · Fixes from the first single-repo maintain run (IsImageUrlDotNet)
- because: L-004 `nuget-group-body-says-updated`, L-005 `nuget-lock-targets-fix-verified`, L-006 `deps-respect-the-repos-own-holds`, L-007 `read-comments-before-posting`, L-008 `fsproj-is-a-package-project`
- files: SKILL.md (Step 2), references/prs.md (Fixing a failing bot PR), scripts/everkeep/classify.py, verdict.py, act.py, cli.py, prs.py, report.py, util.py, duties.py, gaps.py, scope.py, providers/github.py
- NuGet group bodies parse; fix items carry a known recipe and the class after the fix, and the comment says both; the act dry run writes every comment it would post; repeated lockfile reasons collapse; deps skips unlisted versions and lists the repo's own holds apart; the icon gap reads F# projects; bare repo names work everywhere. github.py's write wrappers share one `_write` helper to stay under the 4,000-line budget.

### C-20261013-2 · 2026-10-13 · `keep.py enable` for the D11 settings
- because: user request (decision D11); the gaps table named the fix but no command applied it, found while setting up this repository
- files: SKILL.md (Step 3 table), references/gaps.md (Fixing), scripts/everkeep/cli.py
- `enable` switches on only the settings D11 allows, reads the current state first, and refuses anything else.

### C-20261013-1 · 2026-10-13 · Created as an evergreen unit
- because: user request
- files: SKILL.md, RESEARCH.md, LEARNINGS.md, evergreen.json (skills: also TESTS.md and evals/evals.json)
- Initial version. Tier `fast`, interval 14d. See R-20261013-1 for the research basis; the first test run, for a skill, is logged in TESTS.md.
