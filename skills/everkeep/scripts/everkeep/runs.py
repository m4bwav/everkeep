"""Resumable multi-repo runs (design section 2). The target list is frozen at start; each repo ends done, failed,
skipped or held; an interruption (Ctrl+C, a rate limit, a context limit) loses at most the repo in flight, which stays
pending. A repo showing something unexpected stops the run from widening: the rest are held until the user has seen it."""

from __future__ import annotations

import os

from . import duties as D
from . import gaps as G
from . import prs as P
from . import scope as S
from .providers.base import ProviderNotSupported, RateLimited
from .providers.registry import get_provider, parse_repo_arg
from .util import EverkeepError, iso, now

ALL_DUTIES = ("prs", "vulns", "deps", "gaps", "kb", "research")


def process(run: dict, store, max_repos: int | None = None, deep: bool = False, throwaway: bool = False,
            echo=print) -> dict:
    cfg = store.config()
    registry = D.vault_registry(cfg) if "kb" in run["duties"] else None
    interrupt_after = int(os.environ.get("EVERKEEP_INTERRUPT_AFTER", "0") or 0)  # tests and the Phase 3 drill
    done = 0
    for r in run["repos"]:
        if r["status"] != "pending":
            continue
        if run.get("stopped"):
            store.mark(run, r["id"], "held", "run stopped widening: " + run["stopped"]["finding"])
            continue
        if max_repos is not None and done >= max_repos:
            break
        if interrupt_after and done >= interrupt_after:
            raise KeyboardInterrupt
        rid_text = r["id"]
        echo(f"[{run['id']}] {rid_text} ...")
        try:
            rid = parse_repo_arg(rid_text, hosts=cfg.get("hosts"))
            entry = S.describe(get_provider(rid, cfg).get_repo(rid), store)
            facts: dict = {"repo": rid_text, "tier": entry["tier"], "tier_reason": entry["tier_reason"],
                           "ecosystems": entry["ecosystems"], "packages": entry["packages"], "clone": entry["clone"],
                           "visibility": entry["visibility"], "gathered": iso(now()), "duties": {}}
            unexpected: list[str] = []
            for duty in run["duties"]:
                if duty == "prs":
                    facts["duties"]["prs"] = P.gather_repo(entry, cfg)
                    unexpected += [u for f in facts["duties"]["prs"] for u in f.get("unexpected", [])]
                elif duty == "vulns":
                    facts["duties"]["vulns"] = D.vulns(entry, store, throwaway)
                elif duty == "deps":
                    facts["duties"]["deps"] = D.deps(entry, store)
                elif duty == "gaps":
                    facts["duties"]["gaps"] = G.audit(entry, store, deep)
                elif duty == "kb":
                    facts["duties"]["kb"] = D.kb(entry, store, registry)
                elif duty == "research":
                    facts["duties"]["research"] = D.research(entry, store)
            store.save_facts(run, rid_text, facts)
            st = store.repo_state(rid_text)
            for duty in run["duties"]:
                st.setdefault("duties", {})[duty] = {"last_run": iso(now()), "run": run["id"]}
            store.save_repo_state(rid_text, st)
            store.mark(run, rid_text, "done")
            if unexpected:
                run["stopped"] = {"repo": rid_text, "finding": "; ".join(unexpected[:3]), "at": iso(now())}
                store.save_run(run)
                echo(f"[{run['id']}] STOPPED WIDENING at {rid_text}: {run['stopped']['finding']}")
        except ProviderNotSupported as e:
            store.mark(run, rid_text, "skipped", str(e))
        except RateLimited as e:
            store.mark(run, rid_text, "pending", f"rate limited: {e}")
            raise
        except EverkeepError as e:
            store.mark(run, rid_text, "failed", str(e)[:300])
        done += 1
    return run


def summary(run: dict) -> dict:
    counts: dict[str, int] = {}
    for r in run["repos"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts


def resume(run: dict, store, failed: bool, release_held: bool) -> dict:
    for r in run["repos"]:
        if failed and r["status"] == "failed":
            r["status"], r["reason"] = "pending", "retry after failure: " + r["reason"]
        if release_held and r["status"] == "held":
            r["status"], r["reason"] = "pending", ""
    if release_held:
        run["stopped"] = None
    store.save_run(run)
    return run


def first_pending(run: dict) -> str | None:
    return next((r["id"] for r in run["repos"] if r["status"] == "pending"), None)


__all__ = ["ALL_DUTIES", "process", "resume", "summary", "first_pending"]
