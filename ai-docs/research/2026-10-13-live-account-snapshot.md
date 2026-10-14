# Live account snapshot, 2026-10-13 (m4bwav on GitHub)

Read-only survey done at the start of Phase 0 with `gh` and the local disk, to ground the design in real data. Re-run before relying on any count; the open PRs change daily.

## Repositories

- 67 repositories (repo-traffic `data/repos.csv`, snapshot 2026-10-13; `gh repo list m4bwav` agrees): 21 private, 7 forks (christmas-tree, is-image-url, kendo-ui-core, Kidoju-Widgets, openupm, securesocial, stackexchange), 2 archived (eg-01-csharp-jwt-core, everlast-protocol).
- Local clones: about 46 found in the maintainer's project folders; about 40 have `ai-docs/`. Others live elsewhere, so the CLI needs a clone map (state store) plus a throwaway-clone fallback, never a search of the disk.
- The everlast vault registry lists 28 projects. Several public repos have `ai-docs/` on disk but are not registered (chartwright, everwrite, polywright, threewright, skill-tidy, IsImageUrlDotNet, science-study-evaluator, among others, plus several private repos). Repos with no knowledge base at all include image-concatenator, Angular2TestProject, stack-link-replacer, XBox-Game-List-Website-Example-With-MVC4, several private repos, and every fork.
- Topics: every non-fork source repo has 5 or more except finwright (0, private).

## Downloads (repo-traffic `data/downloads.csv`, 2026-10-13)

| Registry | Package | Recent | Total |
|---|---|---|---|
| NuGet | RandomNameGeneratorLibrary | 173,466 in 6 weeks | 3,923,964 |
| NuGet | JsonPrettyPrinter | 5,810 in 6 weeks | 310,993 |
| NuGet | TrailerClipper | 338 | 17,116 |
| NuGet | IsImageUrlDotNet | 336 | 4,761 |
| NuGet | CachingServiceWithAOPSupport | 230 | 4,194 |
| NuGet | UniverseGenerator, TrailerClipper.Tool | 274, 188 | new |
| npm | seven packages | 532 to 969 a month each | |
| OpenUPM | com.m4bwav.universe-generator | 5 | |

Only the first two are clearly "packages people download". npm counts of 500 to 1,000 a month for packages with no known dependents are mostly mirrors and scanners; tiering thresholds go to the decisions table.

## Open pull requests: 19, all Dependabot

| PR | Files | Checks | What the rules should do |
|---|---|---|---|
| CachingServiceWithAOPSupport#10, #11; IsImageUrlDotNet#15, #16; TrailerClipperLib#11, #12 | `.github/workflows/ci.yml`, `release.yml` (actions/download-artifact 8.0.1 to 8.0.2, upload-artifact 7.0.1 to 7.0.2) | green | Touches CI and release config, so the kickoff's rule says escalate. Six routine first-party patch pins a week would flood Mark's list: decision D-rule for a narrow exception (pin-only diff of a first-party action, patch or minor, past cooldown). |
| FizzBuzzPlus#6, UniverseGenerator#61 | `global.json` (dotnet-sdk 10.0.100 to 10.0.401) | green | Toolchain patch, same publisher, green: merge. |
| DotNetRandomNameGenerator#23 | `global.json` (same bump) | **failing** | High-download package: escalate whatever happens; still diagnose the failure first and fix it on the branch if it is mechanical. |
| CachingServiceWithAOPSupport#12, DotNetRandomNameGenerator#24, IsImageUrlDotNet#17 | test project `.csproj` + `packages.lock.json` ("test-packages" group: NUnit3TestAdapter 6.3.0 to 6.3.1) | **failing** | Dependabot's NuGet updater rewrote each `packages.lock.json` and dropped the `.NETFramework,Version=v4.8` and `net10.0/win-x86` sections (CachingService: +28 -300 and +28 -264 lines). Locked-mode restore then fails. The fix is mechanical: check out the branch in a throwaway worktree, `dotnet restore --force-evaluate` on Windows (where net48 resolves), push, let CI rerun. This is the canonical "fix a failing bot PR" case and the lockfile-diff check must flag removed target sections, not only added packages. |
| format-json-files#10, is-an-image-url#32, replace-string-at-position#9, seeded-random-utilities#26, stack-exchange-markdown-retriever#30 | `package-lock.json` only ("minor-and-patch" group, 2 updates) | green | Lockfile-only, dev tooling: merge after the lockfile-diff check (no new packages, no new sources, no install scripts, past cooldown). |
| a private site repo, two PRs | `client/package*.json`; a test `.csproj` | cancelled + skipped | Private repo on its self-hosted runner: checks did not run, so never merge on this state. Run the runner check, then judge. |

Takeaways for the design:
1. "Fix failing bot PRs" is not rare: 4 of 19 failed on the same day, 3 of them from one Dependabot NuGet lockfile bug.
2. The CI-config escalation rule needs a narrow, explicit exception for Dependabot's own action pin bumps, or every week starts with six escalations.
3. Check state has four outcomes the classifier must tell apart: green, failing, skipped or cancelled (did not run), pending. Only green merges.
4. `gh pr view --json` has no `authorAssociation`; author history comes from the REST API (`GET /repos/{o}/{r}/pulls/{n}` has `author_association`) or a search for the author's other PRs.
