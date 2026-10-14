# everkeep handoff

Updated 2026-10-14 (evening).

**Where things stand:** Phases 0 to 3 done; learning mode is OFF since 2026-10-14 and Phase 4 (apply) has begun. 2026-10-14: D14 built (PR #5: a new transitive package escalates only with a danger signal); the last learning-only run (seeded-random-utilities) found four misreads, fixed in PR #6; both merged. IsImageUrlDotNet#17 got the verified lockfile fix pushed to Dependabot's branch and is green; #15, #16 and #17 are all merge candidates, not yet merged, waiting for the maintainer to see the first Phase 4 result.

**Read first:** [log.md](log.md) (the last two entries), [plans/design.md](plans/design.md) sections 12 (D14) and 13 (rollout), [../skills/everkeep/SKILL.md](../skills/everkeep/SKILL.md), [../skills/everkeep/LEARNINGS.md](../skills/everkeep/LEARNINGS.md) (L-009 to L-011 are new).

**Next, in order:**
1. When the maintainer agrees: `keep.py prs --repo IsImageUrlDotNet --plan P` then `act P --apply` (merges #15, #16, #17), then `--select low-risk`, then all. CachingServiceWithAOPSupport#12 and DotNetRandomNameGenerator#24 take the same lockfile fix (high tier: push, never merge).
2. Phase 5: finish the eval suite (see TESTS.md for what ran), a wiki (wikiwright), the first release (tag and release need his go-ahead).
3. Ask him once: `mailto` for ecosyste.ms in the overlay; the installed size is yellow (research notes ship with the plugin); the `keep.py` package is now yellow too (4,089 lines against 4,000: trim more, or move the line).

**Watch out for:**
- `keep.py` package: 4,089 lines, past the 4,000-line green line (yellow). Dead code is gone; what is left to trim is `duties.research`, `github.merge`'s fallback (a safety net for Phase 4 merges; keep it) and `prs.show`.
- Installed size yellow (597 KB) because the research notes ship with the plugin; his call.
- Inventory is cached per repo by `pushed_at` and `inventory.v`; bump `v` in `scope.describe` when detection changes.
- After editing the source, reinstall (`claude plugin uninstall everkeep@mark-local`, then install): the same version does not refresh the cached copy.
- The session prompt `ai-docs/next-session-prompt.md` is gitignored (local paths); a copy sits in the private sidecar.
- Never `cd` in a shell call; Bash heredocs collapse `\\n` to a real newline inside Python strings (use the Edit tool for those); the Write tool keeps `\u` escapes in Python source intact.
- A shared clone's master may be behind origin: fast-forward it (when clean and on master) before vulns or deps, or the scanners read a stale tree.
