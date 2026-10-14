# Tests: everkeep

Test runs for [SKILL.md](SKILL.md). Cases live in `evals/evals.json`. A failure that taught something is a lesson in [LEARNINGS.md](LEARNINGS.md); a fix it caused is logged in [CHANGELOG.md](CHANGELOG.md) with `because: T-...`; research it triggered is in [RESEARCH.md](RESEARCH.md); counts and the failing list are in `evergreen.json` under `tests`. Rules: MAINTENANCE.md (testing section) and the plugin's `protocol/TESTING.md`.

A test passes on evidence (a tool call in the trace, a file, a marker, a log line), never on the transcript's claim that something was done.

The CLI has its own unit tests in the repository's `tests/` folder (`python -m unittest discover -s tests -t tests`), run in CI on three operating systems and two Python versions. Those prove the rules; the cases here prove the skill drives them.

Entry shape: `### T-YYYYMMDD-n · date · harness · env · passed/total`, then one line per failing case (`id · kind · class · what the evidence showed`), then `led to:` (L-, C-, R- ids or none). Newest first. Budget 150 lines; archive older runs to `TESTS-ARCHIVE.md`.

## Runs

### T-20261014-1 · 2026-10-14 · claude plugin eval 2.1.281 (trigger, decoy) + evergreen-tester agent (action, outcome) · Windows 11 · 9/9
- Trigger 4/4: each fired 3 of 3 with the plugin, 0 of 3 in the no-plugin arm. The harness graded only the Skill call, not the scope sub-expectations; the action runs show the scope chosen. Decoy 2/2: no Skill call in 6 of 6 runs.
- action-1 3/3: `keep.py prs --repo owner/nuget-lib` in every run, no `act --apply`, replies name #10 merge, #12 fix, #13 maintainer. action-2 3/3: `keep.py scope resolve` exited 3 with "isn't supported yet" and the issue link, nothing sent to the host. outcome-1 3/3: npm-lib#9 and nuget-lib#10 named as merges, #12 and #13 not, digest.md written under the run's EVERKEEP_HOME, no `--apply`.
- Baselines (no skill): action-2 differs (no unsupported-host answer, no link): the skill is needed. outcome-1 differs (held nuget-lib#10 under a literal reading of the release-workflow rule). action-1 matched the expected calls by reading the fixture JSON directly. The action-1 and outcome-1 baseline prompts carried the expected answer by mistake, so they overstate the no-skill arm; rerun both without it before `worth` uses them.
- Action and outcome cases ran as tester subagents with EVERKEEP_FAKE_PROVIDER, EVERKEEP_NOW and a per-run EVERKEEP_HOME and empty overlay. `plugin eval` cannot run them on native Windows (Bash needs a WSL2 sandbox) and refuses an eval dir under skills/: export with `evergreen.py eval-export`, copy `skills/everkeep/evals/cases` to a top-level `evals/cases` for the run, and delete both copies after (they are regenerated from evals.json).
- Untested elsewhere (no second platform reached for the skill run; the CLI's own suite runs on Linux and macOS in CI).
- Found while running, fixed (L-012 `public-text-the-model-shapes`): the act dry run's comments preview left out close comments; an escalation the model chose showed only the rules' merge reasons.
- led to: L-012, C-20261014-4

### T-20261013-2 · 2026-10-13 · python unittest · Windows 11, Python 3.10, 3.11, 3.14 · 78/78
- CLI unit tests: URL parsing for every provider, scope and filters, tiers, the classification table with the 2026-10-13 snapshot's diffs, lockfile diffs (npm, NuGet removed target sections, Unity), resume after an interruption, stop-widening, the seam through the fake adapter with gh off PATH, act refusing a moved head, learning mode, caps, sticky verdict comments.
- led to: none

### T-20261013-1 · 2026-10-13 · not yet run · skill · 0/9
- Nine cases written (four triggers, two decoys, two action cases, one outcome case); the skill-level suite runs in Phase 5 after install (`evergreen-test`).
- led to: none
