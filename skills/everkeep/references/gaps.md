# Modernization gaps and the settings everkeep may change

Read when `KEEP gaps` shows gaps to fix. Design: [design.md](../../../ai-docs/plans/design.md) section 9, decision D11.

## What the table checks

SECURITY.md (tiered template), README banner, topics (5 or more), icon (plugins and NuGet packages), a dependency bot with a cooldown, actions pinned by SHA, a read-only workflow token, Dependabot alerts and security updates, secret scanning and push protection, private vulnerability reporting, CodeQL default setup and the open-PR cap (public repos), a ruleset, trusted publishing, a wiki (public packages), a size-budget gate, a golden recording and gated release (packages), AGENTS.md with CLAUDE.md starting `@AGENTS.md`, and CONTRIBUTING.md with an AI-contribution policy (closing comments need a written rule to cite).

Statuses: `ok`, `gap`, `unknown` (the host would not say), `n/a`. Report `unknown` as unknown, never as ok.

## Fixing

| Fix column | What to do |
|---|---|
| cheap | apply in one everkeep PR per repo on branch `everkeep/gaps`, under the same rules as any other PR (it touches workflows or config, so it escalates unless the repo is low tier and only docs and templates changed). Templates: package-modernize's `templates/security/`, its `scripts/topics.py suggest OWNER/REPO`, `scripts/make-icon.py` |
| switch on (D11) | `KEEP enable all <scope>` (dry run, then `--apply`; it refuses anything else), allowed without asking: Dependabot alerts and security updates, secret scanning and push protection, private vulnerability reporting, CodeQL default setup on public repos, the open-PR cap for users without write access |
| ask first (D11) | rulesets, immutable releases, Actions policy, anything that switches a protection off: ask the user |
| banner | an image-generation skill (ComfyUI or similar) when one is available (1536x640, `.github/images/banner.jpg`); otherwise it stays a gap |
| discussions | public repos: `gh repo edit OWNER/REPO --enable-discussions`, allowed without asking (the maintainer asked for it on 2026-10-24); read back `hasDiscussionsEnabled` through `gh api graphql`. Not yet a row in the table: check it by hand when maintaining a public repo |
| social preview | public repos with a banner: crop the centre 1280x640 of the banner to `.github/images/social-preview.jpg` (under 1 MB) and upload it at Settings, Social preview (no API; a browser tool if one is signed in, otherwise a step for the maintainer). `usesCustomOpenGraphImage` in `gh api graphql` reads whether it is set. No banner yet: make the banner first. Recipe: package-modernize `references/readme-images.md`. Not yet a row in the table |
| wikiwright | hand over to the wikiwright skill |
| package-modernize | a package missing a golden recording, a gated release, trusted publishing or a verify-published workflow: write a package-modernize kickoff prompt to the overlay's prompts folder instead of a fix |
| manual | the size budget needs thresholds agreed with the maintainer |

`--deep` also runs package-modernize's `topics.py check` and `lint-workflows.sh` (actionlint, shellcheck, zizmor) on the local clone; without package-modernize installed it says "not checked".

## Dated deadlines

Listed at the top of the digest until they pass:

| Date | What |
|---|---|
| 2026-11-01 | NuGet API keys created before 2026-08-17 expire: a repo still publishing with a stored key needs trusted publishing first |
| 2026-11-02 | `pull_request_target` blocked by default on public repos without an event policy: list each workflow using it and escalate |
| 2026-11-10 | .NET 8 and 9 end of support |
| 2026-10-31 | Unity 6.0 LTS ends |
| January 2027 | npm stops accepting tokens that bypass 2FA |

Settings quirks: `sha_pinning_required` is per repo, and its `PUT` replaces the whole Actions permissions object, so read it and send every field back.

Related: builds on [design.md](../../../ai-docs/plans/design.md); see also [deps.md](deps.md).
