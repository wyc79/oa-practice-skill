#!/usr/bin/env python3
"""OA harness: build, run samples, judge against generated tests.

Usage:
    python3 oa.py run              # run sample tests, show diffs
    python3 oa.py judge            # full judge run, prints Score: k/n (p%)
    python3 oa.py gen              # (re)generate hidden tests into tests/hidden/
    python3 oa.py case <name>      # run one test, show input/expected/actual
    python3 oa.py selfcheck        # check .oa/reference.py against the samples

Config lives in problem.json. Hidden reference solution + generator live in .oa/.
"""
import argparse
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG_PATH = ROOT / "problem.json"
BUILD = ROOT / ".oa" / "build"

G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"; DIM = "\033[2m"; B = "\033[1m"; X = "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    G = R = Y = DIM = B = X = ""


def cfg():
    with open(CFG_PATH) as f:
        c = json.load(f)
    c.setdefault("language", "cpp")
    c.setdefault("entry", "main.cpp" if c["language"] == "cpp" else "main.py")
    c.setdefault("time_limit_ms", 3000)
    c.setdefault("checker", "token")
    c.setdefault("float_eps", 1e-6)
    c.setdefault("num_random_tests", 20)
    c.setdefault("seed", 20260803)
    return c


def load_module(path, name):
    path = Path(path)
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- build / run

def build(c):
    """Compile if needed. Returns the argv used to run the solution."""
    BUILD.mkdir(parents=True, exist_ok=True)
    lang = c["language"]
    entry = ROOT / c["entry"]
    if not entry.exists():
        die(f"entry file not found: {entry}")

    if c.get("run_cmd"):
        if c.get("build_cmd"):
            sh(c["build_cmd"], "build")
        return c["run_cmd"] if isinstance(c["run_cmd"], list) else c["run_cmd"].split()

    if lang == "cpp":
        exe = BUILD / "main"
        cmd = ["g++", "-std=c++17", "-O2", "-pipe", "-o", str(exe), str(entry)]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            print(f"{R}{B}Compile error{X}\n{p.stderr}")
            sys.exit(2)
        if p.stderr.strip():
            print(f"{Y}{p.stderr.strip()}{X}")
        return [str(exe)]
    if lang == "python":
        return [sys.executable, str(entry)]
    if lang == "java":
        p = subprocess.run(["javac", "-d", str(BUILD), str(entry)], capture_output=True, text=True)
        if p.returncode != 0:
            print(f"{R}{B}Compile error{X}\n{p.stderr}")
            sys.exit(2)
        return ["java", "-cp", str(BUILD), entry.stem]
    die(f"unknown language {lang!r}; set run_cmd in problem.json instead")


def sh(cmd, what):
    p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if p.returncode != 0:
        print(f"{R}{what} failed{X}\n{p.stdout}\n{p.stderr}")
        sys.exit(2)


def die(msg):
    print(f"{R}{msg}{X}")
    sys.exit(2)


def run_once(argv, data, limit_ms):
    t0 = time.perf_counter()
    try:
        p = subprocess.run(argv, input=data, capture_output=True, text=True,
                           timeout=max(limit_ms / 1000.0 * 3 + 1, 5))
    except subprocess.TimeoutExpired:
        return "TLE", "", "", (limit_ms * 3)
    ms = (time.perf_counter() - t0) * 1000
    if p.returncode != 0:
        return "RE", p.stdout, p.stderr or f"exit code {p.returncode}", ms
    if ms > limit_ms:
        return "TLE", p.stdout, "", ms
    return "OK", p.stdout, p.stderr, ms


# ---------------------------------------------------------------- comparison

def compare(c, inp, expected, actual):
    mode = c["checker"]
    if mode == "custom":
        chk = load_module(ROOT / ".oa" / "checker.py", "oa_checker")
        if chk is None:
            die("checker=custom but .oa/checker.py is missing")
        res = chk.check(inp, expected, actual)
        return res if isinstance(res, tuple) else (res, "")
    if mode == "exact":
        return (expected.rstrip("\n") == actual.rstrip("\n"), "")
    et, at = expected.split(), actual.split()
    if mode == "float":
        if len(et) != len(at):
            return (False, f"token count {len(at)} != {len(et)}")
        eps = c["float_eps"]
        for i, (e, a) in enumerate(zip(et, at)):
            if e == a:
                continue
            try:
                if abs(float(e) - float(a)) <= eps * max(1.0, abs(float(e))):
                    continue
            except ValueError:
                pass
            return (False, f"token {i}: got {a!r}, want {e!r}")
        return (True, "")
    if et != at:
        for i, (e, a) in enumerate(zip(et, at)):
            if e != a:
                return (False, f"token {i}: got {a!r}, want {e!r}")
        return (False, f"token count {len(at)} != {len(et)}")
    return (True, "")


# ---------------------------------------------------------------- test corpus

def samples():
    d = ROOT / "tests" / "samples"
    out = []
    for f in sorted(d.glob("*.in")):
        exp = f.with_suffix(".out")
        out.append((f.stem, f.read_text(), exp.read_text() if exp.exists() else None))
    return out


def generate(c, force=False):
    """Build tests/hidden/*.in and *.out using .oa/gen.py + .oa/reference.py."""
    hid = ROOT / "tests" / "hidden"
    if force and hid.exists():
        shutil.rmtree(hid)
    hid.mkdir(parents=True, exist_ok=True)
    if list(hid.glob("*.out")) and not force:
        return
    gen = load_module(ROOT / ".oa" / "gen.py", "oa_gen")
    ref = load_module(ROOT / ".oa" / "reference.py", "oa_ref")
    if gen is None or ref is None:
        die("need .oa/gen.py and .oa/reference.py to judge")
    rng = random.Random(c["seed"])
    n = 0
    for i, data in enumerate(gen.cases(rng), 1):
        if not data.endswith("\n"):
            data += "\n"
        name = f"t{i:02d}"
        (hid / f"{name}.in").write_text(data)
        (hid / f"{name}.out").write_text(str(ref.solve(data)).rstrip("\n") + "\n")
        n += 1
    print(f"{DIM}generated {n} hidden tests{X}")


def hidden():
    d = ROOT / "tests" / "hidden"
    return [(f.stem, f.read_text(), f.with_suffix(".out").read_text())
            for f in sorted(d.glob("*.in"))]


# ---------------------------------------------------------------- reporting

def clip(s, lines=15, width=120):
    out = s.rstrip("\n").split("\n")
    body = [ln[:width] + ("…" if len(ln) > width else "") for ln in out[:lines]]
    if len(out) > lines:
        body.append(f"… (+{len(out) - lines} more lines)")
    return "\n".join("    " + ln for ln in body) or "    (empty)"


def show_failure(name, inp, expected, actual, why):
    print(f"\n{R}{B}--- {name} failed ---{X} {DIM}{why}{X}")
    print(f"{B}input:{X}\n{clip(inp)}")
    print(f"{B}expected:{X}\n{clip(expected)}")
    print(f"{B}your output:{X}\n{clip(actual)}")


def execute(c, argv, tests, reveal, label):
    passed = 0
    shown = 0
    slowest = 0.0
    for name, inp, exp in tests:
        status, out, err, ms = run_once(argv, inp, c["time_limit_ms"])
        slowest = max(slowest, ms)
        if status == "OK":
            ok, why = compare(c, inp, exp, out)
            if ok:
                passed += 1
                print(f"  {G}PASS{X} {name:<10} {DIM}{ms:6.0f} ms{X}")
                continue
            print(f"  {R}FAIL{X} {name:<10} {DIM}{ms:6.0f} ms  {why}{X}")
            if shown < reveal:
                show_failure(name, inp, exp, out, why)
                shown += 1
        elif status == "TLE":
            print(f"  {Y}TLE {X} {name:<10} {DIM}>{c['time_limit_ms']} ms{X}")
        else:
            print(f"  {R}RE  {X} {name:<10} {DIM}{err.strip().splitlines()[0] if err.strip() else ''}{X}")
            if shown < reveal:
                print(f"{R}{err.strip()[:2000]}{X}")
                shown += 1
    total = len(tests)
    pct = 100.0 * passed / total if total else 0.0
    bar = G if passed == total else (Y if passed else R)
    print(f"\n{bar}{B}{label}: {passed}/{total} ({pct:.0f}%){X}   {DIM}slowest {slowest:.0f} ms / limit {c['time_limit_ms']} ms{X}")
    return passed, total


def selfcheck(c):
    """Does the reference solution actually reproduce the sample outputs?

    If it does not, the problem statement was misread — fix that before the user
    burns an hour chasing a phantom bug in their own code.
    """
    ref = load_module(ROOT / ".oa" / "reference.py", "oa_ref")
    if ref is None:
        die("no .oa/reference.py")
    bad = 0
    for name, inp, exp in samples():
        if exp is None:
            print(f"  {Y}SKIP{X} {name} (no .out file)")
            continue
        try:
            got = str(ref.solve(inp)).rstrip("\n") + "\n"
        except Exception as e:
            print(f"  {R}CRASH{X} {name}: {type(e).__name__}: {e}")
            bad += 1
            continue
        ok, why = compare(c, inp, exp, got)
        print(f"  {G}OK  {X} {name}" if ok else f"  {R}BAD {X} {name}  {why}")
        if not ok:
            show_failure(name, inp, exp, got, why)
            bad += 1
    print(f"\n{(R if bad else G)}{B}reference vs samples: {'MISMATCH' if bad else 'consistent'}{X}")
    return 1 if bad else 0


# ---------------------------------------------------------------- entrypoints

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "judge", "gen", "case", "selfcheck"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--reveal", type=int, default=1, help="how many failing tests to print in full")
    ap.add_argument("--force", action="store_true", help="regenerate hidden tests")
    a = ap.parse_args()
    c = cfg()

    if a.cmd == "gen":
        generate(c, force=True)
        return

    if a.cmd == "selfcheck":
        sys.exit(selfcheck(c))

    argv = build(c)

    if a.cmd == "run":
        ts = samples()
        if not ts:
            die("no sample tests in tests/samples/")
        print(f"{B}Samples{X}")
        p, t = execute(c, argv, ts, a.reveal, "Samples")
        sys.exit(0 if p == t else 1)

    if a.cmd == "case":
        pool = {n: (n, i, e) for n, i, e in samples() + (hidden() if (ROOT / "tests" / "hidden").exists() else [])}
        if a.name not in pool:
            die(f"no such test {a.name!r}; have: {', '.join(sorted(pool))}")
        execute(c, argv, [pool[a.name]], 1, "Case")
        return

    # judge
    generate(c, force=a.force)
    ts = samples() + hidden()
    print(f"{B}Judging {c.get('name', 'solution')} — {len(ts)} tests{X}")
    p, t = execute(c, argv, ts, a.reveal, "Score")
    sys.exit(0 if p == t else 1)


if __name__ == "__main__":
    main()
