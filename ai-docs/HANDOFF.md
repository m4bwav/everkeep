# everkeep handoff

Updated 2026-10-14.

**Where things stand:** Phases 0 to 2 done; Phase 3 dry runs done (this repo, a three-repo selection, all 60 repos). On 2026-10-14 the first single-repo maintain run (IsImageUrlDotNet, every duty, learning mode) posted three verdict comments and found eight fixable problems, all fixed with tests (L-004 to L-008, changelog C-20261014-1). **Waiting for the maintainer** on: the all-repo digest (his state folder, `runs/20261014-030304-ehtv/digest.md`), and whether a new transitive package from the same publisher on a patch bump should keep escalating. Learning mode stays on until he agrees with a run.

**Read first:** [log.md](log.md) (the last three entries), [plans/design.md](plans/design.md) section 13 (rollout), [../skills/everkeep/SKILL.md](../skills/everkeep/SKILL.md), [../skills/everkeep/LEARNINGS.md](../skills/everkeep/LEARNINGS.md). Adding a host: [plans/providers-roadmap.md](plans/providers-roadmap.md).

**Next, in order:**
1. The maintainer's verdict on the digest and on the transitive-package question; fold corrections into `classify.py`, its tests and LEARNINGS.md.
2. Another single-repo run on a different kind of repo (an npm package or a plugin), the same way: every duty, read `<plan>.comments.md` before `--apply --learn`. Each run so far found parser or detection bugs the all-repo run hid.
3. The learning-mode shakedown (D13): `keep.py prs --all --plan plan.json`, read `plan.comments.md`, then `keep.py act plan.json --apply --learn`.
4. Phase 4: apply on this repo, then `--select low-risk`, then all, once he agrees. High-tier repos always escalate. The NuGet lockfile fix (`nuget-lock-targets`) is verified and ready to push on IsImageUrlDotNet#17, CachingServiceWithAOPSupport#12 and (high tier, push but never merge) DotNetRandomNameGenerator#24.
5. Phase 5: the eval suite (9 cases, `evergreen-test`), a wiki (wikiwright), the first release (tag and release need his go-ahead).

**Watch out for:**
- `keep.py` package: 3,997 lines against a 4,000-line green budget. Trim before adding anything (`duties.research`, `github.merge`'s fallback, `prs.show`).
- Installed size yellow (597 KB) because the research notes ship with the plugin; his call.
- Inventory is cached per repo by `pushed_at` and `inventory.v`; bump `v` in `scope.describe` when detection changes.
- After editing the source, reinstall (`claude plugin uninstall everkeep@mark-local`, then install): the same version does not refresh the cached copy.
- The session prompt `ai-docs/next-session-prompt.md` is gitignored (local paths); a copy sits in the private sidecar.
- Never `cd` in a shell call; Bash heredocs collapse `\\n` to a real newline inside Python strings (use the Edit tool for those); the Write tool keeps `\u` escapes in Python source intact.
- A shared clone's master may be behind origin: fast-forward it (when clean and on master) before vulns or deps, or the scanners read a stale tree.
