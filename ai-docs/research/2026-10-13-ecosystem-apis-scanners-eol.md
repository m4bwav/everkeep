# Ecosystem APIs, scanners and EOL data for everkeep (research 2026-10-13)

Phase 0 research for everkeep's stdlib-Python CLI. It builds on sections 4 and 5 of the landscape note (kept outside this repository). Every free, keyless API below was called once from Mark's PC on 2026-10-13 (evening, US time; some responses carry 2026-10-14 UTC stamps), and the response shape is recorded. Main findings: ecosyste.ms puts you in its polite pool (15,000 requests an hour) only when `?mailto=` is in the query string, and a user agent alone leaves you anonymous (5,000 an hour). OSS Insight's trending endpoints return empty results with a `data_quality: unavailable` note, because their GitHub event capture collapsed on 2026-03-01. deps.dev v3alpha has a working dependents count. OpenUPM's `/packages/extra` gives 30-day downloads for every package in one call. endoflife.date v1 covers nodejs, dotnet, python and unity. The local scanners all emit JSON with usable exit codes: osv-scanner v2.7.0 (released 2026-10-12), npm audit, `dotnet package list`, pip-audit 2.10.1. Node 20 actions stopped running on GitHub-hosted runners on 2026-09-23, and actions/checkout is at v7 (node24). For headless runs, `claude -p` in a repository you did not write still runs that repository's settings hooks and `.mcp.json` servers unless you pass `--bare` or `--setting-sources user`.

## 1. Ecosystem-research APIs

Notation: each entry gives the base URL, a call that worked on 2026-10-13, the limits, and the questions it answers.

### ecosyste.ms (packages, repos, issues, advisories)

- Docs: https://ecosyste.ms/api (read 2026-10-13). Free, no key, CC BY-SA data.
- Limits, from the response headers: `x-ratelimit-tier: anonymous`, `x-ratelimit-limit: 5000` without mailto, and `x-ratelimit-tier: polite`, `x-ratelimit-limit: 15000` with `?mailto=you@example.com`. The reset is hourly. On packages.ecosyste.ms, a user agent containing the email was **not** enough: it stayed anonymous until `?mailto=` was added. repos, issues and advisories gave polite with the user agent alone. **Always append `mailto=` as a query parameter.**
- Packages: `https://packages.ecosyste.ms/api/v1/registries/npmjs.org/packages/get-title-at-url?mailto=...`
  - Abbreviated response: `{"name":"get-title-at-url","latest_release_number":"3.0.0","latest_release_published_at":"2026-09-25T15:42:58.478Z","downloads":772,"downloads_period":"last-month","dependent_packages_count":3,"dependent_repos_count":30,"rankings":{"downloads":6.27,"average":6.77,...},"advisories":[...],"maintainers":[...],"repo_metadata":{...},"related_packages_url":"..."}`
  - Registry names: `npmjs.org`, `nuget.org`, `pypi.org`. NuGet worked: `.../registries/nuget.org/packages/RandomNameGeneratorLibrary` returned `downloads: 3894453` and `dependent_packages_count: 8`.
  - Answers: "who depends on my package" (counts plus `.../dependent_packages?per_page=5`, which returned 4 names), "how big is it relative to others" (`rankings` percentiles), and "what is related" (`related_packages_url`).
- Repos: `https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/m4bwav/get-title-at-url` returns `stargazers_count`, `pushed_at`, `topics`, `archived`, `tags_url`, `releases_url`, `manifests_url`, `sbom_url`, and an embedded OpenSSF `scorecard` (score 1.7, dated 2025-08-11, so it can be stale). Answers: "repo health and Scorecard without running Scorecard".
- Issues: `https://issues.ecosyste.ms/api/v1/hosts/GitHub/repositories/m4bwav/get-title-at-url` returns past-year counts: `past_year_pull_request_authors_count`, `past_year_bot_pull_requests_count`, `pull_request_authors` (dependabot[bot] 8, snyk-bot 3), `maintainers`, `active_maintainers`. Answers: "is the project maintained, and who does the work".
- Advisories: `https://advisories.ecosyste.ms/api/v1/advisories?ecosystem=npm&package_name=lodash&per_page=2` returns `identifiers` (GHSA and CVE), `severity`, `cvss_score`, `epss_percentage`, `withdrawn_at`, `packages`. Answers: "advisories with EPSS for a package" without a GitHub token.

### deps.dev (Google Open Source Insights)

- Docs: https://docs.deps.dev/api/v3/ and https://docs.deps.dev/api/v3alpha/ (read 2026-10-13). No key. The docs state no quota and "Clients are expressly permitted to cache data served by the API."
- Systems: GO, RUBYGEMS, NPM, CARGO, MAVEN, PYPI, NUGET. GetDependencies (the resolved graph) works for npm, Cargo, Maven and PyPI only, not NuGet. GetRequirements covers NuGet.
- v3 endpoints: `/v3/systems/{system}/packages/{name}`, `.../versions/{version}`, `...:requirements`, `...:dependencies`, `/v3/projects/{id}`, `/v3/projects/{id}:packageversions`, `/v3/advisories/{id}`, `/v3/query`.
- Calls that worked:
  - `https://api.deps.dev/v3/systems/npm/packages/lodash/versions/4.17.15` returned `publishedAt`, `isDeprecated`, `licenses`, `advisoryKeys` (6 GHSA IDs), `slsaProvenances`, `attestations`, `registries`, `relatedProjects`.
  - `https://api.deps.dev/v3/systems/nuget/packages/randomnamegeneratorlibrary/versions/2.3.0:requirements` returned `{"nuget":{"dependencyGroups":[{"targetFramework":".NETStandard2.0","dependencies":[]},...],"targetFrameworks":["net10.0","netstandard2.0"]}}`. NuGet names are lower-cased.
  - `https://api.deps.dev/v3/projects/github.com%2Fm4bwav%2Fget-title-at-url` returned stars, forks, license, and a Scorecard dated 2026-08-24, newer than the one ecosyste.ms holds.
  - v3alpha `.../versions/3.0.0:dependents` returned `{"dependentCount":1,"directDependentCount":1,"indirectDependentCount":0}` (npm, Cargo, Maven, PyPI only).
  - v3alpha `.../packages/get-title-at-url:similarlyNamedPackages` returned `"packages":[]`. This is a typosquat check for new dependencies.
  - v3alpha `/v3alpha/purl/pkg:npm%2Fget-title-at-url@3.0.0` returned the version record. A `POST /v3alpha/versionbatch` takes up to 5000 versions.
- Answers: "is this version deprecated or advised against", "does it carry provenance", "who depends on it (count)", and "is this new dependency name suspiciously close to another".

### OSS Insight

- `https://api.ossinsight.io/docs/json` (Swagger, read 2026-10-13) lists `/v1/{wildcard}`, `/gh/...`, `/collections/`, `/q/{wildcard}` and `/explorer/answer/`. There is still no formal public docs page with limits.
- `https://api.ossinsight.io/v1/trends/repos/?period=past_week&language=TypeScript` returned 200 with **empty rows** and `"data_quality":{"status":"unavailable","unavailable_since":"2026-03-01","reason":"...our capture of those events fell to roughly 0.3% of baseline..."}`. It suggests `/gh/repos/{owner}/{repo}` and `/v1/collections/{id}/repos` instead.
- `https://api.ossinsight.io/gh/repos/m4bwav/get-title-at-url` returned 200 with a GitHub-style repo object wrapped in `{"requestedAt","finishedAt","data":{...}}`.
- Verdict: **do not use OSS Insight for "is this trending" in 2026.** Use ecosyste.ms rankings, npm, PyPI and OpenUPM download series, and HN mentions.

### libraries.io

- `https://libraries.io/api/npm/get-title-at-url` answered **without an API key** on 2026-10-13 (200, full package JSON) with headers `x-ratelimit-limit: 10`, `x-ratelimit-remaining: 8`. The window is unknown. The service is alive, but the anonymous allowance is tiny. ecosyste.ms (same author, Andrew Nesbitt) covers the same ground with far higher limits, so everkeep should not depend on libraries.io.

### npm downloads

- `https://api.npmjs.org/downloads/point/last-month/get-title-at-url` returned `{"downloads":772,"start":"2026-09-13","end":"2026-10-12","package":"get-title-at-url"}`.
- `https://api.npmjs.org/downloads/range/last-week/get-title-at-url` returned `{"downloads":[{"downloads":0,"day":"2026-10-06"},{"downloads":12,"day":"2026-10-07"},...]}`.
- Answers: "is usage rising or falling" (store the series and compare windows). Keyless.

### pypistats

- `https://pypistats.org/api/packages/pip-audit/recent` returned `{"data":{"last_day":1265624,"last_month":26723596,"last_week":7845566},"package":"pip-audit","type":"recent_downloads"}`. `/overall` and `/python_minor` also exist. Keyless; the site asks for light use (no published number). Mark has one PyPI CLI, so one call per run is enough.

### NuGet (search, registration, flat container)

- Service index: `https://api.nuget.org/v3/index.json`. Resolve resource URLs from it rather than hard-coding them.
- Search, for downloads and owners: `https://azuresearch-usnc.nuget.org/query?q=packageid:RandomNameGeneratorLibrary&prerelease=true&semVerLevel=2.0.0` returned `{"id":"RandomNameGeneratorLibrary","version":"2.3.0","totalDownloads":3894453,"verified":false,"owners":["rogersm0"],"versions":[{"version":"1.0.5.1","downloads":67783,...}]}`. Per-version download counts are included. **`owners` is the publisher-change signal on NuGet.**
- Registration, for publish dates: `https://api.nuget.org/v3/registration5-gz-semver2/randomnamegeneratorlibrary/index.json`. This URL is **gzip-encoded**: curl needs `--compressed`, and Python needs `gzip.decompress` or an `Accept-Encoding` header plus decoding. `items[].items[].catalogEntry` has `version`, `published` ("2026-09-28T12:17:15.567+00:00" for 2.3.0), `listed`, `vulnerabilities` (null when clean), `deprecation`, and `dependencyGroups`. Unlisted versions show `published` as 1900-01-01.
- Flat container, for the version list: `https://api.nuget.org/v3-flatcontainer/randomnamegeneratorlibrary/index.json` returned `{"versions":["1.0.0",...,"2.3.0-beta.1","2.3.0"]}`.
- No release feed. Poll the flat container.

### OpenUPM

- The registry is npm-compatible: `https://package.openupm.com/com.cysharp.unitask` returned `name`, `versions`, `time` (per-version publish timestamps), and `dist-tags` (`latest: 2.5.11`). This gives cooldown dates exactly as on npm.
- Search: `https://package.openupm.com/-/v1/search?text=unitask&size=2` (npm search shape).
- Site API: `https://api.openupm.com/packages/extra` returns **all ~4,077 packages in one JSON object** keyed by name: `{"com.cysharp.unitask":{"stars":11246,"unity":"2018.4","time":1779179911558,"ver":"2.5.11","dl30d":117480}}`. **`dl30d` is the 30-day download count.** Fetch it once per run and cache it.
- `https://api.openupm.com/packages/com.cysharp.unitask` returns build history (`releases[]` with `tag`, `commit`, `state`, `reason`, `publishedVersion`). It answers "did OpenUPM fail to build my tag".
- `https://api.openupm.com/site/info` returned `{"stars":1919,"readyPackageCount":4069}`.
- `https://api.openupm.com/downloads/point/last-month/<pkg>` returned 404, so there is no npm-style downloads route. Use `dl30d`.

### Hacker News (Algolia)

- `https://hn.algolia.com/api/v1/search_by_date?query=osv-scanner&tags=story&hitsPerPage=2` returned `{"nbHits":9,"hits":[{"title":"OSS Scanner","created_at":"2026-10-12T23:19:16Z","points":5,...}]}`. `/search` ranks by relevance. Keyless. Algolia documents 10,000 requests an hour per IP (from earlier docs; not re-read today).
- Answers: "is anyone talking about my package or a competitor". Quote the package name: `query=%22get-title-at-url%22` returned 0 hits.

### Release feeds (Atom and RSS)

- GitHub: `https://github.com/google/osv-scanner/releases.atom` (200, Atom; entries carry `<updated>` and `<title>v2.7.0</title>`). `/tags.atom` also exists. Unauthenticated, no published limit; poll politely. For structured data, `gh api repos/{o}/{r}/releases/latest` is better (Mark's `gh` is authenticated: 5,000 an hour).
- GitLab: `https://gitlab.com/gitlab-org/gitlab-runner/-/releases.atom` (200) and `/-/tags?format=atom` (200).
- Forgejo and Gitea (Codeberg): `https://codeberg.org/forgejo/forgejo/releases.atom` and `/releases.rss` (both 200). Headers: `ratelimit-policy: "baseline";q=2000;w=600`, i.e. 2,000 requests per 10 minutes.
- PyPI: `https://pypi.org/rss/project/pip-audit/releases.xml` (200, RSS 2.0).
- npm and NuGet have no per-package feed. Poll the registry document.

### GitHub dependency graph (bonus, verified)

- `gh api repos/m4bwav/get-title-at-url/dependency-graph/compare/<base>...<head>` returned a JSON array (1,089 changes since 2026-09-01) of `{change_type, manifest, ecosystem, name, version, package_url, scope, vulnerabilities[]}`. This is what `actions/dependency-review-action` uses. It works with Mark's `gh` login on his own repos and includes GitHub Actions as an ecosystem.
- `gh api repos/m4bwav/get-title-at-url/dependabot/alerts?state=open` returned `[]`.

## 2. Vulnerability scanners (local, no account)

### osv-scanner v2

- Current: **v2.7.0, published 2026-10-12** (GitHub releases API). Assets include `osv-scanner_windows_amd64.exe` and `osv-scanner_windows_arm64.exe`. Docs: https://google.github.io/osv-scanner/ (read 2026-10-13).
- Windows install: `winget install Google.OSVScanner`, `scoop install osv-scanner`, the release binary, or `go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest` (Go 1.26.2+). Chocolatey is not listed. It is not installed on Mark's PC yet.
- Scan: `osv-scanner scan source -r <dir> --format json` (`scan source` is the default, so `osv-scanner scan -r <dir>` also works). `--all-packages` adds every package to the JSON. Offline use: `--offline-vulnerabilities --download-offline-databases`.
- Lockfiles: npm `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`; .NET **`packages.lock.json`**, `packages.config`, `deps.json` (not `.csproj`, so NuGet repos need `RestorePackagesWithLockFile=true` for full coverage); Python `requirements.txt`, `poetry.lock`, `uv.lock`, `pdm.lock`, `pylock.toml`, `Pipfile.lock`. Transitive resolution from a manifest exists only for Maven `pom.xml`. GitHub Actions workflows are not listed.
- JSON: `{"results":[{"source":{"path","type":"lockfile"},"packages":[{"package":{"name","version","ecosystem"},"vulnerabilities":[{"id","aliases",...full OSV}],"groups":[{"ids":[...],"max_severity"?}]}]}]}`. Count `groups`, not `vulnerabilities`, because groups merge aliases.
- Exit codes: 0 = clean; 1 = vulnerabilities found; 127 = general error; **128 = no packages found** (treat as "not applicable", not as a failure).
- Guided remediation `osv-scanner fix` is **experimental**: npm `package-lock.json` (`--strategy=in-place`), npm `package.json` (`--strategy=relax`), Maven (`override`). `--format json` writes JSON to stdout. It can run package-manager scripts, so the docs say only use it on trusted projects. It does not reinstall `node_modules`. Not for NuGet or PyPI.

### npm audit and npm audit signatures

- Docs: https://docs.npmjs.com/cli/v11/commands/npm-audit (read 2026-10-13). Local npm here is 11.16.0.
- `npm audit --json` (run on get-title-at-url) returned `{"auditReportVersion":2,"vulnerabilities":{"braces":{"name","severity":"high","isDirect":false,"via":[{"source":1240992,"title","url":"https://github.com/advisories/GHSA-...","severity","cwe","cvss":{"score":7.5},"range":"<=3.0.3"}],"effects":["micromatch"],"range":"*","nodes":["node_modules/braces"],"fixAvailable":{"name":"xo","version":"0.26.1","isSemVerMajor":true}}},"metadata":{"vulnerabilities":{"high":5,"total":5},"dependencies":{"prod":1,"dev":544,...}}}`. `via` holds either advisory objects or strings that name another vulnerable package; walk it to find the root advisory. **Exit 1 when anything is found**; `--audit-level` sets the threshold. `--omit=dev` scopes to runtime dependencies. It posts to `/-/npm/v1/security/advisories/bulk`.
- `npm audit signatures` printed "493 packages have verified registry signatures" and "122 packages have verified attestations". `--json --include-attestations` adds the Sigstore bundles. It needs an installed `node_modules`. Use it as a cheap provenance and tamper check.

### .NET: dotnet package list vs NuGetAudit

- On SDK 10.0.401 (installed), the noun-first `dotnet package list` is the current spelling, and `dotnet list package` still works. **It restores by default** (pass `--no-restore` to skip).
- `dotnet list package --vulnerable --include-transitive --format json` returned `{"version":1,"parameters":"--vulnerable --include-transitive","sources":[...],"projects":[{"path":"..."}]}`, with no `frameworks` key when clean. With findings, each framework lists `topLevelPackages` and `transitivePackages`, each with `vulnerabilities[]` (`severity`, `advisoryurl`) (per the docs; not seen today). **Exit code was 0** either way, so parse the JSON. `--vulnerable`, `--outdated` and `--deprecated` cannot be combined, so make three calls.
- NuGetAudit (https://learn.microsoft.com/en-us/nuget/concepts/auditing-packages, read 2026-10-13): it runs during restore. **`NuGetAuditMode` defaults to `all` when a project targets net10.0 or higher**, otherwise `direct`; if any target framework selects `all`, all of them use it. So Mark's netstandard2.0 + net10.0 libraries already get transitive audit. `NuGetAuditLevel` defaults to `low`. Warnings: NU1900 (source error), NU1901 to NU1904 (low to critical), NU1905 (audit source without data). `auditSources` can point at `https://data.nuget.org/v3/index.json` (vulnerability data only). `dotnet package update --vulnerable` (NuGet 7.0, .NET 10 SDK) upgrades to the first non-vulnerable version. `dotnet nuget why <pkg>` shows the transitive path.
- Recommendation: everkeep calls `dotnet package list --vulnerable --include-transitive --format json` (structured) and leaves NuGetAudit on in the repos as the build-time guard. Run osv-scanner on `packages.lock.json` as a second opinion; it uses OSV, while NuGet uses the GitHub Advisory Database.

### pip-audit

- Repo https://github.com/pypa/pip-audit (read 2026-10-13). Installed and run today in a throwaway venv: **pip-audit 2.10.1**.
- `pip-audit -r requirements.txt -f json --progress-spinner off -o out.json` against `requests==2.25.0` gave exit 1, "Found 24 known vulnerabilities in 3 packages". The JSON top level is **`{"dependencies":[...],"fixes":[...]}`** (the README's array example is out of date). Each dependency has `{"name","version","vulns":[{"id":"PYSEC-2023-74","fix_versions":["2.31.0"],"aliases":["CVE-2023-32681","GHSA-j8r2-6x86-q33q"],"description"}]}`.
- Targets: an environment, `-r requirements.txt`, a project dir (`pyproject.toml`), and `--locked .` for `pylock.*.toml`. `-s osv` switches from the PyPI JSON service to OSV. Exit 0 clean, 1 findings. `--fix --dry-run` reports upgrades.
- Running `uvx pip-audit` timed out on this PC (uv download), while `python -m venv` + `pip install` worked. Note this for the install instructions.
- Lighter alternative with no install: the PyPI JSON API has a top-level `vulnerabilities` array on `https://pypi.org/pypi/<name>/<version>/json` (it is `[]` on the project endpoint for pip-audit). The OSV API (`POST https://api.osv.dev/v1/query` with `{"package":{"name":"lodash","ecosystem":"npm"},"version":"4.17.15"}`) returned 6 vulns with aliases. `POST /v1/querybatch` exists for batches. A GET to `/v1/query` returns 405.

### GitHub Dependabot alerts API

- https://docs.github.com/en/rest/dependabot/alerts (read 2026-10-13): `GET /repos/{owner}/{repo}/dependabot/alerts` (also org and enterprise). Filters: `state`, `severity`, `ecosystem`, `package`, `scope` (development, runtime), `epss_percentage`, `per_page` up to 100. Fields: `number`, `state`, `dependency.package.{ecosystem,name}`, `security_advisory.{ghsa_id,cve_id,severity}`, `security_vulnerability.first_patched_version.identifier`. Headers: `X-GitHub-Api-Version: 2026-03-10`. A classic token needs `security_events` (or `public_repo` for public repositories only). `gh api` works (verified: returned `[]`). For private repos it requires Dependabot alerts to be enabled.

## 3. Outdated dependencies and publish dates

| Ecosystem | Command (JSON) | Verified shape | Exit code |
|---|---|---|---|
| npm | `npm outdated --json` | `{"tsdown":{"current":"0.23.0","wanted":"0.23.1","latest":"0.23.1","dependent","location"}}` | **1 when anything is outdated** (not an error) |
| NuGet | `dotnet package list --outdated --format json` (add `--highest-minor` or `--highest-patch` for in-major) | `projects[].frameworks[].topLevelPackages[]` with `id`, `requestedVersion`, `resolvedVersion`, `latestVersion` (System.Text.Json 10.0.12 to 10.0.13 seen) | 0 |
| NuGet (alt) | `dotnet outdated -o out.json` (`dotnet tool install --global dotnet-outdated-tool`) | JSON by default; `-vl Major/Minor`; `-f` fails on updates; has an MCP server mode | non-zero with `-f` |
| PyPI | `python -m pip list --outdated --format json` | `[{"name":"pip","version":"26.1.2","latest_version":"26.2.1","latest_filetype":"wheel"}]` | 0 |
| OpenUPM | none; read `Packages/manifest.json` plus `scopedRegistries`, then compare with `dist-tags.latest` from `package.openupm.com/<name>` | npm document | n/a |
| Claude Code plugins | none; compare `plugin.json` `version` and pinned Python and requirements against PyPI, and workflow `uses:` against `gh api repos/{a}/releases/latest` | | |

Publish date per version, for the cooldown rule (no auto-merge under 3 days, 7 to 14 for majors):

- npm: the full document `https://registry.npmjs.org/<name>` has `time[<version>]` (get-title-at-url 3.0.0 = `2026-09-25T15:42:58.478Z`). The abbreviated document (`Accept: application/vnd.npm.install-v1+json`) has **no `time` and no `_npmUser`** (keys: `name`, `dist-tags`, `versions`, `modified`), so cooldown and publisher checks need the full document.
- NuGet: the registration `catalogEntry.published`.
- PyPI: `https://pypi.org/pypi/<name>/json`, `urls[].upload_time_iso_8601` for the latest version (pip-audit 2.10.1 = `2026-06-10T22:17:00.309492Z`) and `releases[<ver>][].upload_time_iso_8601` for others; also `yanked`.
- OpenUPM: `time[<version>]` from the npm-compatible registry.
- deps.dev `publishedAt` is a cross-ecosystem fallback (NuGet included).

## 4. Toolchain EOL data

### endoflife.date API v1

- Spec: `https://endoflife.date/docs/api/v1/openapi.yml` (version 1.2.1; the `/docs/api/v1/` page itself is a Swagger UI that does not render for WebFetch). Paths: `/products`, `/products/full`, `/products/{product}`, `/products/{product}/releases/{release}`, `/products/{product}/releases/latest`, `/categories`, `/tags`, `/identifiers`.
- Response: `{"schema_version":"1.2.1","generated_at","result":{"name","releases":[{"name","label","releaseDate","isLts","ltsFrom","isEoas","eoasFrom","isEol","eolFrom","isEoes","eoesFrom","isMaintained","latest":{"name","date","link"}}]}}`. The old v0 `https://endoflife.date/api/nodejs.json` still answers (`cycle`, `lts`, `eol`, `support`).
- Products verified (200): `nodejs`, `dotnet`, `python`, `unity`, `visual-studio`. `github-actions-runner` returned 404.

### Dates on 2026-10-13 (from the v1 API, cross-checked)

- **Node.js** (also from `https://raw.githubusercontent.com/nodejs/Release/main/schedule.json`): 20 EOL 2026-04-30; 22 maintenance since 2025-10-21, EOL **2027-04-30**; 24 LTS, maintenance from **2026-10-20**, EOL 2028-04-30; 25 EOL 2026-06-01; 26 current (26.11.1), LTS from **2026-10-28**, EOL 2029-04-30; **27: alpha 2026-10-28, 27.0.0 2027-04-22, maintenance 2027-10-20, EOL 2030-04-30**. From 27 there is one major a year, every release becomes LTS, and the project asks library authors to add the alpha to CI (https://nodejs.org/en/blog/announcements/evolving-the-nodejs-release-schedule, read 2026-10-13).
- **.NET**: 8 (LTS, 8.0.31) and 9 (STS, 9.0.20) both EOL **2026-11-10**; 10 (LTS, 10.0.12 runtime) EOL 2028-11-14; 11 is STS, GA scheduled 2026-11-10, end date not yet published (24-month STS policy implies about November 2028; estimate). Local SDKs: 9.0.317 and 10.0.401.
- **Unity**: 6000.0 (6.0 LTS) EOL **2026-10-16** (Unity's own page says "October 2026"; the day comes from endoflife.date), latest 6000.0.84f1; 6000.3 (6.3 LTS, released 2025-12-04) EOL **2027-12-04**, extended support (Enterprise and Industry) to 2028-12-04, latest 6000.3.26f1; 6000.6 is the current update release (6000.6.5f1); 6000.4 and 6000.5 are already EOL.
- **Python**: **3.10 EOL 2026-10-01** (already past); 3.11 EOL 2027-10-31; 3.12 2028-10-31; 3.13 security-only since 2026-10-01, EOL 2029-10-31; 3.14 (3.14.8) EOL 2030-10-31; **3.15.0 released 2026-10-09**. pip-audit needs 3.10+.

### GitHub Actions

- Node 20 on runners (https://github.blog/changelog/2026-09-23-deprecation-of-node-20-on-github-actions-runners/, read 2026-10-13): Node 24 became the default on 2026-06-16. `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true` kept Node 20 only until removal on **2026-09-23**. `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` was the early opt-in. Node 24 does not run on macOS 13.4 or lower, and ARM32 self-hosted runners lose support. So any `using: node20` action in Mark's workflows is now broken on hosted runners. His **self-hosted runners** depend on their runner version; check that they have auto-updated.
- Latest majors (GitHub releases API, 2026-10-13): actions/checkout **v7.0.1** (`runs: using: node24`), actions/setup-node **v7.1.0** (2026-10-08), actions/setup-dotnet **v6.0.0**, actions/setup-python **v7.0.0**, actions/upload-artifact **v7.0.2**, actions/cache **v6.1.0**, github/codeql-action bundle 2.27.2, ossf/scorecard-action **v2.5.0** (2026-10-12), pypa/gh-action-pypi-publish **v1.14.2**, NuGet/login **v1.2.0**.
- everkeep check: parse `.github/workflows/*.yml` `uses:` lines (SHA plus `# vX` comment), fetch each action's `action.yml` at that ref, and flag `using: node20` or older, plus any major behind latest.

## 5. Lockfile-diff supply-chain checks

### npm package-lock.json (lockfileVersion 3)

Field meanings from https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json (read 2026-10-13): `packages` is keyed by path (`node_modules/a/node_modules/b`); `resolved` is the tarball URL, a git URL with commit SHA, or a link target; `integrity` is a sha512 or sha1 SRI; `hasInstallScript` means the package has a `preinstall`, `install` or `postinstall` script; `hasShrinkwrap`, `link`, `dev`, `optional`, `devOptional`, `inBundle`; `bin`, `license`, `engines` and dependencies are copied from package.json. Version 1 = npm 5 and 6, version 2 = npm 7 and 8, version 3 = npm 9+.

Diff algorithm (stdlib `json` plus `git show <base>:package-lock.json`):

1. Build `{path: entry}` for base and head; derive the package name from the last `node_modules/` segment (or the entry's `name` for aliases).
2. **New package names** (not just new paths): escalate every transitive name that did not exist before, and run deps.dev `:similarlyNamedPackages` on it.
3. **Source changes**: escalate when `resolved` does not start with `https://registry.npmjs.org/` (git+, github:, http:, file:, tarball URLs) or when its host changed between base and head.
4. **Integrity changes for the same name and version**: this should never happen; escalate.
5. **`hasInstallScript: true`** newly appearing, on a new package or an upgraded one; escalate. `binding.gyp` does not appear in the lockfile: npm runs `node-gyp rebuild` as an implicit install script when a package ships `binding.gyp` and no install script, and `hasInstallScript` is set in that case (from npm behaviour; not re-verified today). Confirm by listing tarball files (`npm pack <pkg>@<v> --dry-run --json` or the registry `dist.fileCount`).
6. **Publisher change**: for each upgraded package, fetch the full registry document and compare `versions[old]._npmUser` with `versions[new]._npmUser` and the `maintainers` arrays. Verified shape for get-title-at-url 3.0.0: `_npmUser: {"name":"GitHub Actions","email":"npm-oidc-no-reply@github.com","approver":{"name":"markrogers",...},"trustedPublisher":{"id":"github","oidcConfigId":"oidc:..."}}`. **Trusted publishing shows as `_npmUser.trustedPublisher`, and staged publishing shows the human `approver`.** Flag "was trusted publishing, now is not" and "new maintainer" as high signals. `dist.attestations` present or absent is a provenance signal.
7. `npm diff --diff=pkg@old --diff=pkg@new --diff-name-only` downloads both tarballs and lists changed files without installing (the docs do not say whether it runs scripts; it should not, since it only fetches tarballs).

### NuGet packages.lock.json

Shape verified on JsonPrettyPrinterPlus: `{"version":1,"dependencies":{".NETStandard,Version=v2.0":{"System.Memory":{"type":"Direct","requested":"[4.6.3, )","resolved":"4.6.3","contentHash":"...","dependencies":{...}}},"net10.0":{...}}}`. `type` is `Direct`, `Transitive`, `Project` or `CentralTransitive`. Diff per target framework: new names, `resolved` changes, and **`contentHash` changing for the same version** (escalate). There is no source URL in the file (sources live in nuget.config, so diff that too). Publisher check: search API `owners` before and after. Check `verified` (reserved prefix).

### Existing tools

- **lockfile-lint** (https://github.com/lirantal/lockfile-lint, read 2026-10-13): `npx lockfile-lint --path package-lock.json --type npm --allowed-hosts npm --validate-https`. It checks hosts, HTTPS, schemes and package-name to URL integrity (the README excerpt named only hosts and HTTPS). npm and yarn only; pnpm is out of scope by design. Good as a one-shot policy check; everkeep's own diff covers more.
- **Socket CLI** (https://docs.socket.dev/docs/socket-cli): `npm install -g socket`. Most commands need an API token (`socket login` or `SOCKET_CLI_API_TOKEN`); `socket scan create`, `socket ci`, `socket package score npm lodash`, `--json`. Not keyless, so it is optional in everkeep.
- **npm diff** (above), **deps.dev** (provenance, advisories, similar names), **GitHub dependency-graph compare** (verified above; the dependency-review-action data source).

## 6. Claude Code scheduling and headless safety

Sources: https://code.claude.com/docs/en/headless, /cli-reference, /permissions, /scheduled-tasks, /routines, /security (all read 2026-10-13).

### Narrow `claude -p` runs

- `--allowedTools` uses permission-rule syntax; the trailing ` *` means prefix match, so `Bash(git diff *)` matches `git diff ...` but not `git diff-index` (the space matters). Example from the docs: `--allowedTools "Bash(git diff *),Bash(git log *),Bash(git status *),Bash(git commit *)"`.
- `--tools "Read,Grep,Glob"` **restricts which built-in tools exist** (allowedTools only auto-approves). `--tools` does not touch MCP tools; add `--disallowedTools "mcp__*"`.
- `--disallowedTools`: a bare name removes the tool; a scoped rule (`Bash(rm *)`) denies matching calls only, "as written".
- `--permission-mode`: `default` (alias `manual`), `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`. **`dontAsk` denies everything that would prompt**, except read-only actions and what the allow rules cover, which suits locked-down runs. A `-p` run without a mode can start in `auto`, so always pass one.
- `--permission-prompts none` (v2.1.259+): nothing waits on a host; prompts are denied and Claude is told not to retry; denials are listed in `permission_denials`.
- `--max-turns N`, `--max-budget-usd 5.00`, `--output-format json` (includes `total_cost_usd`), and `--json-schema '<schema>'` (result in `structured_output`) give machine-checkable output. `--no-session-persistence` keeps nothing on disk.
- `--bare`: skips hooks, skills, commands, subagents, plugins, MCP, auto memory and CLAUDE.md; recommended for scripts and "will become the default for -p". **It needs `ANTHROPIC_API_KEY` or `apiKeyHelper` in `--settings`; it never reads the subscription OAuth login.** For Mark's subscription use without an API key, use `--setting-sources user` plus `--strict-mcp-config` instead.
- `--restricted` (v2.1.248+): removes Bash, code execution and WebFetch unless named in `--tools`, confines file tools to the working dirs, loads only managed and `--settings` settings, and refuses `bypassPermissions`. This is the strongest flag for reading untrusted repos.
- **What a repository can run under `-p` (the folder is never trusted):** settings-file **hooks**, the `env` block, helper commands, a project skill's hooks and `allowed-tools` are **used**; `.mcp.json` servers are **connected without asking**; `permissions.allow` from `.claude/settings.json` is **not** used. To keep them out: `--setting-sources user`, `--bare`, `--settings '{"disableAllHooks": true}'` (a user-settings value alone can be overridden by project settings), and `disabledMcpjsonServers`.
- Suggested everkeep invocation for the research-note step (reads only; the Python CLI does the network calls):
  `claude -p --setting-sources user --strict-mcp-config --settings '{"disableAllHooks":true}' --tools "Read,Grep,Glob,Write" --allowedTools "Read,Grep,Glob,Write(ai-docs/research/**)" --disallowedTools "mcp__*" --permission-mode dontAsk --permission-prompts none --max-turns 30 --max-budget-usd 2 --output-format json "<prompt>"`. Run it from everkeep's own folder (`--add-dir` for the target repo grants file access but does not load most of its `.claude/` config), never from inside a PR checkout. The `Write(path)` rule form is per the permission-rule syntax; test it before relying on it.

### Scheduling options

| | Cloud routine (`/schedule`) | Desktop scheduled task | `/loop` |
|---|---|---|---|
| Runs on | Anthropic cloud VM, fresh clone | Mark's PC | Mark's PC, inside an open session |
| Minimum interval | 1 hour | 1 minute | 1 minute |
| Survives restart | yes | yes | restored on `--resume`; recurring tasks expire after **7 days** |
| Local files | no | yes | yes |
| Permissions | autonomous, no mode picker; all included connectors usable with writes | per task | inherits session |

- Routines (research preview): Pro, Max, Team and Enterprise; schedule, API (`/fire` with a bearer token, beta header `experimental-cc-routine-2026-04-01`) and GitHub triggers (pull_request, release). Limits: 100 scheduled runs an hour per account; 30 Run-now or API fires an hour per routine. Pushes go to `claude/`-prefixed branches; the GitHub proxy rejects tag pushes and branch deletions. The default "Trusted" network allows only an allowlist of package registries and dev domains (api.osv.dev, ecosyste.ms and deps.dev may need adding). Fire `text` arrives wrapped in `<routine-fire-payload>` as untrusted data. `/schedule` needs a claude.ai login, not an API key.
- For everkeep (local Windows repos, private repos built on self-hosted runners, the vault): a **Windows Task Scheduler job running the stdlib CLI**, like repo-traffic, is the main route. Use a Desktop scheduled task only if the agent step must run on a schedule. Cloud routines suit public-repo-only checks.

### Prompt injection guidance (Anthropic)

- From /security: avoid piping untrusted content directly to Claude; review commands; run in VMs for untrusted work; WebFetch passes pages through a separate summarising model call; `curl` and `wget` are not auto-approved; `-p` shows no trust dialog. Routines and cloud sessions run in isolated VMs, keep GitHub credentials outside the VM, and push through a proxy.
- Rules for everkeep that follow from this and from the landscape file's rules 4 and 5: the CLI gathers GitHub text (issues, PR bodies, release notes, changelogs) into files marked as data; the agent step gets `--tools` without Bash or WebFetch, so injected text has nothing dangerous to call; outputs are limited to `ai-docs/research/**` and the run never pushes, comments or merges.

## What the CLI should call, per ecosystem

| Ecosystem | Outdated | Vulnerabilities | Publish date (cooldown) | Supply chain | Usage and research | Toolchain EOL |
|---|---|---|---|---|---|---|
| npm (TS/ESM libs) | `npm outdated --json` (exit 1 = outdated) | `npm audit --json` + `osv-scanner scan source -r . --format json`; `npm audit signatures` | registry full doc `time[v]` | package-lock diff (names, `resolved` host, integrity, `hasInstallScript`), `_npmUser`/`trustedPublisher`/`maintainers` diff, deps.dev `:similarlyNamedPackages` | api.npmjs.org point/range, ecosyste.ms package + dependents, deps.dev `:dependents`, HN Algolia | endoflife `nodejs`; `engines.node` floor vs 22/24/26; Node 27 alpha in CI |
| NuGet (netstandard2.0 + net10.0) | `dotnet package list --outdated --format json` | `dotnet package list --vulnerable --include-transitive --format json` + osv-scanner on `packages.lock.json`; NuGetAudit in the build | registration `catalogEntry.published` (gzip) | packages.lock.json diff (contentHash, new names), nuget.config diff, search `owners` diff | NuGet search `totalDownloads` and per-version downloads, ecosyste.ms nuget.org | endoflife `dotnet` (8 and 9 end 2026-11-10) |
| PyPI (one CLI) | `pip list --outdated --format json` in the project venv | `pip-audit -f json` (top level `dependencies`/`fixes`) or OSV `querybatch`; osv-scanner on `uv.lock`/`pylock.toml` | PyPI JSON `upload_time_iso_8601` | new names in lock diff; deps.dev similar names | pypistats `recent`, PyPI RSS | endoflife `python` (3.10 EOL 2026-10-01) |
| Unity on OpenUPM | `package.openupm.com/<name>` `dist-tags` vs `manifest.json` | OSV has no Unity ecosystem; check the package's own NuGet or npm deps if any | OpenUPM `time[v]` | OpenUPM build state (`api.openupm.com/packages/<name>`) | `api.openupm.com/packages/extra` `dl30d` (one call) | endoflife `unity` (6.0 LTS ends 2026-10-16) |
| Claude Code plugins (skills, Python) | compare pinned versions to PyPI and npm; `plugin.json` version vs marketplace | osv-scanner on any lockfile or requirements | as above | review `.claude/`, `.mcp.json`, hooks changes as human decisions | GitHub release Atom, ecosyste.ms repos/issues | Python floor via endoflife |
| GitHub Actions (all repos) | `uses:` vs `gh api repos/{a}/releases/latest` | Dependabot alerts API; dependency-graph compare (`ecosystem: actions`) | release `published_at` | SHA pinning; `using: node20` in `action.yml` = broken since 2026-09-23 | | runner version on self-hosted runners |

## Not verified

- osv-scanner JSON field `max_severity` inside `groups` (not on the output page; check with a real run after installing v2.7.0); whether osv-scanner reads GitHub Actions workflows.
- `dotnet package list --vulnerable` JSON shape with actual findings (only the clean shape was seen).
- That npm sets `hasInstallScript` for packages with `binding.gyp` and no install script (from npm behaviour, not re-read).
- libraries.io anonymous rate-limit window (only the header `limit: 10` was seen); its 2026 maintenance status.
- HN Algolia rate limit (10,000 an hour per IP is from older docs).
- pypistats published limits; OSS Insight limits (no docs page).
- deps.dev quotas (the docs state none) and the PurlLookupBatch path.
- dotnet-outdated latest version and .NET 10 support beyond the README's file-based-app note.
- lockfile-lint latest release and full validator list (the README excerpt named only hosts and HTTPS).
- Socket CLI free tier.
- .NET 11 end of support (unpublished; about November 2028 is an estimate).
- Unity 6.0's exact end day (2026-10-16 is from endoflife.date; Unity says "October 2026").
- Whether the `Write(ai-docs/research/**)` allow-rule form works as intended under `dontAsk`; whether `--restricted` blocks Write.
- Whether the maintainer's self-hosted runners have auto-updated past Node 20 removal.
