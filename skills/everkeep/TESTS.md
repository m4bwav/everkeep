# Tests: everkeep

Test runs for [SKILL.md](SKILL.md). Cases live in `evals/evals.json`. A failure that taught something is a lesson in [LEARNINGS.md](LEARNINGS.md); a fix it caused is logged in [CHANGELOG.md](CHANGELOG.md) with `because: T-...`; research it triggered is in [RESEARCH.md](RESEARCH.md); counts and the failing list are in `evergreen.json` under `tests`. Rules: MAINTENANCE.md (testing section) and the plugin's `protocol/TESTING.md`.

A test passes on evidence (a tool call in the trace, a file, a marker, a log line), never on the transcript's claim that something was done.

The CLI has its own unit tests in the repository's `tests/` folder (`python -m unittest discover -s tests -t tests`), run in CI on three operating systems and two Python versions. Those prove the rules; the cases here prove the skill drives them.

Entry shape: `### T-YYYYMMDD-n · date · harness · env · passed/total`, then one line per failing case (`id · kind · class · what the evidence showed`), then `led to:` (L-, C-, R- ids or none). Newest first. Budget 150 lines; archive older runs to `TESTS-ARCHIVE.md`.

## Runs

### T-20261013-2 · 2026-10-13 · python unittest · Windows 11, Python 3.10, 3.11, 3.14 · 78/78
- CLI unit tests: URL parsing for every provider, scope and filters, tiers, the classification table with the 2026-10-13 snapshot's diffs, lockfile diffs (npm, NuGet removed target sections, Unity), resume after an interruption, stop-widening, the seam through the fake adapter with gh off PATH, act refusing a moved head, learning mode, caps, sticky verdict comments.
- led to: none

### T-20261013-1 · 2026-10-13 · not yet run · skill · 0/9
- Nine cases written (four triggers, two decoys, two action cases, one outcome case); the skill-level suite runs in Phase 5 after install (`evergreen-test`).
- led to: none
