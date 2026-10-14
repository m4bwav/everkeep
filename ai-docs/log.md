# everkeep log

Append-only. Newest last.

## 2026-10-13: Phase 0 research and Phase 1 design (kickoff kept outside this repository, in the maintainer's private notes)

- Name checked: `everkeep` free on GitHub (no m4bwav repo; five unrelated 0-star repos), npm (404), NuGet (0 hits) and every installed plugin. PyPI `everkeep` is reserved (0.0.0) by an unrelated storage product, everkeep.dev; not a blocker since everkeep publishes nowhere. `keepwright` is taken by leonardocandiani/keepwright, a Claude Code skill for repo quality: a worse collision. Kept everkeep.
- Mark, mid-session: "This will be for a public repo with all the fixin's" (public `m4bwav/everkeep`, banner, icon, SECURITY.md, topics, wiki, CI, evals).
- Mark, mid-session: "Eventually we will run this on all my repos to sharpen the tool with and encounter real life bullshit. As your learning maybe you warn me not to merge a dependency until x time or something and leave a comment on it." Became the sticky verdict comment and learning mode (design section 6, decision D13).
- Live snapshot (`research/2026-10-13-live-account-snapshot.md`): 67 repos, 19 open PRs all Dependabot, 4 failing; 3 failures are one Dependabot NuGet bug that rewrites `packages.lock.json` and drops the `net48` and `win-x86` sections (CachingServiceWithAOPSupport#12, DotNetRandomNameGenerator#24, IsImageUrlDotNet#17). Six open PRs are first-party action pin bumps touching workflows (decision D7).
- Four research agents wrote `research/2026-10-13-verification-and-recent-changes.md`, `-maintainer-bots-and-practice.md`, `-other-providers.md`, `-ecosystem-apis-scanners-eol.md`. The first agent stopped once without working and had to be resumed with a direct instruction; the forum agent was slow from Reddit RSS pacing and was told to wrap up after 20 minutes.
- Corrections filed in the old landscape note: Yegge's post date, Ghostty's policy wording, Miasma provenance.
- Wrote `plans/design.md` (decisions table D1 to D13), `../references/providers.md` (interface, GitHub matrix, rule mapping with other providers not built), `plans/providers-roadmap.md`.
- Skill catalog measured with skill-tidy: 61 skills, about 12.3K tokens of descriptions against a 2K-character Claude Code listing budget, hence one listed skill (D8).
- Stopped at the Phase 1 stop: decisions table to Mark.
- Mark's answers (structured question, 2026-10-13): D4 "Private in, forks out (Recommended)", D6 "RNG + JsonPrettyPrinter (Recommended)", D7 "Merge pin-only first-party (Recommended)", D2 "Weekly, after rollout (Recommended)". The other rows stand as recommended. Design approved; Phase 2 build is next, from `next-session-prompt.md`.

## 2026-10-13: Phase 2 build

- `git init` (master), everlast-setup (mode repo, sync push). `references/providers.md` moved to `skills/everkeep/references/`.
- Built the CLI inside the skill folder (`skills/everkeep/scripts/keep.py` and `scripts/everkeep/`, about 3,900 lines, stdlib only) so the skill travels whole; `scripts/size_check.py` stays at the root. Recorded in design section 4.
- Classes as designed plus one addition: `own` for PRs opened by the account everkeep runs as (other sessions' work), listed and left alone.
- GitHub adapter checked against the live account: the 19 open Dependabot PRs classify as the snapshot expected (npm groups and FizzBuzzPlus#6 merge; the six first-party pin bumps merge under D7; the three NuGet lockfile PRs are `fix`, with the removed `net48`/`win-x86` sections and one new transitive package flagged). Async merge body (`sha`, `merge_method`, `merge_action`) confirmed in the REST docs.
- Real-data fixes found while resolving the whole account: an unpublished npm name claimed by a private repo, an F# library missed (`.fsproj`), template and fixture folders read as ecosystems, a version parsed with Dependabot's trailing full stop, NuGet's two-digit fraction of a second (Python 3.10). Packages now count only when the registry has them and, with `registry_accounts` set, the user owns them. Filters gained `package=` and comma-as-any.
- 80 unit tests pass on Python 3.10, 3.11 and 3.14 (Windows). The seam test puts a one-file git shim alone on PATH, because GitHub's Linux and macOS runners keep gh beside git in /usr/bin.
- Skill written through evergreen-new (tier fast, next due 2026-10-27); worth UNPROVEN (nothing suspect, no A/B yet); skill-tidy: closest description 0.17; size budget green except the installed size, 569 KB (yellow, line 400 KB) because the Phase 0 research notes ship with the plugin.
- Banner: Z-Image Turbo on the idle Mac (the PC was rendering another session's video), polywright's banner workflow, seed 44 of four. Icon: package-modernize's make-icon.py from origin/master (the local clone lacked `--size`), 512 master plus 128.
- Private overlay written to the vault sidecar (`projects/everkeep/private/overlay`, D10) and junctioned to `~/.everkeep/overlay`: escalation account, private repos in `--all`, learning mode on, high-risk list, starter selections, clone roots, registry accounts.
- Registered in evergreen, added to the mark-local marketplace, installed as `everkeep@mark-local`.
- Before publishing: scrubbed private repo names and local paths from the docs, code and research notes; the session prompt `ai-docs/next-session-prompt.md` is gitignored (local paths) with a copy in the private sidecar.

## 2026-10-13: Phase 3 dry runs (no --apply) and the public repository

- Public repository m4bwav/everkeep created from a squashed first commit (private names and local paths removed first; history checked clean). Topics set; `keep.py enable all --repo everkeep --apply` switched on Dependabot alerts and security updates, private vulnerability reporting, CodeQL default setup and the open-PR cap, read back as on. CI green on all six suite jobs and the budget job.
- PR #1 added `keep.py enable` (the gaps table named the D11 fix but no command did it); PR #2 carried the dry-run fixes. Both merged by the author rule after green checks. everkeep classified its own PR #1 as `own` and left it alone.
- Dry run 1, this repo, every duty: one gap (ruleset, ask first).
- Dry run 2, replace-string-at-position, CachingServiceWithAOPSupport, readwright: 3 would merge, 1 needs a fix (the NuGet lockfile PR), real gaps; npm audit's 10 findings were all dev-only (L-003).
- Dry run 3, `run start --all` (60 repos: private in, forks and archived out per D4), interrupted after 8 with `EVERKEEP_INTERRUPT_AFTER=8` (exit 130, 8 done, 52 pending), resumed to 59 done and 1 failed; the failure (gh refusing a raw file with terminal escapes) was fixed and `run resume --failed` finished it: 60 done.
- Hand check: all 19 open PRs match the live snapshot's expected calls (13 would merge, 6 need a fix); five verified independently from GitHub (files and check conclusions of format-json-files#10, is-an-image-url#32, seeded-random-utilities#26, IsImageUrlDotNet#17, UniverseGenerator#61).
- Findings for the maintainer: an open secret-scanning alert (Google API key, since 2026-09-27, validity unknown) on a public plugin repo; five Dependabot alerts, all in development dependencies; 63 npm audit findings across 7 npm repos, all dev-only; CONTRIBUTING.md with an AI policy missing in 59 repos, no dependency-bot cooldown in 45, CodeQL default setup and the PR cap off in 39 public repos. Deadlines: one private repo still tests Node 20; one private Unity repo has a net8/9 test project (2026-11-10).
- The all-repo digest is in the maintainer's state folder (`runs/20261014-030304-ehtv/digest.md`), not in this repository (it names private repos).
- Package at 3,937 lines (green line 4,000); installed size 579 KB (yellow).

## 2026-10-14: first single-repo maintain run (IsImageUrlDotNet), learning mode, and the fixes it found

- Mark asked to run everkeep on another repo and fold everything learned back in. Picked IsImageUrlDotNet (public NuGet library, medium tier, never run alone): two first-party pin bumps that would merge, one failing Dependabot NuGet PR, gaps, a knowledge base not in the vault. Fast-forwarded its clean clone first (4 behind; scanners would have read a stale tree).
- Every duty ran (prs, vulns, deps, gaps, kb). The fix duty was exercised for real for the first time, without pushing (learning mode): #17's failure is NU1004 in locked restore on all three OSes; in a throwaway worktree on Windows `dotnet restore --force-evaluate` restored the net48 and win-x86 sections, and locked restore, build and all tests (net10.0 and net48) passed. The same bump adds a transitive package, so #17 still escalates once fixed.
- Reading the dry-run comment text before posting caught a parser bug: NuGet group bodies say "Updated [x](url) from A to B", which `parse_bot` missed, so NuGet group PRs never had their cooldown checked (masked in the all-repo run because the fix row wins first).
- Fixed, with tests (86 pass): NuGet "Updated" parsing; `fix_recipe` and `after_fix` on fix items, said in the verdict comment and `prs show` and the digest; `act` dry run writes `<plan>.comments.md`; repeated lockfile reasons collapse (`util.collapse_reasons`); deps skips unlisted NuGet versions (dated 1900-01-01) and lists dependabot ignores and exact pins as held; `$(...)` target frameworks skipped; icon gap reads `.fsproj`; bare repo names in `prs show` and `state`. github.py write wrappers folded into one `_write` helper: package 3,997 lines (green under 4,000).
- Posted three learning-mode verdict comments (IsImageUrlDotNet#15, #16, #17), checked sticky on a second dry run.
- Lessons L-004 to L-008 in the skill's LEARNINGS.md; recipe in references/prs.md.
- Open for Mark: new transitive packages from the same publisher (Microsoft.TestPlatform.AdapterUtilities with NUnit3TestAdapter) always escalate; keep that, or allow a same-owner transitive on a patch bump? Not changed without his say.

## 2026-10-14: the maintainer's rulings after the IsImageUrlDotNet run

- PR #3 merged (squash) after green checks.
- Mark: "ok, 1 more learning mode run": one more learning-only single-repo run, then learning mode goes off and Phase 4 begins. Picked seeded-random-utilities (npm, never run alone; an open Dependabot alert, low severity in a development dependency, so the vulnerability duty meets a real alert; one Dependabot group PR; clean clone).
- Mark on new transitive packages: escalate "only if it seems dangerous". Recorded as D14 in plans/design.md; not built yet (the next session builds it, with tests, before the run).
- Mark: the everlast secret-scanning alert was a false alarm, resolved as used in tests. everkeep queries open alerts only, so no code change.


## 2026-10-14: D14 built, the last learning-only run (seeded-random-utilities), learning mode off, Phase 4 begun

- D14 built in PR #5 (merged after green checks). Checked against live registry data first: nuget.org lists NUnit3TestAdapter's owners as NUnit and three people, and the new Microsoft.TestPlatform.AdapterUtilities as Microsoft and vstest, so "a different owner than the direct package" as first worded would still have escalated IsImageUrlDotNet#17. The owner check compares instead with every package the update moves (the bumped packages and the lockfile entries whose version changed; here four Microsoft.Testing packages owned by Microsoft). Other signals: first published under 90 days ago or date unknown, not on its registry, a name one edit from a popular or bumped package, a known-compromised version; a failed lookup is a signal, never a pass. L-009 `transitive-owner-is-the-update-not-the-parent`.
- To pay for D14 the unused provider methods `open_pr` and `rate_state`, `GuardRefused` and `overlay_text` were removed and two GitHub helpers folded. The package still ends past the green line: 4,089 lines against 4,000 (yellow; CI passes, the maintainer decides whether to trim further or move the line).
- seeded-random-utilities (fast-forward not needed, clean and current): #26 merge-candidate (two dev-only patch bumps, 11 checks green, same publishers); comment read word for word in the dry run, then posted in learning mode: https://github.com/m4bwav/seeded-random-utilities/pull/26#issuecomment-6173988266. vulns: the katex alert (low, development scope), npm audit 9 findings all dev-only. kb ok.
- The run found four misreads, fixed in PR #6 (merged after green checks): deps held @types/node and typescript outright although their dependabot ignores cover majors only (L-010 `dependabot-ignore-has-update-types`); gaps missed `npm stage publish` and the tarball budget in `scripts/check-tarball.mjs` (L-011 `gaps-read-the-repos-own-gates`); vulns did not show an alert's scope (L-003 extended).
- Learning mode set off in the overlay (`"learn": false`, noted in OVERLAY.md beside D13). Plugin reinstalled from master.
- Phase 4 on everkeep itself: no open PRs, nothing to apply.
- IsImageUrlDotNet#17: the verified lockfile fix pushed to Dependabot's branch (D12) after a Windows `dotnet restore --force-evaluate`, locked restore, Release build and every test on net10.0 and net48 passed locally; CI green on all three OSes. Under D14 the PR is now a merge candidate, like #15 and #16. Their sticky comments were refreshed (comments only); nothing merged, because the maintainer sees the first Phase 4 result before anything merges or widens.
- No replies from the maintainer on the earlier verdict comments (IsImageUrlDotNet #15, #16, #17).
- Phase 5 eval suite, first run (T-20261014-1): 9/9. Triggers fired 3 of 3 with the plugin and never without; decoys stayed quiet; action and outcome cases passed every run on the fake provider (tester subagents, since `plugin eval` needs WSL2 for Bash on Windows and refuses an eval dir under skills/). About $5 for the plugin-eval half. The action-1 and outcome-1 baselines are biased (their prompts carried the expected answer by mistake) and need a clean rerun. The runs found two public-text bugs (close comments missing from the dry-run preview; an agent-chosen escalation showing only merge reasons), fixed with tests (L-012) in the same PR as the SKILL.md wording fix (only scope-taking commands exit 3 on an unsupported host).
