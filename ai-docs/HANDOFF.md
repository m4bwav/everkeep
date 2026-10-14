# everkeep handoff

Updated 2026-10-13.

**Where things stand:** Phases 0 to 2 done; public repository m4bwav/everkeep live (CI green, PRs #1 and #2 merged); installed as `everkeep@mark-local`. Phase 3 dry runs done up to the stop point: this repo, a three-repo selection, and all 60 repos (interrupted once and resumed); 19 of 19 PR classifications match the live snapshot, five checked by hand. **Waiting for the maintainer** to read the all-repo digest (in his state folder, `runs/20261014-030304-ehtv/digest.md`) and say whether the calls look right. Learning mode stays on until he agrees.

**Read first:** [log.md](log.md) (the last two entries), [plans/design.md](plans/design.md) section 13 (rollout), [../skills/everkeep/SKILL.md](../skills/everkeep/SKILL.md). Adding a host: [plans/providers-roadmap.md](plans/providers-roadmap.md).

**Next, in order:**
1. The maintainer's verdict on the digest; fold corrections into `classify.py`, its tests and the skill's LEARNINGS.md.
2. The learning-mode shakedown (D13): `keep.py prs --all --plan plan.json`, then `keep.py act plan.json --apply --learn`. That posts one verdict comment per open PR and does nothing else. Then he reads the comments.
3. Phase 4: apply on this repo, then `--select low-risk`, then all, once he agrees. High-tier repos always escalate.
4. Phase 5: run the skill's eval suite (9 cases, `evergreen-test`; action and outcome cases use the fake account), a wiki (wikiwright), and the first release (tag and release need his go-ahead).

**Watch out for:**
- `keep.py` package: 3,937 lines against a 4,000-line green budget. Trim before adding anything (candidates: `github.py`'s repetitive write wrappers, `duties.research`).
- Installed size yellow (579 KB) because the research notes ship with the plugin; his call.
- Inventory is cached per repo by `pushed_at` and `inventory.v`; bump `v` in `scope.describe` when detection changes.
- After editing the source, reinstall (`claude plugin uninstall everkeep@mark-local`, then install): the same version does not refresh the cached copy.
- The session prompt `ai-docs/next-session-prompt.md` is gitignored (local paths); a copy sits in the private sidecar.
- Never `cd` in a shell call; Bash heredocs collapse backslashes (use `chr(92)`); the Write tool keeps `\u` escapes in Python source intact (checked).
