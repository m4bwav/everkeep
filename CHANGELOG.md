# Changelog

Plugin versions. Reasoned changes to the skill are in `skills/everkeep/CHANGELOG.md`.

## Unreleased

- A lockfile adding a package no longer escalates on its own (decision D14): it escalates only when the new package shares no owner with the packages the same update moves, was first published under 90 days ago, is missing from its registry, has a name one edit from a popular or bumped package, or is a known-compromised version. Otherwise the verdict comment names it as a reason.
- `deps` holds only the update types a dependabot.yml ignore names (majors only, say), not the whole package.
- `gaps` recognises staged npm publishing (`npm stage publish`) and a size budget enforced by a tarball or size script.
- `vulns` shows each Dependabot alert's scope (runtime or development).
- Removed the unused provider methods `open_pr` and `rate_state`.
- `keep.py enable`: switch on the security settings the maintainer allows without asking (D11), dry run unless `--apply`.
- `act` without `--apply` writes the comments it would post, word for word, beside the plan (`<plan>.comments.md`).
- A failing bot PR with a known fix says so: the fix, and whether the PR will merge or still go to the maintainer afterwards (`prs show`, the verdict comment, the digest).
- Fixed: Dependabot's NuGet group PRs ("Updated [x] from A to B") were read as having no versions, so their cooldown was never checked.
- Fixed: `deps` no longer offers unlisted NuGet versions, and lists packages the repo holds on purpose (ignored in dependabot.yml, exact `[x.y.z]` pins) apart from bump candidates.
- Fixed: the icon gap now reads F# and VB projects; `prs show` and `state` accept a bare repo name; the same lockfile finding in several files is one line.

## 0.1.0

First version.

- One evergreen skill, `everkeep`: scope (one repo by default, a saved selection, a filter, or the whole account), pull request triage, vulnerabilities, dependencies and toolchains, modernization gaps, knowledge bases, ecosystem research facts, and one digest per run.
- `keep.py`, a standard-library Python CLI: `providers`, `scope`, `inventory`, `prs` (with `show` and a draft plan), `deps`, `vulns`, `gaps`, `kb`, `research gather`, `act` (dry run unless `--apply`; learning mode with `--learn`), `run start/resume/status`, `report`, `state`.
- Classification from facts: checks on the head SHA, registry publish time and publisher, lockfile diffs (new packages, git or tarball sources, install scripts, removed target sections), first-party action pin bumps, executed config, negative signals for human PRs.
- GitHub adapter through `gh`, with the async merge guarded by the reviewed head SHA, spaced and capped writes; a fake adapter for tests; other hosts answer "not supported yet" with exit code 3.
- Sticky verdict comments from templates; resumable multi-repo runs that stop widening on an unexpected finding.
