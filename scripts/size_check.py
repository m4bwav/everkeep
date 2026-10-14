#!/usr/bin/env python3
"""everkeep's size budget (design section 11): small enough to install without hesitation.

Green passes, yellow passes with a warning to raise with the maintainer, red fails CI. Run from anywhere:
    python scripts/size_check.py"""

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "everkeep" / "SKILL.md"
PACKAGE = ROOT / "skills" / "everkeep" / "scripts"

# measure: (green below, red above); between is yellow
BUDGET = {
    "installed plugin, excluding .github/images (KB)": (400, 1024),
    "SKILL.md body (tokens, characters / 4)": (4000, 5000),
    "skill description (characters)": (700, 1024),
    "keep.py package (lines)": (4000, 6000),
    "third-party runtime imports": (1, 1),
}


def tracked_files():
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True).stdout
        return [ROOT / p for p in out.decode("utf-8").split("\0") if p]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


def description(front):
    m = re.search(r"^description:\s*(.+?)(?=^\w[\w-]*:|\Z)", front, re.M | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip().strip('"').strip("'") if m else ""


def third_party_imports():
    std = set(sys.stdlib_module_names) | {"everkeep", "__future__"}
    bad = set()
    for py in PACKAGE.rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            bad |= {n.split(".")[0] for n in names if n.split(".")[0] not in std}
    return sorted(bad)


def measure():
    files = [f for f in tracked_files() if f.exists() and ".github/images/" not in f.relative_to(ROOT).as_posix()]
    size_kb = round(sum(f.stat().st_size for f in files) / 1024, 1)
    text = SKILL.read_text(encoding="utf-8") if SKILL.exists() else ""
    front, body = frontmatter(text)
    lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in PACKAGE.rglob("*.py"))
    imports = third_party_imports()
    values = [size_kb, round(len(body) / 4), len(description(front)), lines, len(imports)]
    return values, imports


def main():
    values, imports = measure()
    worst = "green"
    for (name, (green, red)), value in zip(BUDGET.items(), values):
        level = "green" if value < green else "red" if value > red or (green == red and value >= red) else "yellow"
        if level == "red" or (level == "yellow" and worst == "green"):
            worst = level
        extra = f" ({', '.join(imports)})" if name.startswith("third") and imports else ""
        print(f"{level.upper():6} {name}: {value}{extra} (green under {green}, red over {red})")
    if worst == "yellow":
        print("YELLOW: within budget but past the green line; tell the maintainer before it grows.")
    print(f"size budget: {worst.upper()}")
    return 1 if worst == "red" else 0


if __name__ == "__main__":
    sys.exit(main())
