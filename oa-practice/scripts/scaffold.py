#!/usr/bin/env python3
"""Stamp out a fresh OA problem folder from the harness template.

    python3 scripts/scaffold.py <slug> [--dir DEST] [--lang cpp|python] [--tl 3000]

Creates DEST/<slug>/ with oa.py, the run/judge/oa wrappers for both platforms,
problem.json, README.md, a solution stub, tests/samples/, and .oa/gen.py plus
.oa/ref/reference.py. The stub is saved twice — once as the entry file the user
edits, once as .oa/stub.<ext>, which is what `oa.py wipe` restores from.

Those last two arrive as a worked example for a different problem, each carrying a
`TEMPLATE = True` line. The harness refuses to run until you have rewritten them and
removed that line — an example generator that quietly grades the wrong problem is
worse than no generator.
"""
import argparse
import json
import shutil
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
HARNESS = HERE / "assets" / "harness"
STUBS = HERE / "assets" / "stubs"

# Dot-entries do not survive skill packaging — a synced or installed copy of this skill
# simply arrives without them — so the template keeps its dotted paths under undotted
# names and they are renamed back into place once copied. Anything a workspace needs to
# see as a dotfile goes in this table rather than into assets/ under its real name.
DOTTED = {"oa-internal": ".oa"}


def write(path, text):
    """LF regardless of platform, so a workspace scaffolded on Windows is
    byte-identical to one scaffolded on macOS."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--lang", default="cpp", choices=["cpp", "python"])
    ap.add_argument("--tl", type=int, default=3000, help="time limit in ms")
    a = ap.parse_args()

    dest = Path(a.dir).expanduser().resolve() / a.slug
    if dest.exists():
        raise SystemExit(f"{dest} already exists")
    # Ignore __pycache__: running any harness file in the template directory leaves
    # one behind, and copytree would otherwise stamp it into every new workspace.
    shutil.copytree(HARNESS, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for packaged, dotted in DOTTED.items():
        if not (dest / packaged).exists():
            raise SystemExit(
                f"missing {HARNESS / packaged} — the skill's assets are incomplete")
        (dest / packaged).rename(dest / dotted)

    entry = {"cpp": "main.cpp", "python": "main.py"}[a.lang]
    stub = STUBS / entry
    if not stub.exists():
        raise SystemExit(f"missing stub {stub} — the skill's assets are incomplete")
    shutil.copy(stub, dest / entry)
    # A pristine copy, for `oa.py wipe`. The entry file stops being a stub the moment
    # the user types into it, so the only way back to a cold start is a copy kept out
    # of the way — .oa/ is already the folder the user is told not to read.
    shutil.copy(stub, dest / ".oa" / f"stub{Path(entry).suffix}")

    cfg = json.loads((dest / "problem.json").read_text(encoding="utf-8-sig"))
    cfg.update(name=a.slug, language=a.lang, entry=entry, time_limit_ms=a.tl)
    write(dest / "problem.json", json.dumps(cfg, indent=2) + "\n")

    readme = dest / "README.md"
    write(readme, readme.read_text(encoding="utf-8").replace("PROBLEM_SLUG", a.slug))

    # Record the interpreter running this script. It is a working Python 3 by
    # construction, which is more than can be said for anything named `python3` on
    # PATH — on Windows that is usually a Microsoft Store stub and `py` may not exist
    # at all. The wrappers still try PATH first, so a workspace stays portable; this
    # is only the fallback that keeps ./run.sh working on the machine it was built on.
    write(dest / ".oa" / "python-path", sys.executable + "\n")

    for f in ("run.sh", "judge.sh", "oa.sh", "oa.py"):
        p = dest / f
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    (dest / "tests" / "samples").mkdir(parents=True, exist_ok=True)
    print(dest)


if __name__ == "__main__":
    main()
