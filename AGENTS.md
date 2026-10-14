# AGENTS.md

Rules for any AI agent (Claude Code, Copilot, Cursor, Codex, Gemini CLI) working in this repository. `CLAUDE.md` imports this file and `.github/copilot-instructions.md` points here.

## What this is

A cross-agent plugin with one skill, `skills/everkeep/`: SKILL.md (scope, duties, the rules in short), `references/` (one file per duty plus providers, safety and schedule), the CLI `scripts/keep.py` with its package `scripts/everkeep/` (providers behind one interface, classification, lockfile diffs, act, runs, digest), public comment templates in `templates/comments/`, and the evergreen companions (RESEARCH, CHANGELOG, LEARNINGS, TESTS, MAINTENANCE, `evergreen.json`, `evals/evals.json`). Unit tests and fixtures are in `tests/`; the size budget is `scripts/size_check.py`. Design, research, decisions and the log are under `ai-docs/` (start with `ai-docs/HANDOFF.md`; the design is `ai-docs/plans/design.md`).

## Rules

- The CLI is standard-library Python 3.10 or newer, runs on Windows, macOS and Linux, and has no third-party imports (`scripts/size_check.py` fails CI on any). Output is UTF-8 with LF.
- Every hosting call goes through `scripts/everkeep/providers/`; nothing above that interface may call `gh` or a host API. `tests/test_seam.py` runs the duties with `gh` off PATH to prove it. A new host is one adapter file plus a row in `references/providers.md` (see `ai-docs/plans/providers-roadmap.md`).
- Nothing writes to a host without `--apply`, and only `act` writes. Guards are re-checked at the moment of acting. Public comments come only from `templates/comments/` with slots filled from facts the CLI computed and reduced to safe characters; never from PR text.
- A change to a decision rule changes `classify.py` and its test in `tests/test_classify.py` together, and is logged in `skills/everkeep/CHANGELOG.md` with its reason.
- Run `python -m unittest discover -s tests -t tests` and `python scripts/size_check.py` before committing. Fixtures are public Dependabot diffs or invented data: never a private repository's name or content.
- The skill is an evergreen unit. Before editing it read `skills/everkeep/evergreen.json`; if `next_due` has passed or `contradiction` is set, say so and refresh after the task (`evergreen-refresh`). Lessons from real repos go to `LEARNINGS.md` with a code name.
- A release bumps the version in `.claude-plugin/plugin.json`, `plugin.json`, `VERSION` in `scripts/everkeep/__init__.py`, `metadata.version` in SKILL.md and `version` in `evergreen.json` together, then tags `vX.Y.Z` and publishes a GitHub Release with the CHANGELOG entry as notes. Tagging and releasing need the maintainer's go-ahead.
- No top-level `bin/` folder (Cowork refuses plugins with one).
- Prose people read (README, SKILL.md, references) is checked with the everwrite checker when it is available: `python <everwrite>/scripts/tells.py <files>`, zero strong findings.
- This is a public repository. Nothing in it names a person other than the author credit, a machine, an absolute path on someone's machine, a private project, or a credential. The maintainer's own settings live in a private overlay outside the repository (`~/.everkeep/overlay`).
- No AI attribution anywhere: no Co-Authored-By trailers, no "generated with" lines in commits, pull requests, releases or files.

## everlast (session knowledge, load on demand)

- `ai-docs/INDEX.md` lists what past sessions learned here (solutions with verified commands, decisions with reasons, plans). At the start of a task, scan it and open only the entries whose title or tags match; no line matches: `everlast.py search "<key terms>"` before concluding nothing was recorded. Read `ai-docs/HANDOFF.md` when continuing unfinished work (everlast-resume skill).
- Before acting on an entry marked `(recheck due)`, run `everlast.py recheck <entry>`, re-run its Verified-by command only when that is read-only or safe (a build, a test, a version query), then record `everlast.py verify <entry>` or `verify <entry> --failed "what broke"`; a fix that changed is superseded, never reused blindly.
- Before finishing a task that hit a dead end, verified a non-obvious command, made a design choice, or taught you something about the user, record it (everlast-capture skill, or `everlast.py note` / `handoff`); rewrite `HANDOFF.md` when work is left unfinished. Say "nothing to record" when that is true.
- Anything naming a person, an internal host or name, a credential, or an opinion about people goes to the private sidecar (`--private`), never here. Lessons about the user or this machine go to the user tier (`--user`).
- Rules go in this file, system layout in CODEMAP.md; the doc set holds only what could not be re-derived from the code in a minute.
- Link documents together with relative markdown links: every markdown folder is reachable from an index whose lines say when to read each file (`ai-docs/INDEX.md` is generated from frontmatter; give entries a one-line `summary`), and an entry links the entries it relates to on a typed `Related:` line (`supersedes`, `contradicts`, `builds on`, `see also`). The set then reads as a graph for people in Obsidian and for agents alike. No wikilinks in the repo.
