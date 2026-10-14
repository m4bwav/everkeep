# Providers roadmap

## Status

Planned, not started. Owner: a later session, after everkeep's GitHub build is live.

## Goal

add hosting providers to everkeep one adapter file at a time, with nothing above the provider interface changing.

## Next single action

When Mark asks for a second provider, start with Forgejo/Gitea against a disposable local container (below).

The interface, GitHub's capability matrix and the rule-mapping table with every provider's column: [../../skills/everkeep/references/providers.md](../../skills/everkeep/references/providers.md). Research with sources: [../research/2026-10-13-other-providers.md](../research/2026-10-13-other-providers.md).

## Order and why

1. **Forgejo/Gitea (Codeberg)**: closest to GitHub (labels, assignees, reviewers, head-SHA merge, `pull_request_target`-style Actions), free to test with a local container and with read-only calls on Codeberg, common for open source. One adapter covers both (Forgejo answers `/api/forgejo/v1/version`; Gitea does not). Watch Codeberg's terms: projects that mostly consist of AI-written code are barred, so everkeep's own PRs there stay small and human-reviewed.
2. **GitLab**: almost one to one with GitHub; `glab` has JSON output. Security alerts need Ultimate, so the vulnerability duty falls back to osv-scanner on a clone. Trusted publishing works from gitlab.com only (npm, PyPI, crates.io; NuGet also self-managed per its docs).
3. **Bitbucket Cloud**: no labels, assignees, issues or wiki; escalation is reviewer + marker comment; no CLI, raw REST with an Atlassian API token.
4. **Azure DevOps**: labels but no assignee; "complete" and "abandon"; comments are threads; rate limits in TSTUs. Testing needs a free organization, which is Mark's to create.

## What each adapter must do

- Implement every method in the interface or return `Unsupported` with a reason; declare its `Capabilities` honestly.
- Implement `escalate()` per the mapping table and `checks_state()` reducing the host's model to `passed`, `failed`, `not_run`, `pending`, `none`.
- Guard every merge with the judged head SHA.
- Add its URL forms to `registry.py` with table-driven tests (nested GitLab groups, Azure `DefaultCollection`, `org@` prefixes, `vs-ssh`, `ssh://` ports, `%20` in names).
- Read auth from the host's CLI or an environment token; never store a token; report the exact login command when missing.
- Respect the host's rate limits (in the mapping table) and read its rate headers.
- Never write the unsafe fork-pipeline form for that host (mapping table, "Fork secret hygiene").
- Add a row to the capability table in `skills/everkeep/references/providers.md`, flip its column from "not built" to "built", and add trigger evals ("maintain this repo" in a clone from that host).

## Test approach

- **Forgejo/Gitea**: `docker run -d --name ek-forgejo -p 3000:3000 -e FORGEJO__security__INSTALL_LOCK=true codeberg.org/forgejo/forgejo:<current-major>`, then `docker exec -u git ek-forgejo forgejo admin user create --admin --username ek --password <random> --email <any address>` and `forgejo admin user generate-access-token --username ek --scopes all`; create a repo, a fork and a PR through the API; run list, diff, label, assign, review request, comment, merge, close; `docker rm -f ek-forgejo`. Gitea: `docker.gitea.com/gitea:<version>` with `gitea admin user create`. Image names and flags are from the research agent's memory: check them first. Docker is not confirmed installed on Mark's PC; WSL2 Ubuntu is.
- **GitLab and Codeberg read-only**: `curl "https://gitlab.com/api/v4/projects/gitlab-org%2Fcli/merge_requests?state=opened&per_page=1"`; `curl "https://codeberg.org/api/v1/repos/forgejo/forgejo/pulls?state=open&limit=1"` (both answered anonymously on 2026-10-13).
- **Recorded fixtures** for any provider without a free test account (Azure until Mark creates an organization): build JSON fixtures from the REST reference and run the adapter against them.
- **Seam test**: the existing `tests/test_seam.py` must keep passing unchanged; a new adapter that needs a change above the interface is a design bug to fix in the interface first.

## Open questions to settle when the work starts

From the research note's "Not verified" list: GitLab secret push protection on Free public projects; Bitbucket Pipelines and forks; Azure Repos fork builds; `AZURE_DEVOPS_EXT_PAT`; whether Gitea and Forgejo read `.github/workflows/`; `fj` and `tea` JSON output.

Related: builds on [design.md](design.md); see also [../../skills/everkeep/references/providers.md](../../skills/everkeep/references/providers.md).
