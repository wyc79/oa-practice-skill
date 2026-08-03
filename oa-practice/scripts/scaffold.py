#!/usr/bin/env python3
"""Stamp out a fresh OA problem folder from the harness template.

    python3 scripts/scaffold.py <slug> [--dir DEST] [--lang cpp|python] [--tl 3000]

Creates DEST/<slug>/ with oa.py, run.sh, judge.sh, problem.json, a solution stub,
tests/samples/, and .oa/{reference,gen}.py placeholders. Fill those in afterwards.
"""
import argparse
import json
import shutil
import stat
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
HARNESS = HERE / "assets" / "harness"
STUBS = HERE / "assets" / "stubs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--lang", default="cpp", choices=["cpp", "python", "java"])
    ap.add_argument("--tl", type=int, default=3000, help="time limit in ms")
    a = ap.parse_args()

    dest = Path(a.dir).expanduser().resolve() / a.slug
    if dest.exists():
        raise SystemExit(f"{dest} already exists")
    shutil.copytree(HARNESS, dest)

    entry = {"cpp": "main.cpp", "python": "main.py", "java": "Main.java"}[a.lang]
    stub = STUBS / entry
    if stub.exists():
        shutil.copy(stub, dest / entry)
    else:
        (dest / entry).write_text("// TODO\n")

    cfg = json.loads((dest / "problem.json").read_text())
    cfg.update(name=a.slug, language=a.lang, entry=entry, time_limit_ms=a.tl)
    (dest / "problem.json").write_text(json.dumps(cfg, indent=2) + "\n")

    for f in ("run.sh", "judge.sh", "oa.py"):
        p = dest / f
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    (dest / "tests" / "samples").mkdir(parents=True, exist_ok=True)
    print(dest)


if __name__ == "__main__":
    main()
