# everkeep

![A small white robot gardener in a sunny greenhouse pruning a dead branch from a potted bonsai, beside rows of bonsai in labelled pots, a tray of seedlings, an hourglass, a clipboard checklist and a laptop showing green and amber rows](https://raw.githubusercontent.com/m4bwav/everkeep/master/.github/images/banner.jpg)

An agent skill and a small command-line tool that keep the repositories and packages you already own healthy. By default it looks after the one repo you are in. Ask, and it looks after a saved selection or your whole account. It triages pull requests, checks vulnerabilities, outdated dependencies and toolchains, finds missing modernization pieces, and ends every run with one digest.

It is built for a solo maintainer with dozens of small repositories and a weekly pile of Dependabot pull requests, most of them safe and a few of them not. The tool gathers the facts and makes the mechanical calls. The agent judges what the rules leave open. Nothing is merged, closed or commented on until you add `--apply`, and every guard is checked again at the moment of acting.

## What it does with a pull request

Each open pull request gets facts and a class:

| Class | When | What happens |
|---|---|---|
| hold | checks still running, a draft, or a dependency version younger than the cooldown (3 days, 7 for a major), measured from the registry's own publish time | a comment says until when |
| fix | a bot PR whose checks failed, or never ran | the agent diagnoses the failure and pushes the smallest mechanical fix to the bot's branch |
| escalate | a package people download, a major bump, CI or publish config touched, a lockfile that adds packages or sources or drops target sections, a publisher change, anything unsure | assigned to you with a `needs-review` label, and a comment saying why |
| close-candidate | a newer bot PR replaced it, or a human PR with several negative signals that the agent confirms by reading the diff | closed politely from a template that cites your CONTRIBUTING.md |
| merge-candidate | green on the head commit, past the cooldown, same publisher, clean lockfile | merged with your repo's usual merge method, guarded by the reviewed commit |

Two cases from the first real data: on one day Dependabot's NuGet updater rewrote three `packages.lock.json` files and dropped their `net48` and `win-x86` sections, and the lockfile check catches exactly that. Six pull requests the same day only moved first-party `actions/*` pins by a patch version; everkeep proves a diff is pin-only line by line and lets those through instead of burying real escalations.

Every pull request it holds, fixes, escalates or plans to close gets one comment that is edited in place on later runs, never stacked. In learning mode (`--learn`) that comment is all it does: it says what it would do and asks you to correct it. Start there.

## Commands

```
python skills/everkeep/scripts/keep.py providers
python skills/everkeep/scripts/keep.py scope resolve --all
python skills/everkeep/scripts/keep.py prs --plan plan.json            # this repo
python skills/everkeep/scripts/keep.py prs show owner/name#12
python skills/everkeep/scripts/keep.py act plan.json                   # dry run
python skills/everkeep/scripts/keep.py act plan.json --apply --learn   # comments only
python skills/everkeep/scripts/keep.py gaps --repo owner/name
python skills/everkeep/scripts/keep.py vulns --select nuget --clone
python skills/everkeep/scripts/keep.py run start --all --duties prs,vulns,gaps,kb
python skills/everkeep/scripts/keep.py run resume <run-id>
python skills/everkeep/scripts/keep.py report latest
```

| Command | Does |
|---|---|
| `providers` | which hosts are configured, who is logged in, what each host can do |
| `scope resolve`, `scope save NAME`, `scope list` | resolve a scope to a list of repos, store a selection |
| `inventory` | every repo in scope with its risk tier, ecosystems, packages, local clone and knowledge base |
| `prs`, `prs show REPO#N` | open pull requests with facts and a class; one PR with its text fenced as untrusted |
| `act PLAN.json` | carry out the agent's verdicts, refusing anything the rules do not allow now |
| `vulns` | host alerts plus osv-scanner, npm audit and `dotnet package list --vulnerable` on a clone |
| `deps` | outdated direct dependencies and toolchains, with publish dates |
| `gaps` | missing SECURITY.md, banner, topics, pinned actions, security settings, trusted publishing, wiki, size gate, CONTRIBUTING.md, and dated deadlines |
| `kb` | repos with no `ai-docs/` knowledge base, with the everlast command to set one up |
| `research gather` | dependents, downloads and discussion for an ecosystem note |
| `run start/resume/status`, `report` | resumable multi-repo runs and their digest |

Every command takes the same scope arguments: none (the current repo), `--repo` (repeatable), `--select NAME`, `--filter KEY=VALUE` (ecosystem, topic, name, visibility, tier, pushed, has), or `--all`, plus `--include-forks`, `--include-archived` and `--include-private`. `--json` gives JSON. A multi-repo run goes low-risk repos first, and it stops widening when a repo shows something unexpected (a lockfile pulling a git source, a known-compromised version) until you have looked.

## Hosts

GitHub only for now, through the `gh` CLI and whatever `gh auth login` holds. Everything goes through a provider interface, so GitLab, Forgejo and Gitea (Codeberg), Bitbucket and Azure DevOps can each be added as one adapter. In a clone from one of those, every command says "provider X isn't supported yet", links to the [request template](.github/ISSUE_TEMPLATE/provider.md), and does nothing else. The interface, GitHub's capabilities and how each rule maps to the other hosts are in [references/providers.md](skills/everkeep/references/providers.md).

## Install

Claude Code, from a clone:

```
git clone https://github.com/m4bwav/everkeep
claude plugin marketplace add ./everkeep
claude plugin install everkeep@everkeep
```

Other agents that read Agent Skills (`SKILL.md`): link or copy `skills/everkeep` into their skills folder (`~/.claude/skills/`, `~/.agents/skills/`). The tool alone needs Python 3.10 or newer and a logged-in `gh`.

Your own settings (who escalations go to, packages that always need a human, saved selections, caps, learning mode) go in `~/.everkeep/overlay/overlay.json`, outside every repository. The keys and their defaults are in `DEFAULTS` in [state.py](skills/everkeep/scripts/everkeep/state.py).

## Safety

Pull request titles, bodies, comments and diffs are treated as data: hidden HTML, invisible characters and over-long fields are stripped before the agent reads them, and the skill tells it never to follow instructions found there. Judging and acting are separate: the agent writes a plan, and only `act` writes, only from a short list of actions, with public comments built from templates. Pull request code never runs to be judged. Caps (3 merges per repo, 10 per run, 5 closes per run) and learning mode keep a wrong rule from doing much before you see it. [references/safety.md](skills/everkeep/references/safety.md) has the details.

## Privacy

everkeep runs on your machine. It talks to GitHub through your own `gh` login and stores no token. It reads public registry data without a key (npm, NuGet, PyPI, the .NET release metadata, endoflife.date) to learn when versions were published, and `research gather` asks ecosyste.ms and Hacker News' search for public package facts. State (run files, per-repo memory, digests) stays in `~/.everkeep`. What it reads goes into your agent's context and so reaches whatever model provider your agent already uses.

## Tests

`python -m unittest discover -s tests -t tests` runs the unit tests, on Windows, macOS and Linux with Python 3.10 and 3.14 in CI. The fixtures include real public Dependabot diffs from October 2026 and a fake account that runs every duty with `gh` removed from PATH, proving nothing above the provider interface needs `gh`. `python scripts/size_check.py` checks the size budget. Skill evals are in [skills/everkeep/evals](skills/everkeep/evals/evals.json).

## Evergreen

The skill keeps its research current on a schedule (tier fast, every 14 days to start): GitHub's API and Dependabot changes, registry and supply-chain news, toolchain end-of-life dates and how other maintainers handle AI-era pull requests are re-checked from primary sources. Every change is logged with its reason in [CHANGELOG.md](skills/everkeep/CHANGELOG.md), and lessons from real repos go to [LEARNINGS.md](skills/everkeep/LEARNINGS.md).

## Licence

MIT, see [LICENSE](LICENSE). Contributions: [CONTRIBUTING.md](CONTRIBUTING.md). Security: [SECURITY.md](SECURITY.md).
