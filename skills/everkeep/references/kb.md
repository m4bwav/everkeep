# Knowledge bases

Read when `KEEP kb` reports a repo with no `ai-docs/` or one not registered in the vault. Design: [design.md](../../../ai-docs/plans/design.md) section 9, duty 5.

## Setting one up

everkeep does not write knowledge bases itself; everlast does. `KEEP kb` prints the command:

    python <everlast>/scripts/everlast.py project register <clone> --mode repo|excluded --sync push|pr|off

- `repo` mode commits `ai-docs/` with the project; `excluded` keeps it in the vault and junctions it in (shared repos, work repos, and private repos when the overlay says `kb_private: excluded`).
- The overlay's `kb_sync` picks the sync mode; the plugin default is `pr`.
- Without everlast installed (overlay `everlast` path missing), report "not checked" and the everlast-setup skill as the way to get it.

A new knowledge base starts with the build and test commands that work, verified once by running them. Written build instructions lifted agent success on dotnet/runtime from 38 to 69 percent.

## Each sweep

Append one log entry per repo touched: what changed (merged, closed, fixed), what was decided and why, what waits for the maintainer. One entry per sweep, not one per PR. In mode repo the entry goes through the repo's normal PR rules like any other change.

## No clone

`KEEP kb` needs a local clone to look for `ai-docs/` (the overlay's `clones` map or `clone_roots`). A repo with none is "no clone": say so, and ask before cloning anything permanent.

Related: builds on [design.md](../../../ai-docs/plans/design.md).
