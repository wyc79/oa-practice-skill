#!/usr/bin/env python3
"""Stamp out a fresh OA problem folder from the harness template.

    python3 scripts/scaffold.py <slug> [--dir DEST] [--lang cpp|python] [--tl 3000]

Creates DEST/<slug>/ with oa.py, the run/judge/oa wrappers for both platforms,
problem.json, README.md, a solution stub, tests/samples/, and .oa/gen.py plus
.oa/ref/reference.py.

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

    entry = {"cpp": "main.cpp", "python": "main.py"}[a.lang]
    stub = STUBS / entry
    if not stub.exists():
        raise SystemExit(f"missing stub {stub} — the skill's assets are incomplete")
    shutil.copy(stub, dest / entry)

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
