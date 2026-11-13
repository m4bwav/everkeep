"""Delivery numbers per repo (Accelerate, ch. 2 and 4): PR lead time, how long the default branch has been red,
release age and unreleased commits, the fix-release share, flaky checks and stale branches. Report only: numbers
for one repo at a time, never a ranking and never the book's survey thresholds. Pure functions over the raw facts
a provider's delivery() returns, so the tests need no host."""

from __future__ import annotations

import re
from statistics import median

from .util import day, parse_time

BOT_PREFIXES = ("dependabot/", "renovate/", "snyk-", "pre-commit-ci")


def _days(a, b) -> float:
    return (b - a).total_seconds() / 86400


def _minor(tag: str):
    m = re.match(r"^\D*(\d+)\.(\d+)\.\d+$", tag or "")
    return m.groups() if m else None


def compute(raw: dict, today, stale_days: int = 90, fix_days: int = 3) -> dict:
    out: dict = {}
    lead = [_days(parse_time(c), parse_time(m)) for c, m in raw.get("merged_prs", []) if c and m]
    out["pr_median_hours"] = round(median(lead) * 24, 2) if lead else None
    out["pr_count"] = len(lead)
    # Runs newest first. The default branch is red while its newest completed run of any workflow failed;
    # red since = the oldest failure in that workflow's current unbroken failing streak.
    runs = sorted(raw.get("runs", []), key=lambda r: r["created"], reverse=True)
    main = [r for r in runs if r.get("branch") == raw.get("default_branch") and r.get("conclusion")]
    red = {}
    for wf in dict.fromkeys(r["workflow"] for r in main):
        streak = []
        for r in (x for x in main if x["workflow"] == wf):
            if r["conclusion"] not in ("failure", "timed_out", "startup_failure"):
                break
            streak.append(r["created"])
        if streak:
            red[wf] = streak[-1]
    out["red_since"] = day(parse_time(min(red.values()))) if red else None
    out["red_workflows"] = sorted(red)
    # Flaky: a check that failed and then passed on the same commit (a re-run attempt that passed, or two runs).
    seen: dict = {}
    for r in runs:
        seen.setdefault((r["workflow"], r["sha"]), set()).add("pass" if r.get("conclusion") == "success" else
                                                              "fail" if r.get("conclusion") == "failure" else "")
        if r.get("attempt", 1) > 1 and r.get("conclusion") == "success":
            seen[(r["workflow"], r["sha"])].add("fail")
    out["flaky"] = sorted({wf for (wf, _), s in seen.items() if {"pass", "fail"} <= s})
    rel = sorted((parse_time(t), tag) for tag, t in raw.get("releases", []) if t)
    if rel:
        out["release_age_days"] = int(_days(rel[-1][0], today))
        out["last_release"] = rel[-1][1]
        # A fix release: the next release is a patch bump of the same major.minor, out within fix_days.
        quick = sum(1 for (a, x), (b, y) in zip(rel, rel[1:])
                    if _days(a, b) <= fix_days and _minor(x) and _minor(x) == _minor(y))
        out["fix_release_share"] = f"{quick}/{len(rel) - 1}" if len(rel) > 1 else None
    out["unreleased_commits"] = raw.get("unreleased_commits")
    heads = set(raw.get("open_pr_heads", []))
    out["stale_branches"] = sorted(n for n, t in raw.get("branches", [])
                                   if n not in heads and not n.startswith(BOT_PREFIXES) and t
                                   and _days(parse_time(t), today) > stale_days)
    return out


def line(d: dict) -> str:
    parts = []
    if d.get("pr_median_hours") is not None:
        m = d["pr_median_hours"]
        took = f"{round(m / 24, 1)} d" if m >= 24 else f"{m} h" if m >= 1 else f"{round(m * 60)} min"
        parts.append(f"PR open to merge median {took} ({d['pr_count']} PRs)")
    if d.get("last_release"):
        parts.append(f"last release {d['last_release']} {d['release_age_days']} d ago"
                     + (f", {d['unreleased_commits']} commits since" if d.get("unreleased_commits") is not None else ""))
    if d.get("fix_release_share"):
        parts.append(f"releases followed by a patch release within days: {d['fix_release_share']}")
    if d.get("red_since"):
        parts.append(f"default branch red since {d['red_since']} ({', '.join(d['red_workflows'][:3])})")
    if d.get("flaky"):
        parts.append("flaky: " + ", ".join(d["flaky"][:4]))
    return "; ".join(parts) or "no merged PRs, releases or runs seen"
