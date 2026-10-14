"""Public text everkeep posts: the sticky verdict comment and the closing comments. Everything comes from a template
in templates/comments/ with slots filled from facts the CLI computed, reduced to safe characters; nothing is copied
from a PR's own text (GitLost leaked a private README through a comment an agent wrote freely)."""

from __future__ import annotations

import re
from pathlib import Path

from . import VERSION
from .util import collapse_reasons, day, now, parse_time

MARKER = "<!-- everkeep:verdict -->"
TEMPLATES = Path(__file__).resolve().parents[2] / "templates" / "comments"
LEARN_NOTE = "everkeep is in learning mode; reply on this PR or tell the agent if this call is wrong."
RULES = {
    "issue-first": ("CONTRIBUTING.md", "changes like this one start with an issue that the maintainer accepts.",
                    "an issue describing the problem first, then a small pull request that fixes it."),
    "ai-policy": ("CONTRIBUTING.md", "pull requests must be explained and tested by the person who opens them.",
                  "a smaller change you can explain line by line, with a test that fails without it."),
    "no-churn": ("CONTRIBUTING.md", "unrequested refactors and formatting changes are not accepted.",
                 "a fix for a real bug or an accepted issue."),
    "spam": ("CONTRIBUTING.md", "pull requests opened to pad contribution counts are closed.",
             "a change that fixes something you ran into."),
}
_UNSAFE = re.compile(r"[^A-Za-z0-9 .,:;()/_+@#'=\-]")


def public(text: str, cap: int = 200) -> str:
    """A reason line made safe for a public comment: no markup, no links, no characters that could carry formatting."""
    return _UNSAFE.sub("", text or "").strip()[:cap]


def _template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def footer(learn: bool) -> str:
    base = f"everkeep {VERSION}, {day(now())}."
    return f"{base} {LEARN_NOTE}" if learn else base


def _reason_lines(facts: dict) -> list[str]:
    reasons = facts["classification"]["reasons"]
    if not facts.get("bot"):
        # A human PR's paths and check names are the author's own text: keep only the rule each reason came from.
        reasons = [r.split(":", 1)[0] for r in reasons]
    return [f"- {public(r)}" for r in collapse_reasons(reasons) if public(r)]


def verdict_body(facts: dict, verdict: str, learn: bool, extra: str = "") -> str:
    c = facts["classification"]
    until = parse_time(c.get("hold_until"))
    high = facts.get("tier") in ("high", "shared")
    would = "Would " if learn else ""
    if verdict == "hold":
        if until:
            headline = f"Holding until {day(until)}."
            nxt = ("After that date it goes to the maintainer's review list: this repo always gets a human review."
                   if high else "If checks stay green, everkeep merges it on the first run after that date. "
                                "Merge it sooner by hand if you need it.")
        else:
            headline = "Holding for now."
            nxt = "everkeep looks again on its next run."
    elif verdict == "fix":
        headline = "Checks did not pass; this needs a fix before anything else."
        from .classify import FIX_RECIPES
        recipe = FIX_RECIPES.get(c.get("fix_recipe") or "")
        after = {"merge-candidate": "Once the fix is green, every rule for merging holds.", "escalate":
                 "Once the fix is green it still goes to the maintainer: " + "; ".join(public(r, 160) for r in collapse_reasons(c.get("after_fix_reasons") or [])[:3]) + "."}
        nxt = ((f"Known fix: {public(recipe['how'])}. " if recipe else "") + ("Would push" if learn else "everkeep pushes")
               + " the smallest mechanical fix to this branch, then the PR goes back through the rules. "
               + after.get(c.get("after_fix") or "", "If no fix works, it goes to the maintainer's review list."))
    elif verdict == "escalate":
        headline = "Waiting for the maintainer's review."
        nxt = "Assigned to the maintainer and labelled needs-review." if not learn else \
            "Would assign the maintainer and add the needs-review label."
    elif verdict == "merge":
        headline = f"{would}merge: every rule for merging holds." if learn else "Merged: every rule for merging held."
        nxt = "" if not learn else "Nothing was merged; learning mode only comments."
    elif verdict == "close":
        headline = f"{would}close." if learn else "Closing."
        nxt = "" if not learn else "Nothing was closed; learning mode only comments."
    else:
        headline = "Noted."
        nxt = ""
    details = "\n".join(_reason_lines(facts))
    if extra:
        details += ("\n" if details else "") + f"- {public(extra)}"
    return _template("verdict.md").format(headline=headline, details=details or "- (no details)", next=nxt,
                                          footer=footer(learn)).replace("\n\n\n", "\n\n")


def close_body(facts: dict, rule: str | None, learn: bool) -> str:
    c = facts["classification"]
    if c.get("superseded_by"):
        return _template("close-superseded.md").format(newer=int(c["superseded_by"]), footer=footer(learn))
    rule_file, text, welcome = RULES.get(rule or "issue-first", RULES["issue-first"])
    return _template("close-human.md").format(rule_file=rule_file, rule=text, welcome=welcome, footer=footer(learn))
