# everkeep handoff

Updated 2026-10-14.

**Where things stand:** Phases 0 to 3 done. 2026-10-14: the first single-repo maintain run (IsImageUrlDotNet, learning mode) found eight bugs, fixed in PR #3 (merged). The maintainer then ruled: one more learning-only run (seeded-random-utilities), after which learning mode goes off; and new transitive packages escalate only with a danger signal (D14, not built yet).

**Read first:** [log.md](log.md) (the last four entries), [plans/design.md](plans/design.md) sections 12 (D14) and 13 (rollout), [../skills/everkeep/SKILL.md](../skills/everkeep/SKILL.md), [../skills/everkeep/LEARNINGS.md](../skills/everkeep/LEARNINGS.md).

**Next, in order:**
1. Build D14 in `classify.py` with tests (trim first: the package is at 3,997 of 4,000 lines), PR, merge after green checks.
2. The last learning-only run: seeded-random-utilities, every duty, read `<plan>.comments.md` before `act --apply --learn`; fix what it finds the same way.
3. Set `"learn": false` in the overlay, then Phase 4: apply on this repo, then `--select low-risk`, then all. The verified NuGet lockfile fix goes on IsImageUrlDotNet#17, CachingServiceWithAOPSupport#12 and DotNetRandomNameGenerator#24 (high tier: push, never merge).
4. Phase 5: the eval suite (9 cases, `evergreen-test`), a wiki (wikiwright), the first release (tag and release need his go-ahead).

**Watch out for:**
- `keep.py` package: 3,997 lines against a 4,000-line green budget. Trim before adding anything (`duties.research`, `github.merge`'s fallback, `prs.show`).
- Installed size yellow (597 KB) because the research notes ship with the plugin; his call.
- Inventory is cached per repo by `pushed_at` and `inventory.v`; bump `v` in `scope.describe` when detection changes.
- After editing the source, reinstall (`claude plugin uninstall everkeep@mark-local`, then install): the same version does not refresh the cached copy.
- The session prompt `ai-docs/next-session-prompt.md` is gitignored (local paths); a copy sits in the private sidecar.
- Never `cd` in a shell call; Bash heredocs collapse `\\n` to a real newline inside Python strings (use the Edit tool for those); the Write tool keeps `\u` escapes in Python source intact.
- A shared clone's master may be behind origin: fast-forward it (when clean and on master) before vulns or deps, or the scanners read a stale tree.
