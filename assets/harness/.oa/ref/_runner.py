"""Runs a reference module in a subprocess so the harness can time-limit it.

    python3 _runner.py <path-to-reference.py>  < input.in  > output.out

Called by oa.py; not something you run by hand.
"""
import importlib.util
import sys
from pathlib import Path


def main():
    path = Path(sys.argv[1])
    # Compiled from source rather than spec_from_file_location: __pycache__
    # invalidates on (mtime-in-whole-seconds, size), so a same-length edit rerun
    # within the same second would silently run the previous reference.
    mod = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("oa_reference", loader=None))
    mod.__file__ = str(path)
    sys.modules["oa_reference"] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), mod.__dict__)
    sys.stdout.write(str(mod.solve(sys.stdin.read())).rstrip("\n") + "\n")


if __name__ == "__main__":
    main()
