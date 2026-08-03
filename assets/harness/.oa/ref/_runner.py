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
    # Both ends go through .buffer with an explicit encoding: sys.stdin on a cp936
    # or cp1252 console would otherwise mis-decode UTF-8 input, and sys.stdout would
    # turn every "\n" into "\r\n" on Windows.
    data = sys.stdin.buffer.read().decode("utf-8").replace("\r\n", "\n")
    sys.stdout.buffer.write((str(mod.solve(data)).rstrip("\n") + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
