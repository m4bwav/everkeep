# everkeep handoff

Updated 2026-10-13.

**Where things stand:** Phases 0 and 1 done; Phase 2 (build) done: the CLI, 80 unit tests, the skill, CI, banner and icon, the maintainer's private overlay, installed locally. Public repository being created. Phase 3 (dry runs, widening the scope) is next. The skill's eval suite (9 cases in `skills/everkeep/evals/evals.json`) has not been run yet.

**Read first:** [plans/design.md](plans/design.md) (section 6 for the rules, 12 for the decisions), [../skills/everkeep/SKILL.md](../skills/everkeep/SKILL.md), [log.md](log.md) for what this session found on real data. Adding a host: [../skills/everkeep/references/providers.md](../skills/everkeep/references/providers.md) and [plans/providers-roadmap.md](plans/providers-roadmap.md).

**Next:**
1. Phase 3 dry runs, no `--apply`: this repo; then the selection replace-string-at-position, CachingServiceWithAOPSupport, readwright; then `run start --all`, interrupted once (`EVERKEEP_INTERRUPT_AFTER=N` or Ctrl+C) and resumed; 10 classifications checked by hand; stop and show the maintainer the all-repo digest (`keep.py report <run>`).
2. Phase 5 eval suite (`evergreen-test`), with the fake account for the action and outcome cases.

**Watch out for:**
- The session prompt `ai-docs/next-session-prompt.md` is gitignored (it holds local paths); it stays on the maintainer's machine with a copy in the private sidecar.
- `keep.py` package is at about 3,900 lines against a 4,000-line green budget: split or trim before adding duties.
- Installed size is yellow (569 KB, line 400 KB) because the research notes ship with the plugin; the maintainer decides whether to move them.
- Inventory caches per repo by `pushed_at` (`inventory.v` in the state file); bump the version in `scope.describe` when detection changes.
- Never `cd` in a shell call; write files with the editor tools; Bash heredocs collapse backslashes (use `chr(92)`).
