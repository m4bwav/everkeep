# Changelog

Plugin versions. Reasoned changes to the skill are in `skills/everkeep/CHANGELOG.md`.

## Unreleased

## 0.1.0

First version.

- One evergreen skill, `everkeep`: scope (one repo by default, a saved selection, a filter, or the whole account), pull request triage, vulnerabilities, dependencies and toolchains, modernization gaps, knowledge bases, ecosystem research facts, and one digest per run.
- `keep.py`, a standard-library Python CLI: `providers`, `scope`, `inventory`, `prs` (with `show` and a draft plan), `deps`, `vulns`, `gaps`, `kb`, `research gather`, `act` (dry run unless `--apply`; learning mode with `--learn`), `run start/resume/status`, `report`, `state`.
- Classification from facts: checks on the head SHA, registry publish time and publisher, lockfile diffs (new packages, git or tarball sources, install scripts, removed target sections), first-party action pin bumps, executed config, negative signals for human PRs.
- GitHub adapter through `gh`, with the async merge guarded by the reviewed head SHA, spaced and capped writes; a fake adapter for tests; other hosts answer "not supported yet" with exit code 3.
- Sticky verdict comments from templates; resumable multi-repo runs that stop widening on an unexpected finding.
