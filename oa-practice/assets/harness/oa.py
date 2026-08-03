#!/usr/bin/env python3
"""OA harness: build, run samples, judge against generated tests.

Usage:
    python3 oa.py run              # run sample tests, show diffs
    python3 oa.py judge            # full judge run, prints Score: k/n (p%)
    python3 oa.py gen              # (re)write tests/hidden/*.in + boundary coverage
    python3 oa.py answers          # compute the expected outputs (slow, resumable)
    python3 oa.py case <name>      # run one test, show input/expected/actual
    python3 oa.py selfcheck        # check the reference against the samples

Config lives in problem.json. Hidden generator lives in .oa/, reference solutions
in .oa/ref/.
"""
import argparse
import importlib.util
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG_PATH = ROOT / "problem.json"
BUILD = ROOT / ".oa" / "build"
REF_DIR = ROOT / ".oa" / "ref"
BRUTE = REF_DIR / "reference.py"
FAST = REF_DIR / "reference_fast.py"
RUNNER = REF_DIR / "_runner.py"
HIDDEN = ROOT / "tests" / "hidden"
TIMINGS = "_timings.json"

G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"; DIM = "\033[2m"; B = "\033[1m"; X = "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    G = R = Y = DIM = B = X = ""

# A console on a non-UTF-8 codepage (cp936, cp1252, …) raises on the box-drawing and
# dash characters below rather than printing them. Degrade the glyph, never the run.
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

# Every file this harness touches is UTF-8, whatever the system codepage says, and
# problem.json may carry a BOM if it has been through a Windows editor.
UTF8 = {"encoding": "utf-8"}


def read(path):
    return Path(path).read_text(**UTF8)


def write(path, text):
    Path(path).write_text(text, **UTF8)


def cfg():
    with open(CFG_PATH, encoding="utf-8-sig") as f:
        c = json.load(f)
    c.setdefault("language", "cpp")
    c.setdefault("entry", "main.cpp" if c["language"] == "cpp" else "main.py")
    c.setdefault("time_limit_ms", 3000)
    c.setdefault("checker", "token")
    c.setdefault("float_eps", 1e-6)
    c.setdefault("ref_time_limit_ms", 120000)
    c.setdefault("seed", 20260803)
    return c


def load_module(path, name):
    """Load a .py file fresh, every time.

    Deliberately not spec_from_file_location: that path caches bytecode in
    __pycache__ and invalidates on (mtime-in-whole-seconds, size), so editing
    .oa/gen.py without changing its length and rerunning within the same second
    silently reruns the *old* generator. Compiling the source has no such trap.
    """
    path = Path(path)
    if not path.exists():
        return None
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(read(path), str(path), "exec"), mod.__dict__)
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


# ------------------------------------------------------------- peak memory
# Windows reads the kernel's own peak working set, which is exact and free.
# Linux samples /proc while the child runs. Everywhere else reports n/a rather
# than a number that would quietly mean something different.

def _peak_windows(proc):
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    c = Counters()
    c.cb = ctypes.sizeof(c)
    try:
        ok = ctypes.WinDLL("psapi").GetProcessMemoryInfo(
            wintypes.HANDLE(int(proc._handle)), ctypes.byref(c), c.cb)
    except Exception:
        return None
    return c.PeakWorkingSetSize if ok else None


class _LinuxSampler(threading.Thread):
    """Poll /proc/<pid>/statm; the kernel drops VmHWM the moment the process exits."""

    def __init__(self, pid):
        super().__init__(daemon=True)
        self.pid, self.peak, self.stop = pid, 0, False

    def run(self):
        page = os.sysconf("SC_PAGE_SIZE")
        path = f"/proc/{self.pid}/statm"
        while not self.stop:
            try:
                with open(path) as f:
                    self.peak = max(self.peak, int(f.read().split()[1]) * page)
            except (OSError, IndexError, ValueError):
                return
            time.sleep(0.002)


def run_once(argv, data, limit_ms):
    """Run the solution once. Returns (status, stdout, stderr, ms, peak_bytes|None)."""
    t0 = time.perf_counter()
    p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    sampler = None
    if sys.platform.startswith("linux"):
        sampler = _LinuxSampler(p.pid)
        sampler.start()
    try:
        out, err = p.communicate(data, timeout=max(limit_ms / 1000.0 * 3 + 1, 5))
        timed_out = False
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        timed_out = True
    ms = (time.perf_counter() - t0) * 1000
    if sampler:
        sampler.stop = True
        sampler.join(0.05)
    mem = _peak_windows(p) if os.name == "nt" else (sampler.peak or None if sampler else None)

    if timed_out:
        return "TLE", "", "", limit_ms * 3, mem
    if p.returncode != 0:
        return "RE", out, err or f"exit code {p.returncode}", ms, mem
    if ms > limit_ms:
        return "TLE", out, "", ms, mem
    return "OK", out, err, ms, mem


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


# ---------------------------------------------------------- boundary coverage

def bounds(entry):
    """A LIMITS value is (lo, hi), or (lo, hi, "no-corner") when two upper bounds
    are mutually exclusive and this key cannot be part of the joint max corner."""
    return entry[0], entry[1], "no-corner" in entry[2:]


def check_limits(gen_mod, tests):
    """Do the generated inputs actually reach the constraint boundaries?

    Hard failures: an endpoint no test reaches, a value outside its declared bound,
    or no single test attaining every upper bound at once. Returns True when the
    suite covers what it claims to.
    """
    lim = getattr(gen_mod, "LIMITS", None)
    measure = getattr(gen_mod, "measure", None)
    if not lim or not measure:
        print(f"  {Y}.oa/gen.py declares no LIMITS/measure — boundaries unchecked{X}")
        return True

    obs = {k: {"lo": None, "lo_at": "", "hi": None, "hi_at": "", "listy": False} for k in lim}
    tops, spread, bad = {}, {}, []

    for name, data in tests:
        tops[name], spread[name] = set(), {}
        for k, v in measure(data).items():
            if k not in lim:
                continue
            lo, hi, _ = bounds(lim[k])
            listy = not isinstance(v, (int, float))
            vals = list(v) if listy else [v]
            obs[k]["listy"] |= listy
            if not vals:
                continue
            if min(vals) < lo:
                bad.append((name, k, min(vals), lo, hi))
            if max(vals) > hi:
                bad.append((name, k, max(vals), lo, hi))

            # Endpoint coverage looks only at in-range values, so an out-of-range
            # test reports as a violation and not also as phantom coverage.
            inr = [x for x in vals if lo <= x <= hi]
            if not inr:
                continue
            vmin, vmax = min(inr), max(inr)
            o = obs[k]
            if o["lo"] is None or vmin < o["lo"]:
                o["lo"], o["lo_at"] = vmin, name
            if o["hi"] is None or vmax > o["hi"]:
                o["hi"], o["hi_at"] = vmax, name
            if vmax == hi:
                tops[name].add(k)
            if listy:
                spread[name][k] = (vmin, vmax)

    ok = True
    w = max(max(len(k) for k in lim), len("joint max corner"))
    sw = max(len(f"{bounds(e)[0]} .. {bounds(e)[1]}") for e in lim.values())
    for k, entry in lim.items():
        lo, hi, exempt = bounds(entry)
        o = obs[k]
        miss = [n for n, got, want in (("min", o["lo"], lo), ("max", o["hi"], hi)) if got != want]
        span = f"{lo} .. {hi}"
        if miss:
            ok = False
            got = f"reached {o['lo']} .. {o['hi']}" if o["lo"] is not None else "never measured"
            print(f"  {k:<{w}}  {span:<{sw}}  {R}MISSING {' and '.join(miss)}{X}  {DIM}{got}{X}")
        else:
            at = f"min {o['lo_at']}  max {o['hi_at']}"
            tag = f"  {DIM}(corner exempt){X}" if exempt else ""
            print(f"  {k:<{w}}  {span:<{sw}}  {DIM}{at}{X}  {G}OK{X}{tag}")

    corner_keys = {k for k, e in lim.items() if not bounds(e)[2]}
    corner = next((n for n, _ in tests if corner_keys <= tops[n]), None)
    if corner is None:
        ok = False
        print(f"  {'joint max corner':<{w}}  {R}MISSING{X}  "
              f"{DIM}no single test attains {', '.join(sorted(corner_keys))} at their max{X}")
    else:
        print(f"  {'joint max corner':<{w}}  {corner:<{sw}}  {G}OK{X}")
        for k, (vmin, vmax) in spread[corner].items():
            hi = bounds(lim[k])[1]
            if vmin != hi:
                print(f"  {Y}hint{X} {corner} has {k} in [{vmin}, {vmax}], not saturated at {hi}"
                      f"  {DIM}— saturate it if the problem allows{X}")

    for name, k, val, lo, hi in bad[:10]:
        ok = False
        print(f"  {R}VIOLATION{X} {name}: {k}={val} outside [{lo}, {hi}]")
    if len(bad) > 10:
        print(f"  {DIM}… +{len(bad) - 10} more violations{X}")
    return ok


# ---------------------------------------------------------------- test corpus

def samples():
    d = ROOT / "tests" / "samples"
    out = []
    for f in sorted(d.glob("*.in")):
        exp = f.with_suffix(".out")
        out.append((f.stem, read(f), read(exp) if exp.exists() else None))
    return out


def case_name(i, label):
    if not label:
        return f"t{i:02d}"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(label)).strip("-").lower()
    return f"t{i:02d}-{slug}" if slug else f"t{i:02d}"


def generate(c, force=False):
    """Write tests/hidden/*.in from .oa/gen.py, then check boundary coverage."""
    gen = load_module(ROOT / ".oa" / "gen.py", "oa_gen")
    if gen is None:
        die("need .oa/gen.py to judge")
    if force and HIDDEN.exists():
        shutil.rmtree(HIDDEN)
    HIDDEN.mkdir(parents=True, exist_ok=True)
    if list(HIDDEN.glob("*.in")) and not force:
        return

    rng = random.Random(c["seed"])
    tests = []
    for i, item in enumerate(gen.cases(rng), 1):
        label, data = item if isinstance(item, tuple) else (None, item)
        if not data.endswith("\n"):
            data += "\n"
        name = case_name(i, label)
        write(HIDDEN / f"{name}.in", data)
        tests.append((name, data))
    print(f"{DIM}generated {len(tests)} test inputs{X}")

    print(f"{B}Boundary coverage{X}")
    if not check_limits(gen, tests):
        die("\nboundary coverage failed — fix .oa/gen.py and rerun")


def run_reference(path, data, limit_ms):
    """Run a reference in a subprocess so the budget is actually enforceable."""
    argv = [sys.executable, str(RUNNER), str(path)]
    t0 = time.perf_counter()
    try:
        p = subprocess.run(argv, input=data, capture_output=True, text=True,
                           timeout=limit_ms / 1000.0)
    except subprocess.TimeoutExpired:
        return "TLE", "", "", (time.perf_counter() - t0) * 1000
    ms = (time.perf_counter() - t0) * 1000
    if p.returncode != 0:
        return "RE", "", p.stderr.strip(), ms
    return "OK", p.stdout, "", ms


def answers(c, force=False):
    """Compute tests/hidden/*.out. Slow by design, and resumable: every answer is
    written the moment it lands, so an interrupt costs one test, not the suite."""
    ins = sorted(HIDDEN.glob("*.in"))
    if not ins:
        die("no test inputs — run: python3 oa.py gen")
    if not BRUTE.exists():
        die(f"missing {BRUTE.relative_to(ROOT)}")
    limit = c["ref_time_limit_ms"]
    todo = [f for f in ins if force or not f.with_suffix(".out").exists()]
    if not todo:
        return

    print(f"{B}Answers{X} {DIM}— {len(todo)} to compute, {limit / 1000:g}s budget each{X}")
    agreed, beyond, timings = 0, [], ref_timings()
    for f in todo:
        data = read(f)
        status, out, err, ms = run_reference(BRUTE, data, limit)
        if status == "RE":
            die(f"reference crashed on {f.stem}:\n{err}")

        if status == "OK":
            print(f"  {f.stem:<18} {ms / 1000:6.1f}s  {DIM}reference{X}")
            timings[f.stem] = (ms, "reference")
            if FAST.exists():
                fstatus, fout, ferr, _ = run_reference(FAST, data, limit)
                if fstatus != "OK":
                    die(f"reference_fast {fstatus} on {f.stem}: {ferr}")
                same, why = compare(c, data, out, fout)
                if not same:
                    print(f"\n{R}{B}reference_fast disagrees with reference on {f.stem}{X}")
                    show_failure(f.stem, data, out, fout, why)
                    die("one of the two references is wrong — fix it before trusting either")
                agreed += 1
        else:
            if not FAST.exists():
                die(f"reference exceeded {limit / 1000:g}s on {f.stem}.\n"
                    f"  Raise ref_time_limit_ms in problem.json, or add "
                    f"{FAST.relative_to(ROOT)} with the intended algorithm —\n"
                    f"  it gets cross-checked against the brute force on every test the "
                    f"brute force can finish.")
            fstatus, out, ferr, fms = run_reference(FAST, data, limit)
            if fstatus != "OK":
                die(f"reference_fast {fstatus} on {f.stem}: {ferr}")
            print(f"  {f.stem:<18} {DIM}>{limit / 1000:g}s reference gave up{X} -> "
                  f"{fms / 1000:.1f}s  {Y}reference_fast{X}")
            timings[f.stem] = (fms, "reference_fast")
            beyond.append(f.stem)

        write(f.with_suffix(".out"), str(out).rstrip("\n") + "\n")

    write(HIDDEN / TIMINGS, json.dumps(timings, indent=1))
    if FAST.exists():
        print(f"  {DIM}cross-check: reference_fast agrees with reference on "
              f"{agreed}/{agreed} checkable tests{X}  {G}OK{X}")
        if beyond:
            print(f"  {Y}{len(beyond)} beyond brute force, answered by reference_fast alone{X}"
                  f"  {DIM}({', '.join(beyond)}){X}")


def ref_timings():
    """How long each reference took, recorded by `answers` for the scaling report."""
    p = HIDDEN / TIMINGS
    if not p.exists():
        return {}
    try:
        return {k: tuple(v) for k, v in json.loads(read(p)).items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def hidden():
    out = []
    for f in sorted(HIDDEN.glob("*.in")):
        o = f.with_suffix(".out")
        if o.exists():
            out.append((f.stem, read(f), read(o)))
    return out


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


def human_bytes(b):
    if b is None:
        return "n/a"
    for unit, div in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if b >= div:
            return f"{b / div:.1f} {unit}"
    return f"{b} B"


def fit_exponent(points):
    """Least-squares slope of log(y) against log(x): the k in y ~ x^k.

    Returns None when the data is too thin or too flat to say anything.
    """
    pts = [(x, y) for x, y in points if x and x > 0 and y and y > 0]
    if len(pts) < 3:
        return None
    n = len(pts)
    lx = [math.log(x) for x, _ in pts]
    ly = [math.log(y) for _, y in pts]
    mx, my = sum(lx) / n, sum(ly) / n
    den = sum((a - mx) ** 2 for a in lx)
    if den <= 1e-9:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / den


def complexity_report(c, stats):
    """How does the solution scale? stats: [(name, input_bytes, ms, mem_or_None)]"""
    rows = sorted(stats, key=lambda r: r[1])
    if len(rows) < 3:
        return
    print(f"\n{B}Scaling{X} {DIM}— largest tests, by input size{X}")
    for name, size, ms, mem in rows[-5:]:
        print(f"  {human_bytes(size):>9}  {ms:7.0f} ms  {human_bytes(mem):>10}   {DIM}{name}{X}")

    # Both curves have a large constant term — process startup, and the runtime's
    # baseline heap. Subtract each before fitting, or the exponent reads far too low.
    all_pts = [r for r in rows if r[1] > 0]
    t_base = min(r[2] for r in all_pts)
    mems = [r[3] for r in all_pts if r[3]]
    m_base = min(mems) if mems else None
    t_signal = max(r[2] for r in all_pts) - t_base
    m_signal = (max(mems) - m_base) if mems else 0

    # Fit only above a size floor. On the tiny tests the runtime *is* the process
    # startup and the memory *is* the runtime baseline, so their y values are noise
    # sitting at x values spanning several decades — including them flattens the
    # slope of a perfectly linear solution towards zero.
    pts = [r for r in all_pts if r[1] >= all_pts[-1][1] / 1000.0]
    spread = pts[-1][1] / pts[0][1] if len(pts) >= 2 else 1
    if len(pts) < 4 or spread < 10:
        print(f"  {DIM}only {len(pts)} tests within 1000x of the largest, spanning {spread:.0f}x "
              f"— too narrow to fit. Add a geometric size ladder to .oa/gen.py.{X}")
        return

    # A curve fitted through noise is worse than no curve. Time needs real dynamic
    # range above the startup floor before its exponent means anything.
    # Points sitting within a few ms of the floor are startup jitter, not work. They
    # span decades of x at a constant y, which flattens the slope of even a quadratic
    # solution towards zero, so they are dropped rather than fitted.
    kt = (fit_exponent([(r[1], r[2] - t_base) for r in pts if r[2] - t_base >= 3.0])
          if t_signal >= max(25.0, 2 * t_base) else None)
    km = (fit_exponent([(r[1], r[3] - m_base) for r in pts if r[3]])
          if m_signal >= (4 << 20) else None)

    if kt is not None:
        note = f"  {Y}— above linear{X}" if kt > 1.35 else ""
        print(f"  {B}time   ~ n^{kt:.2f}{X}{note}  {DIM}({t_base:.0f} ms startup subtracted){X}")
    else:
        print(f"  {DIM}time:   {t_signal:.0f} ms of range above a {t_base:.0f} ms startup floor "
              f"— too little to fit a curve, which is itself a good sign{X}")
    if km is not None:
        print(f"  {B}memory ~ n^{km:.2f}{X}  {DIM}({human_bytes(m_base)} runtime baseline subtracted){X}")
    else:
        print(f"  {DIM}memory: {human_bytes(m_signal)} of variation — too flat to fit{X}")

    ref = ref_timings()
    if ref:
        name, size, ms, _ = rows[-1]
        rms, who = ref.get(name, (None, None))
        if rms:
            print(f"  {DIM}{who} took {rms / 1000:.1f}s on {name} vs your {ms:.0f} ms — "
                  f"it is Python, so treat the ratio as a sanity check, not a benchmark{X}")


def execute(c, argv, tests, reveal, label):
    passed = 0
    shown = 0
    slowest = 0.0
    stats = []
    for name, inp, exp in tests:
        status, out, err, ms, mem = run_once(argv, inp, c["time_limit_ms"])
        slowest = max(slowest, ms)
        used = f"{DIM}{ms:6.0f} ms  {human_bytes(mem):>9}{X}"
        if status == "OK":
            ok, why = compare(c, inp, exp, out)
            stats.append((name, len(inp), ms, mem))
            if ok:
                passed += 1
                print(f"  {G}PASS{X} {name:<18} {used}")
                continue
            print(f"  {R}FAIL{X} {name:<18} {used}  {DIM}{why}{X}")
            if shown < reveal:
                show_failure(name, inp, exp, out, why)
                shown += 1
        elif status == "TLE":
            print(f"  {Y}TLE {X} {name:<18} {DIM}>{c['time_limit_ms']} ms{X}")
        else:
            print(f"  {R}RE  {X} {name:<18} {DIM}{err.strip().splitlines()[0] if err.strip() else ''}{X}")
            if shown < reveal:
                print(f"{R}{err.strip()[:2000]}{X}")
                shown += 1
    total = len(tests)
    pct = 100.0 * passed / total if total else 0.0
    bar = G if passed == total else (Y if passed else R)
    print(f"\n{bar}{B}{label}: {passed}/{total} ({pct:.0f}%){X}   {DIM}slowest {slowest:.0f} ms / limit {c['time_limit_ms']} ms{X}")
    return passed, total, stats


def check_against_samples(c, path, title):
    """Does this reference reproduce the sample outputs from the statement?

    If it does not, the statement was misread — fix that before the user burns an
    hour chasing a phantom bug in their own code. Every reference gets this, the
    fast one included: it is the only place either is checked against ground truth
    the harness did not produce itself.
    """
    ref = load_module(path, f"oa_ref_{title}")
    bad = 0
    print(f"\n{B}{title} vs samples{X}")
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
    print(f"  {(R + B + 'MISMATCH') if bad else (G + B + 'consistent')}{X}")
    return bad


def selfcheck(c):
    if not BRUTE.exists():
        die(f"no {BRUTE.relative_to(ROOT)}")
    bad = check_against_samples(c, BRUTE, "reference")
    if FAST.exists():
        bad += check_against_samples(c, FAST, "reference_fast")

    ins = sorted(HIDDEN.glob("*.in"))
    if ins:
        gen = load_module(ROOT / ".oa" / "gen.py", "oa_gen")
        print(f"\n{B}Boundary coverage{X} {DIM}({len(ins)} cached tests){X}")
        if not check_limits(gen, [(f.stem, read(f)) for f in ins]):
            bad += 1
    else:
        print(f"\n{Y}no tests generated yet — run: python3 oa.py gen{X}")
    return 1 if bad else 0


# ---------------------------------------------------------------- entrypoints

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "judge", "gen", "answers", "case", "selfcheck"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--reveal", type=int, default=1, help="how many failing tests to print in full")
    ap.add_argument("--force", action="store_true", help="discard cached tests / answers")
    a = ap.parse_args()
    c = cfg()

    if a.cmd == "gen":
        generate(c, force=True)
        return

    if a.cmd == "answers":
        generate(c, force=a.force)
        answers(c, force=a.force)
        return

    if a.cmd == "selfcheck":
        sys.exit(selfcheck(c))

    argv = build(c)

    if a.cmd == "run":
        ts = samples()
        if not ts:
            die("no sample tests in tests/samples/")
        print(f"{B}Samples{X}")
        p, t, _ = execute(c, argv, ts, a.reveal, "Samples")
        sys.exit(0 if p == t else 1)

    if a.cmd == "case":
        pool = {n: (n, i, e) for n, i, e in samples() + (hidden() if HIDDEN.exists() else [])}
        if a.name not in pool:
            die(f"no such test {a.name!r}; have: {', '.join(sorted(pool))}")
        execute(c, argv, [pool[a.name]], 1, "Case")
        return

    # judge
    generate(c, force=a.force)
    answers(c, force=a.force)
    ts = samples() + hidden()
    print(f"{B}Judging {c.get('name', 'solution')} — {len(ts)} tests{X}")
    p, t, stats = execute(c, argv, ts, a.reveal, "Score")
    if p == t:
        complexity_report(c, stats)
    sys.exit(0 if p == t else 1)


if __name__ == "__main__":
    main()
