#!/usr/bin/env python3
r"""OA harness: build, run samples, judge against generated tests.

Usage (or ./oa.sh <cmd> / .\oa.cmd <cmd>, which find a working interpreter first):
    python3 oa.py run              # run sample tests, show diffs
    python3 oa.py judge            # full judge run, prints Score: k/n (p%)
    python3 oa.py gen              # (re)write tests/hidden/*.in + boundary coverage
    python3 oa.py answers          # compute the expected outputs (slow, resumable)
    python3 oa.py case <name>      # run one test, show input/expected/actual
    python3 oa.py selfcheck        # references vs samples, coverage, staleness
    python3 oa.py selfcheck --entry _check.cpp  # ...and the entry file's I/O

`run` explains every failing sample; `judge` explains none, because the expected
output of a hidden test is the answer. `--reveal N` overrides either way.

The `--entry` stand-in carries the entry file's extension, because it goes through the
same build() and so to the same toolchain: `_check.cpp` for the default C++ workspace,
`_check.py` for a Python one.

Config lives in problem.json. Hidden generator lives in .oa/, reference solutions
in .oa/ref/.
"""
import argparse
import hashlib
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
STAMP = "_stamp.json"

G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"; DIM = "\033[2m"; B = "\033[1m"; X = "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    G = R = Y = DIM = B = X = ""

# Windows renders a real console through WriteConsoleW, so the dashes below survive
# there whatever the codepage — but redirect the output and Python falls back to the
# locale encoding, where cp936/cp1252 turn every "—" into "??" or raise outright.
# Pin UTF-8 on both streams, and keep errors="replace" so a stray glyph can never be
# the thing that kills a judge run.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# Every file this harness touches is UTF-8, whatever the system codepage says. Read
# as utf-8-sig, not utf-8: anything that has been through a Windows editor may carry
# a BOM — PowerShell's `Set-Content -Encoding utf8` writes one by default — and a BOM
# left in the string is a hard `SyntaxError: invalid non-printable character U+FEFF`
# when load_module compiles .oa/gen.py or a reference. Writes stay BOM-less.
UTF8 = {"encoding": "utf-8-sig"}


def read(path):
    return Path(path).read_text(**UTF8)


def write(path, text):
    """Always LF. The default translates "\\n" to os.linesep, which would make the
    same seed produce byte-different test files on Windows than on macOS/Linux."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def decode(b):
    """Child output back to text. Text-mode pipes would do this for us, but they
    also rewrite stdin on the way in (see run_once), so we do both ends by hand."""
    return b.decode("utf-8", "replace").replace("\r\n", "\n") if b else ""


def plat():
    return "windows" if os.name == "nt" else ("macos" if sys.platform == "darwin" else "linux")


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
# Toolchain names differ per platform and none of them are guaranteed: macOS ships
# clang++ (often as g++), Windows ships neither until you install one. Look for what
# is actually there and, when nothing is, say how to get it — a bare "g++ not found"
# leaves the user to guess which of several answers applies to their machine.

CXX = ("g++", "clang++", "c++")

HINTS = {
    "c++ compiler": {
        "windows": "install MSYS2, then `pacman -S mingw-w64-ucrt-x86_64-gcc` and put\n"
                   "  its ucrt64/bin on PATH — or set \"language\": \"python\" in problem.json",
        "macos": "run `xcode-select --install`",
        "linux": "install build-essential (Debian/Ubuntu) or gcc-c++ (Fedora)",
    },
}


def need_tool(names, what):
    for n in names:
        if shutil.which(n):
            return n
    die(f"no {what} on PATH (looked for {', '.join(names)})\n"
        f"  {HINTS[what][plat()]}")


def compile_with(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if p.returncode != 0:
        print(f"{R}{B}Compile error{X}\n{p.stderr}")
        sys.exit(2)
    if p.stderr.strip():
        print(f"{Y}{p.stderr.strip()}{X}")


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
        # Name the .exe explicitly on Windows: MinGW's linker appends .exe to a
        # suffixless -o anyway, and CreateProcess will not find the file without it.
        exe = BUILD / ("main.exe" if os.name == "nt" else "main")
        compile_with([need_tool(CXX, "c++ compiler"), "-std=c++17", "-O2", "-pipe",
                      "-o", str(exe), str(entry)])
        return [str(exe)]
    if lang == "python":
        return [sys.executable, str(entry)]
    die(f"unsupported language {lang!r} — built-in support is cpp and python.\n"
        f"  Anything else runs through build_cmd / run_cmd in problem.json.")


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
# Linux and macOS sample the running child instead — the kernel discards the true
# high-water mark the moment the process exits, and neither exposes it per-child
# through subprocess. Sampling can undershoot on a very short run; it never
# overshoots. Anywhere else reports n/a rather than a number that would quietly
# mean something different.

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


class _Sampler(threading.Thread):
    def __init__(self, pid, interval):
        super().__init__(daemon=True)
        self.pid, self.interval, self.peak, self.stop = pid, interval, 0, False

    def run(self):
        while not self.stop:
            b = self.sample()
            if b is None:
                return
            self.peak = max(self.peak, b)
            time.sleep(self.interval)


class _LinuxSampler(_Sampler):
    """Poll /proc/<pid>/statm; the kernel drops VmHWM the moment the process exits."""

    def __init__(self, pid):
        super().__init__(pid, 0.002)
        self.page = os.sysconf("SC_PAGE_SIZE")
        self.path = f"/proc/{pid}/statm"

    def sample(self):
        try:
            with open(self.path) as f:
                return int(f.read().split()[1]) * self.page
        except (OSError, IndexError, ValueError):
            return None


class _MacSampler(_Sampler):
    """macOS has no /proc, so shell out to ps. Each sample costs a fork, hence the
    coarser interval — a test that finishes in a few ms may go unsampled entirely."""

    def __init__(self, pid):
        super().__init__(pid, 0.01)

    def sample(self):
        try:
            out = subprocess.run(["ps", "-o", "rss=", "-p", str(self.pid)],
                                 capture_output=True, text=True, timeout=1).stdout.strip()
            return int(out) * 1024 if out else None
        except (OSError, ValueError, subprocess.SubprocessError):
            return None


def sampler_for(pid):
    if sys.platform.startswith("linux"):
        return _LinuxSampler(pid)
    if sys.platform == "darwin":
        return _MacSampler(pid)
    return None


def run_once(argv, data, limit_ms):
    """Run the solution once. Returns (status, stdout, stderr, ms, peak_bytes|None).

    Binary pipes, decoded by hand: a text-mode stdin translates "\\n" to os.linesep,
    so on Windows every solution would be fed CRLF and any getline() would come back
    with a trailing "\\r".
    """
    t0 = time.perf_counter()
    p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    sampler = sampler_for(p.pid)
    if sampler:
        sampler.start()
    try:
        out, err = p.communicate(data.encode("utf-8"), timeout=max(limit_ms / 1000.0 * 3 + 1, 5))
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
    out, err = decode(out), decode(err)

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
    """A LIMITS value is (lo, hi), optionally followed by markers:

      "no-corner"    two upper bounds are mutually exclusive, so this key cannot be
                     part of the joint max corner at all.
      "no-saturate"  the corner can *attain* this key's max but cannot hold every
                     element there, because a derived bound forbids it — 10^4 lists
                     of 500 against a total-length budget of 10^4. The key stays
                     required in the corner; only the saturation hint is dropped.
    """
    flags = entry[2:]
    return entry[0], entry[1], "no-corner" in flags, "no-saturate" in flags


def check_limits(gen_mod, tests):
    """Do the generated inputs actually reach the constraint boundaries?

    Hard failures: an endpoint no test reaches, a value outside its declared bound,
    or no single test attaining every upper bound at once. Returns True when the
    suite covers what it claims to.
    """
    lim = getattr(gen_mod, "LIMITS", None)
    measure = getattr(gen_mod, "measure", None)
    if not lim and not measure:
        # Declaring neither is a real choice, and the folders scaffolded before this
        # check existed made it. Warn and carry on.
        print(f"  {Y}.oa/gen.py declares no LIMITS/measure — boundaries unchecked{X}")
        return True
    if not measure:
        # Half-declared is not a choice, it is an unfinished edit. Warning here would
        # print "boundaries unchecked" over a file that visibly declares boundaries.
        print(f"  {R}.oa/gen.py declares LIMITS but no measure(){X} — nothing can read those\n"
              f"  bounds back off a generated input, so none of them are being checked.")
        return False
    if not lim:
        print(f"  {R}.oa/gen.py defines measure() but no LIMITS{X} — there is nothing to\n"
              f"  check the measured values against.")
        return False

    obs = {k: {"lo": None, "lo_at": "", "hi": None, "hi_at": "", "listy": False} for k in lim}
    tops, spread, bad = {}, {}, []

    for name, data in tests:
        tops[name], spread[name] = set(), {}
        for k, v in measure(data).items():
            if k not in lim:
                continue
            lo, hi = bounds(lim[k])[:2]
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
        lo, hi, exempt, no_sat = bounds(entry)
        o = obs[k]
        miss = [n for n, got, want in (("min", o["lo"], lo), ("max", o["hi"], hi)) if got != want]
        span = f"{lo} .. {hi}"
        if miss:
            ok = False
            got = f"reached {o['lo']} .. {o['hi']}" if o["lo"] is not None else "never measured"
            print(f"  {k:<{w}}  {span:<{sw}}  {R}MISSING {' and '.join(miss)}{X}  {DIM}{got}{X}")
        else:
            at = f"min {o['lo_at']}  max {o['hi_at']}"
            waived = [n for n, on in (("corner", exempt), ("saturation", no_sat)) if on]
            tag = f"  {DIM}({' and '.join(waived)} exempt){X}" if waived else ""
            print(f"  {k:<{w}}  {span:<{sw}}  {DIM}{at}{X}  {G}OK{X}{tag}")

    corner_keys = {k for k, e in lim.items() if not bounds(e)[2]}
    # Several tests can attain every upper bound while differing in how much else they
    # max out. Report the most saturated one: naming the first would flag a purpose-built
    # saturated corner as "not saturated" whenever any earlier test also qualified.
    cands = [n for n, _ in tests if corner_keys <= tops[n]]
    corner = min(cands, key=lambda n: sum(
        1 for k, (vmin, _) in spread[n].items() if vmin != bounds(lim[k])[1])) if cands else None
    if corner is None:
        ok = False
        print(f"  {'joint max corner':<{w}}  {R}MISSING{X}  "
              f"{DIM}no single test attains {', '.join(sorted(corner_keys))} at their max{X}")
    else:
        print(f"  {'joint max corner':<{w}}  {corner:<{sw}}  {G}OK{X}")
        for k, (vmin, vmax) in spread[corner].items():
            _, hi, exempt_k, no_sat_k = bounds(lim[k])
            # Both exemptions mean the same thing here: the author has already said
            # this key cannot be held at its maximum, so the hint has no legal answer
            # and no edit would silence it. no-corner drops the key from the corner
            # entirely; no-saturate keeps it required there and only drops the nag.
            if exempt_k or no_sat_k or vmin == hi:
                continue
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


TEMPLATE_MARK = re.compile(r"^TEMPLATE\s*=\s*True", re.M)


def refuse_template(path):
    """The scaffold ships a complete worked example, not a stub. Left alone it
    generates tests, passes its own coverage check and scores a solution — for a
    problem nobody asked about. So it carries a marker, and nothing runs until the
    marker is gone."""
    if path.exists() and TEMPLATE_MARK.search(read(path)):
        die(f"{path.relative_to(ROOT)} is still the scaffold example (sum an array).\n"
            f"  Rewrite it for this problem, then delete its `TEMPLATE = True` line.")


def case_name(i, label):
    if not label:
        return f"t{i:02d}"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(label)).strip("-").lower()
    return f"t{i:02d}-{slug}" if slug else f"t{i:02d}"


# ------------------------------------------------------------------- staleness
# tests/hidden/ is a cache of two expensive things — the generated inputs, and the
# reference's answers to them. Both were previously keyed on nothing but existence,
# so editing .oa/gen.py or a reference and rerunning `judge` scored the solution
# against the *old* suite and printed a green nobody had earned. Fingerprint what
# each half was built from, and rebuild the half that no longer matches.

def sha(path):
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None


def input_stamp(c):
    """What tests/hidden/*.in was generated from."""
    return {"gen": sha(ROOT / ".oa" / "gen.py"), "seed": c["seed"]}


def answer_stamp():
    """What tests/hidden/*.out was computed by. Either reference can set answers,
    so a change to either invalidates all of them."""
    return {"ref": [sha(BRUTE), sha(FAST)]}


def read_stamp():
    try:
        return json.loads(read(HIDDEN / STAMP))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def save_stamp(**fields):
    s = read_stamp()
    s.update(fields)
    HIDDEN.mkdir(parents=True, exist_ok=True)
    write(HIDDEN / STAMP, json.dumps(s, indent=1))


def stale(want):
    """Which of `want`'s fields the cache disagrees with. A field the cache never
    recorded counts as stale — provenance you cannot check is provenance you do not
    have — but say so differently, because "gen changed" about a file nobody has
    touched sends the reader looking for an edit that was never made."""
    have = read_stamp()
    return [k for k, v in want.items() if have.get(k) != v]


def why_stale(want, subject):
    have = read_stamp()
    if not any(k in have for k in want):
        return f"no record of what built {subject}"
    return f"{', '.join(stale(want))} changed since {subject} were built"


def coverage_or_die(gen, tests):
    print(f"{B}Boundary coverage{X}")
    if not check_limits(gen, tests):
        die("\nboundary coverage failed — fix .oa/gen.py and rerun")


def generate(c, force=False, report=False):
    """Write tests/hidden/*.in from .oa/gen.py, then check boundary coverage.

    `report` marks the explicit `gen` command, as against the implicit calls judge
    and answers make on every run. Those two want silence when there is nothing to
    do; `gen` still owes an answer, because checking coverage is most of why anyone
    runs it — and because a `gen` that fails coverage leaves the cache behind, so a
    second `gen` printing nothing would read as the failure having cleared itself.
    """
    refuse_template(ROOT / ".oa" / "gen.py")
    gen = load_module(ROOT / ".oa" / "gen.py", "oa_gen")
    if gen is None:
        die("need .oa/gen.py to judge")
    HIDDEN.mkdir(parents=True, exist_ok=True)
    cached = sorted(HIDDEN.glob("*.in"))
    want = input_stamp(c)
    changed = stale(want)
    if cached and not force and not changed:
        if report:
            print(f"{DIM}{len(cached)} test inputs already current{X}")
            coverage_or_die(gen, [(f.stem, read(f)) for f in cached])
        return
    if cached and changed and not force:
        print(f"{Y}{why_stale(want, 'these tests')} — rebuilding them{X}")

    rng = random.Random(c["seed"])
    tests = []
    for i, item in enumerate(gen.cases(rng), 1):
        label, data = item if isinstance(item, tuple) else (None, item)
        if not data.endswith("\n"):
            data += "\n"
        tests.append((case_name(i, label), data))

    # Rewrite only what actually differs. An answer stays valid exactly as long as
    # the input that produced it is unchanged, so appending a case to gen.py should
    # cost one reference run rather than the whole suite — which is the entire point
    # of `answers` being a separate resumable pass.
    fresh = {name for name, _ in tests}
    for f in cached:
        if f.stem not in fresh:
            f.unlink()
            f.with_suffix(".out").unlink(missing_ok=True)
    kept = 0
    for name, data in tests:
        inp = HIDDEN / f"{name}.in"
        out = inp.with_suffix(".out")
        if not force and inp.exists() and read(inp) == data:
            kept += out.exists()
            continue
        write(inp, data)
        out.unlink(missing_ok=True)

    reuse = f"{DIM}, {kept} cached answers still valid{X}" if kept else ""
    print(f"{DIM}generated {len(tests)} test inputs{X}{reuse}")

    coverage_or_die(gen, tests)
    # Stamp only once coverage has passed, never before. The stamp is what every
    # other command reads as "this cache is current", and a cache that failed its
    # boundary check is not something to be current with: stamping first meant a
    # failed `gen` left a suite the next `judge` accepted on the silent fast path,
    # printing 100% over tests that never reached their own declared bounds. Left
    # unstamped it gets rebuilt and rechecked instead, so the failure stays failed.
    save_stamp(**want)


def run_reference(path, data, limit_ms):
    """Run a reference in a subprocess so the budget is actually enforceable."""
    argv = [sys.executable, str(RUNNER), str(path)]
    t0 = time.perf_counter()
    try:
        p = subprocess.run(argv, input=data.encode("utf-8"), capture_output=True,
                           timeout=limit_ms / 1000.0)
    except subprocess.TimeoutExpired:
        return "TLE", "", "", (time.perf_counter() - t0) * 1000
    ms = (time.perf_counter() - t0) * 1000
    if p.returncode != 0:
        return "RE", "", decode(p.stderr).strip(), ms
    return "OK", decode(p.stdout), "", ms


def answers(c, force=False):
    """Compute tests/hidden/*.out. Slow by design, and resumable: every answer is
    written the moment it lands, so an interrupt costs one test, not the suite."""
    ins = sorted(HIDDEN.glob("*.in"))
    if not ins:
        die("no test inputs — run: python3 oa.py gen")
    if not BRUTE.exists():
        die(f"missing {BRUTE.relative_to(ROOT)}")
    refuse_template(BRUTE)
    limit = c["ref_time_limit_ms"]

    # An edited reference invalidates every answer it produced, and there is no way
    # to know which ones it would have changed. Recomputing all of them is the cost
    # of the edit — silently keeping answers the current reference disagrees with is
    # the alternative, and that grades the user against a solution nobody is running.
    want = answer_stamp()
    if stale(want) and any(f.with_suffix(".out").exists() for f in ins):
        print(f"{Y}{why_stale(want, 'these answers')} — recomputing all {len(ins)}{X}")
        force = True

    todo = [f for f in ins if force or not f.with_suffix(".out").exists()]
    # Stamp before computing, never after. A stamp written on completion would be
    # missing after an interrupt, the next run would read that as "the reference
    # changed", and it would throw away every answer that did land — turning the
    # resumable pass into one that has to start over.
    save_stamp(**want)
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
        # Alongside the answer, not after the loop. The pass is resumable and expected
        # to be interrupted, and a resumed run only recomputes what has no .out — so a
        # timing left unwritten here is lost for good, and the scaling report quietly
        # drops its reference comparison.
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
    """Least-squares slope of log(y) against log(x): the k in y ~ x^k, plus the
    fraction of the variance that slope explains. Returns (k, r2), or None when the
    data is too thin or too flat to say anything."""
    pts = [(x, y) for x, y in points if x and x > 0 and y and y > 0]
    if len(pts) < 3:
        return None
    n = len(pts)
    lx = [math.log(x) for x, _ in pts]
    ly = [math.log(y) for _, y in pts]
    mx, my = sum(lx) / n, sum(ly) / n
    sxx = sum((a - mx) ** 2 for a in lx)
    syy = sum((b - my) ** 2 for b in ly)
    sxy = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    if sxx <= 1e-9 or syy <= 1e-9:
        return None
    return sxy / sxx, sxy * sxy / (sxx * syy)


def fit_curve(pts, min_signal, floor_note, min_spread=3.0, min_r2=0.9):
    """(k, r2) when a curve through these points means something, otherwise a short
    sentence saying why it does not.

    Every guard is asked of the points that will *actually* be fitted. Gating on a
    superset is what let a cold-start outlier — at the smallest input, discarded by
    the fit itself — unlock the fit it took no part in, and report a merge sort as
    n^0.60.

    r2 is the decisive one. Tests of the same size but different *shape* — sorted
    versus random at 2 MB — cost visibly different time, so points sitting together
    in x and far apart in y are not samples of one curve and no amount of range in x
    rescues a line drawn through them.
    """
    pts = [p for p in pts if p[1] > 0]
    if len(pts) < 3:
        return f"only {len(pts)} of the largest tests rose clear of {floor_note}"
    xs = [x for x, _ in pts]
    if max(xs) / min(xs) < min_spread:
        return (f"the {len(pts)} tests clear of {floor_note} span only "
                f"{max(xs) / min(xs):.1f}x in input size")
    if max(y for _, y in pts) < min_signal:
        return f"nothing rose far enough above {floor_note} to measure"
    got = fit_exponent(pts)
    if got is None:
        return "the measurements are degenerate"
    if got[1] < min_r2:
        return (f"the {len(pts)} largest tests do not lie on one curve (R²={got[1]:.2f}) "
                f"— test shape is costing more than test size")
    return got


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

    # Fit only above a size floor. On the tiny tests the runtime *is* the process
    # startup and the memory *is* the runtime baseline, so their y values are noise
    # sitting at x values spanning several decades — including them flattens the
    # slope of a perfectly linear solution towards zero.
    big = [r for r in all_pts if r[1] >= all_pts[-1][1] / 1000.0]
    spread = big[-1][1] / big[0][1] if len(big) >= 2 else 1
    if len(big) < 4 or spread < 10:
        print(f"  {DIM}only {len(big)} tests within 1000x of the largest, spanning {spread:.0f}x "
              f"— too narrow to fit. Add a geometric size ladder to .oa/gen.py.{X}")
        return

    # Points sitting near the floor are jitter, not work. They span decades of x at a
    # near-constant y, which flattens the slope of even a quadratic solution towards
    # zero, so they are dropped rather than fitted.
    #
    # Both filters are absolute-and-relative, for the same two reasons. The absolute
    # part is the instrument: a few milliseconds is the clock's own resolution, and a
    # few MB is an allocator rounding. The relative part is run-to-run variation, which
    # scales with the runtime and not with the instrument — CPython's startup wanders
    # by ten-odd milliseconds between runs, so an absolute 3 ms floor on its own admits
    # a whole suite of fast tests as a band of noise a few ms above t_base. Those then
    # outnumber the handful of points that did real work and take R² down with them,
    # which reads as "test shape is costing more than test size" when the truth is that
    # nothing was being measured. Keep only what is large against the biggest signal.
    t_sig = [(r[1], r[2] - t_base) for r in big if r[2] > t_base]
    t_top = max((y for _, y in t_sig), default=0)
    t_pts = [(x, y) for x, y in t_sig if y >= max(3.0, t_top / 16)]
    m_sig = [(r[1], r[3] - m_base) for r in big if r[3] and r[3] > m_base]
    m_top = max((y for _, y in m_sig), default=0)
    m_pts = [(x, y) for x, y in m_sig if y >= m_top / 16]
    kt = fit_curve(t_pts, max(25.0, 2 * t_base), f"the {t_base:.0f} ms startup floor")
    km = fit_curve(m_pts, 4 << 20, f"the {human_bytes(m_base)} baseline heap")

    if isinstance(kt, tuple):
        note = f"  {Y}— above linear{X}" if kt[0] > 1.35 else ""
        print(f"  {B}time   ~ n^{kt[0]:.2f}{X}{note}  {DIM}({t_base:.0f} ms startup subtracted, "
              f"{len(t_pts)} points, R²={kt[1]:.2f}){X}")
    else:
        print(f"  {DIM}time:   no exponent — {kt}.")
        print(f"          A solution too fast to characterise is a good sign; a suite whose"
              f"\n          largest tests cluster is a reason to widen the size ladder.{X}")
    if isinstance(km, tuple):
        print(f"  {B}memory ~ n^{km[0]:.2f}{X}  {DIM}({human_bytes(m_base)} runtime baseline "
              f"subtracted, R²={km[1]:.2f}){X}")
    else:
        print(f"  {DIM}memory: no exponent — {km}.{X}")

    ref = ref_timings()
    if ref:
        name, size, ms, _ = rows[-1]
        rms, who = ref.get(name, (None, None))
        if rms:
            print(f"  {DIM}{who} took {rms / 1000:.1f}s on {name} vs your {ms:.0f} ms — "
                  f"it is Python, so treat the ratio as a sanity check, not a benchmark{X}")


def execute(c, argv, tests, reveal, label):
    """reveal caps how many failures are explained. It has to cap the one-line
    reason too, not just the input/expected/actual block: "token 0: got '0', want
    '200000000000000'" hands over the answer, and --reveal 0 is meant to be the
    real thing — a score and nothing else."""
    passed = 0
    shown = 0
    slowest = 0.0
    over = skipped = 0
    stats = []
    # Which tests went red, not just how many. A wrong output shape fails every test
    # at once while a wrong answer key fails a subset, so the *pattern* of failure is
    # what tells the two apart — see check_plumbing.
    failed = []

    # The first process launched pays cold-start cost none of the others do: loading
    # a just-compiled binary, resolving its DLLs, a first-touch antivirus scan. Here
    # that is ~40 ms against ~8 ms for every later run, and it lands on whichever test
    # runs first — usually the smallest, where it reads as a tiny input being the
    # slowest in the suite and drags the scaling fit with it. Spend one run on the
    # smallest input, cheap ones only, and throw the result away.
    warm = min((i for _, i, e in tests if e is not None), key=len, default="")
    if warm and len(warm) <= (1 << 16):
        run_once(argv, warm, c["time_limit_ms"])

    for name, inp, exp in tests:
        if exp is None:
            # A sample .in with no .out. samples() returns these deliberately, so
            # scoring one is impossible rather than merely inconvenient — say which
            # file is missing and leave it out of the denominator.
            print(f"  {Y}SKIP{X} {name:<18} {DIM}no {name}.out to compare against{X}")
            skipped += 1
            continue
        status, out, err, ms, mem = run_once(argv, inp, c["time_limit_ms"])
        # Only a run that finished inside the limit contributes a real measurement.
        # A killed process reports limit*3 by construction, and a crashing one on
        # Windows spends seconds in the error reporter — averaging either into
        # "slowest" prints a number that appears nowhere in the rows above it.
        if status == "OK":
            slowest = max(slowest, ms)
        elif status == "TLE":
            over += 1
        used = f"{DIM}{ms:6.0f} ms  {human_bytes(mem):>9}{X}"
        if status == "OK":
            ok, why = compare(c, inp, exp, out)
            stats.append((name, len(inp), ms, mem))
            if ok:
                passed += 1
                print(f"  {G}PASS{X} {name:<18} {used}")
                continue
            failed.append(name)
            explain = shown < reveal
            print(f"  {R}FAIL{X} {name:<18} {used}{f'  {DIM}{why}{X}' if explain else ''}")
            if explain:
                show_failure(name, inp, exp, out, why)
                shown += 1
        elif status == "TLE":
            failed.append(name)
            print(f"  {Y}TLE {X} {name:<18} {DIM}>{c['time_limit_ms']} ms{X}")
        else:
            failed.append(name)
            print(f"  {R}RE  {X} {name:<18} {DIM}{err.strip().splitlines()[0] if err.strip() else ''}{X}")
            if shown < reveal:
                print(f"{R}{err.strip()[:2000]}{X}")
                shown += 1
    total = len(tests) - skipped
    if not total:
        print(f"\n{R}{B}{label}: nothing to score{X} — every test was skipped for want "
              f"of an expected output")
        return 0, 0, stats, failed

    timing = (f"slowest {slowest:.0f} ms" if slowest else "nothing finished")
    timing += f" / limit {c['time_limit_ms']} ms" + (f", {over} over it" if over else "")
    if skipped:
        timing += f", {skipped} skipped"
    pct = 100.0 * passed / total
    bar = G if passed == total else (Y if passed else R)
    print(f"\n{bar}{B}{label}: {passed}/{total} ({pct:.0f}%){X}   {DIM}{timing}{X}")
    return passed, total, stats, failed


def check_against_samples(c, path, title):
    """Does this reference reproduce the sample outputs from the statement?

    If it does not, the statement was misread — fix that before the user burns an
    hour chasing a phantom bug in their own code. Every reference gets this, the
    fast one included: it is the only place either is checked against ground truth
    the harness did not produce itself.
    """
    ref = load_module(path, f"oa_ref_{title}")
    bad = checked = 0
    print(f"\n{B}{title} vs samples{X}")
    for name, inp, exp in samples():
        if exp is None:
            print(f"  {Y}SKIP{X} {name} (no .out file)")
            continue
        checked += 1
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
    if not checked:
        # "consistent" over zero comparisons is the most dangerous output this
        # harness could print: it is the green light on the one check that catches
        # a misread statement, and a fresh scaffold is exactly this state.
        print(f"  {R}{B}NOTHING TO CHECK{X} — no tests/samples/*.in with a matching .out")
        print(f"  {DIM}Copy the statement's examples in verbatim first. Until then nothing"
              f"\n  has ever compared {title} against ground truth.{X}")
        return 1
    print(f"  {(R + B + 'MISMATCH') if bad else (G + B + 'consistent')}{X} {DIM}({checked} samples){X}")
    return bad


def answer_key_report(c):
    """Where the answers came from, and how much of the suite that actually covers.

    The samples are the only truth the harness did not generate itself, and a
    statement's examples are small by nature — so the answers to the tests that do the
    discriminating rest on reference.py being right about shapes no sample exercises.
    Nothing here can prove that it is. What this can do is say how wide the gap is,
    using the quantities LIMITS already declares, and name the one gate that closes it.

    A disclosure, never a gate: no statement ships a max-size example, so failing on
    an unsampled range would fail every workspace ever built. It prints what it knows
    and lets the author decide, which is the same bargain the scaling report makes.
    """
    hid = [(f.stem, read(f)) for f in sorted(HIDDEN.glob("*.in"))
           if f.with_suffix(".out").exists()]
    if not hid:
        return
    samp = [(n, i) for n, i, e in samples() if e is not None]

    print(f"\n{B}Answer key{X}")
    if FAST.exists():
        print(f"  {DIM}{len(samp)} samples are the only external ground truth. "
              f"{len(hid)} hidden answers come\n  from .oa/ref/, where two independent "
              f"references cross-check each other.{X}")
    else:
        print(f"  {DIM}{len(samp)} samples are the only external ground truth. "
              f"{len(hid)} hidden answers come\n  from .oa/ref/reference.py alone.{X}")

    gen = load_module(ROOT / ".oa" / "gen.py", "oa_gen")
    lim = getattr(gen, "LIMITS", None)
    measure = getattr(gen, "measure", None)

    def span(tests):
        """Range of each declared quantity actually present in these inputs."""
        got = {}
        for _, data in tests:
            try:
                m = measure(data)
            except Exception:
                # measure() is written against generated inputs; a sample it chokes on
                # is worth neither a crash nor a diagnosis here. Coverage owns that.
                continue
            for k, v in m.items():
                if k not in lim:
                    continue
                vals = [v] if isinstance(v, (int, float)) else list(v)
                if not vals:
                    continue
                lo, hi = got.get(k, (vals[0], vals[0]))
                got[k] = (min(lo, min(vals)), max(hi, max(vals)))
        return got

    if lim and measure:
        s, t = span(samp), span(hid)
        w = max(len(k) for k in lim)
        gaps = []
        for k in lim:
            tv = t.get(k)
            if tv is None:
                continue
            sv = s.get(k)
            reach = f"{sv[0]} .. {sv[1]}" if sv else "never reached"
            print(f"  {k:<{w}}  {DIM}samples{X} {reach:<18}  {DIM}tests{X} {tv[0]} .. {tv[1]}")
            if sv is None or sv[0] > tv[0] or sv[1] < tv[1]:
                gaps.append(k)
        if gaps:
            print(f"  {Y}outside the sampled range of {', '.join(gaps)} nothing has checked "
                  f"the\n  answers against the statement{X}")

    print(f"  {DIM}selfcheck --entry is what covers that, and only if the stand-in's "
          f"algorithm was\n  re-derived from the statement — a port of reference.py shares "
          f"its mistakes,\n  agrees with it everywhere, and scores 100%.{X}")


def survives_inputs(c, argv, tests):
    """Feed every generated input to the real entry file and require it not to die.

    The stub returns a placeholder, so it cannot be scored — but a crash or a hang is
    unambiguous whatever the algorithm is: whatever it read, it was not what
    .oa/gen.py wrote. This is the half of the plumbing check that examines the file
    the user will actually edit, rather than a stand-in for it.
    """
    bad = []
    for name, inp, _ in tests:
        status, _, err, _, _ = run_once(argv, inp, c["time_limit_ms"])
        if status in ("RE", "TLE"):
            bad.append((status, name, err.strip().splitlines()[-1] if err.strip() else status))
    if not bad:
        print(f"  {G}OK{X}   {DIM}{c['entry']} reads all {len(tests)} generated inputs "
              f"without dying{X}")
        return 0
    print(f"  {R}BAD{X}  {c['entry']} dies on {len(bad)} of {len(tests)} generated inputs")
    for status, name, first in bad[:3]:
        print(f"       {R}{status}{X} {name:<18} {DIM}{first}{X}")
    print(f"  {DIM}The stub cannot be scored, but it can be made to run: crashing or hanging"
          f"\n  means it did not read the format .oa/gen.py writes.{X}")
    return 1


def check_checker(c, scored):
    """Does .oa/checker.py ever say no?

    `checker: custom` replaces compare() outright with a file written by hand for this
    one problem, and nothing else here ever asks that file to reject anything: the
    sample check, the coverage table and the plumbing check all consult it, and all
    three stay green while it accepts everything. A checker stuck at True scores a
    solution that prints nothing at 100%, which is the same failure the plumbing check
    exists to prevent, arriving through the one door that check leaves open.

    So hand it one test's input with a different test's answer — wrong by construction
    — and require it to notice at least once. Once, not always: a checker for a
    constructive problem judges the answer against the input alone, and two inputs
    similar enough for one's answer to satisfy the other is unlikely but not absurd.
    Never rejecting anything is the failure worth naming.
    """
    pairs = []
    for i, (name, inp, exp) in enumerate(scored):
        rest = scored[i + 1:] + scored[:i]
        other = next((e for _, _, e in rest if e.split() != exp.split()), None)
        if other is not None:
            pairs.append((inp, exp, other))
        if len(pairs) >= 8:
            break

    if not pairs:
        print(f"  {DIM}every scored test has the same expected output, so there is "
              f"nothing to\n  cross against it — the checker went unexercised{X}")
        return 0

    rejected = 0
    for inp, exp, other in pairs:
        try:
            ok, _ = compare(c, inp, exp, other)
        except Exception:
            # Blowing up on an answer that makes no sense for this input is a
            # rejection. It is not a reason to take selfcheck down.
            ok = False
        rejected += not ok

    if rejected:
        print(f"  {G}OK{X}   {DIM}.oa/checker.py rejects another test's answer "
              f"({rejected} of {len(pairs)} crossed pairs){X}")
        return 0
    print(f"  {R}BAD{X}  .oa/checker.py accepted another test's answer as correct, on "
          f"all {len(pairs)} pairs")
    print(f"  {DIM}It is not comparing anything, so it cannot fail a solution either: an\n"
          f"  entry file that prints nothing would score 100%. Every other gate here\n"
          f"  consults this same checker, so all of them stay green while it does.{X}")
    return 1


def stand_in(c):
    """What to call the known-correct stand-in.

    Its suffix has to match the entry file's, because --entry goes through the same
    build() and so to the same toolchain: `_check.py` in a C++ workspace — which is
    the default — reaches g++ and comes back as a compile error rather than as the
    gate this is meant to be.
    """
    return f"_check{Path(c['entry']).suffix}"


def check_plumbing(c, entry):
    """Does the entry file's I/O agree with the generator and the reference?

    This is the one failure the harness cannot show the user. A main file that reads a
    different format than .oa/gen.py writes, or prints a different shape than
    .oa/ref/reference.py, turns every hidden test red at once — and from the user's
    side that is indistinguishable from a wrong algorithm, on a workspace whose whole
    promise is that a red test means their code. Nothing else here catches it:
    selfcheck proves the reference matches the statement, `run` proves the stub builds,
    and both stay green while the two halves disagree with each other.

    Two halves, because neither is enough alone. Feeding the generated inputs to the
    real entry catches a wrong *parse* in the file that actually ships. Scoring a
    known-correct stand-in at 100% catches a wrong *output shape*, which no stub can
    demonstrate — at the cost of only proving it for the stand-in, so the two together
    are what make the answer trustworthy.
    """
    ins = sorted(HIDDEN.glob("*.in"))
    if not ins:
        return 0                       # nothing generated yet; the caller already said so

    print(f"\n{B}Plumbing{X} {DIM}— does {c['entry']}'s I/O match the suite?{X}")
    bad = survives_inputs(c, build(c), [(f.stem, read(f), None) for f in ins])

    scored = [t for t in samples() + hidden() if t[2] is not None]
    if entry is None:
        if not hidden():
            # Before `answers` there is nothing to score against, and step 7 runs
            # selfcheck here on purpose — to catch a misread statement before paying
            # for the slow pass. Not applicable is not the same as unchecked.
            print(f"  {DIM}output shape not checkable until answers exist — rerun with "
                  f"--entry after `answers`{X}")
            return bad
        print(f"  {R}{B}OUTPUT SHAPE UNCHECKED{X} — nothing has confirmed that {c['entry']} prints\n"
              f"       the shape .oa/ref/reference.py answers in.")
        me = stand_in(c)
        print(f"  {DIM}A mismatch fails every hidden test at once and looks exactly like a wrong\n"
              f"  algorithm from the user's side, so it is the one failure they cannot debug.\n"
              f"  Copy {c['entry']} to {me} and fill in the algorithm — copy it rather than\n"
              f"  writing one from scratch, or the stand-in re-implements the parsing and all\n"
              f"  this proves is that it agrees with itself. Then:\n"
              f"      python3 oa.py selfcheck --entry {me}\n"
              f"  and delete {me} once it scores 100%.{X}")
        return bad + 1

    p = (ROOT / entry).resolve()
    if not p.exists():
        die(f"--entry {entry}: no such file")
    try:
        rel = p.relative_to(ROOT)
    except ValueError:
        die(f"--entry {entry}: must live inside the workspace")
    if rel == Path(c["entry"]):
        die(f"--entry {entry} is the workspace's own entry file.\n"
            f"  The point is to score a *known-correct* solution against the suite, and\n"
            f"  {c['entry']} is the stub the user is meant to fill in.")
    if c.get("run_cmd"):
        # build() hands back run_cmd untouched, so --entry would build the stand-in and
        # then run the stub — reporting the stub's score as the stand-in's, which reads
        # as "the workspace is broken" on a workspace that is fine. Say so instead.
        die(f"--entry cannot redirect a custom run_cmd.\n"
            f"  build_cmd/run_cmd in problem.json name their own files, so {rel} would be\n"
            f"  ignored and {c['entry']} scored in its place.\n"
            f"  Point run_cmd (and build_cmd) at {rel} for the length of this check instead.")
    if not scored:
        print(f"  {R}nothing to score{X} — no samples and no answers yet")
        return bad + 1

    print(f"  {DIM}scoring {rel} — a correct solution through the real tests and checker{X}")
    passed, total, _, failing = execute(c, build({**c, "entry": str(rel)}), scored,
                                        1, "Plumbing")
    if passed == total and total:
        print(f"  {DIM}output shape agrees with the answer key, and a correct solution fits"
              f"\n  the time limit. Delete {rel}.{X}")
        return bad

    # Which failed matters as much as how many, and the two cases send the author to
    # different files. A format mismatch is systematic: the stand-in and the reference
    # disagree about what an answer *looks like*, so nothing can match and everything
    # goes red. A subset going red means they agree on the shape and disagree on the
    # value — the algorithms differ, and the samples cannot arbitrate because both
    # already reproduce them.
    if passed == 0:
        print(f"\n{R}{B}the workspace is broken, not the solution{X} — a correct solution "
              f"scored\n  0/{total}. Every test failed, which is what a *format* mismatch "
              f"looks like:\n  reconcile {c['entry']}'s parsing and printing against the format "
              f".oa/gen.py\n  emits and the shape .oa/ref/reference.py returns, then rerun.")
    else:
        shown = ", ".join(failing[:5])
        more = f", +{len(failing) - 5} more" if len(failing) > 5 else ""
        print(f"\n{R}{B}the answer key and the stand-in disagree{X} — a correct solution "
              f"scored\n  {passed}/{total}, failing {shown}{more}.")
        print(f"  {DIM}A wrong output shape fails every test at once. A subset failing means "
              f"these\n  two agree on the shape and disagree on the answer, so one of "
              f".oa/ref/reference.py\n  and {rel} has misread the statement — and the samples "
              f"cannot say which, since\n  both already reproduce them. Work the failing inputs "
              f"by hand; whichever file\n  the hand-worked answer contradicts is the wrong one.{X}")
    return bad + 1


def selfcheck(c, entry=None):
    if not BRUTE.exists():
        die(f"no {BRUTE.relative_to(ROOT)}")
    refuse_template(ROOT / ".oa" / "gen.py")
    refuse_template(BRUTE)
    bad = check_against_samples(c, BRUTE, "reference")
    if FAST.exists():
        bad += check_against_samples(c, FAST, "reference_fast")

    ins = sorted(HIDDEN.glob("*.in"))
    if ins:
        # selfcheck is the last gate before hand-over and the only command that reads
        # the cache without rebuilding it, so it has to say when the cache no longer
        # matches what would be built now — otherwise it green-lights a coverage
        # table describing tests the judge will replace on its next run.
        # Step 7 of the workflow runs selfcheck *before* answers, so an empty answer
        # cache is the expected state here, not a stale one. Only judge provenance
        # that exists.
        outs = [f for f in ins if f.with_suffix(".out").exists()]
        if not outs:
            print(f"\n{DIM}no answers computed yet — python3 oa.py answers, or let judge do it{X}")
        ins_drift = stale(input_stamp(c))
        out_drift = stale(answer_stamp()) if outs else []
        if ins_drift or out_drift:
            # Which half is stale decides both what judge will rebuild and whether the
            # coverage table printed below still describes the suite being reported on.
            effect = ("the coverage table below describes a suite the next judge run "
                      "will regenerate" if ins_drift else
                      "the next judge run will recompute every answer")
            fix = "gen && python3 oa.py answers" if ins_drift else "answers"
            print(f"\n{R}tests/hidden is stale{X} — it no longer matches the current"
                  f" {', '.join(ins_drift + out_drift)}.\n  {DIM}{effect}."
                  f"\n  Run: python3 oa.py {fix}{X}")
            bad += 1
        gen = load_module(ROOT / ".oa" / "gen.py", "oa_gen")
        print(f"\n{B}Boundary coverage{X} {DIM}({len(ins)} cached tests){X}")
        if not check_limits(gen, [(f.stem, read(f)) for f in ins]):
            bad += 1
    else:
        print(f"\n{Y}no tests generated yet — run: python3 oa.py gen{X}")
    if c["checker"] == "custom":
        print(f"\n{B}Checker{X} {DIM}— does .oa/checker.py ever say no?{X}")
        bad += check_checker(c, [t for t in samples() + hidden() if t[2] is not None])
    answer_key_report(c)
    bad += check_plumbing(c, entry)
    return 1 if bad else 0


# ---------------------------------------------------------------- entrypoints

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "judge", "gen", "answers", "case", "selfcheck"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--reveal", type=int, default=None,
                    help="how many failing tests to explain in full "
                         "(default: every sample for run, none for judge)")
    ap.add_argument("--force", action="store_true", help="discard cached tests / answers")
    ap.add_argument("--entry", help="selfcheck: score this known-correct solution instead "
                                    "of the stub, to prove the entry file's I/O matches "
                                    "the generator and the reference")
    a = ap.parse_args()
    c = cfg()

    if a.cmd == "gen":
        # --force is what discards the answer cache; `gen` on its own must not. An
        # input that comes out byte-identical keeps the answer already computed for
        # it, so appending a case to gen.py costs one reference run instead of the
        # whole pass. Forcing here unconditionally took that away from the one command
        # the workflow tells you to run after every edit, which is precisely where it
        # was supposed to pay off.
        generate(c, force=a.force, report=True)
        return

    if a.cmd == "answers":
        generate(c, force=a.force)
        answers(c, force=a.force)
        return

    if a.cmd == "selfcheck":
        sys.exit(selfcheck(c, a.entry))

    argv = build(c)

    if a.cmd == "run":
        ts = samples()
        if not ts:
            die("no sample tests in tests/samples/")
        print(f"{B}Samples{X}")
        # Explain every failing sample, not just the first. A sample's expected output
        # is printed in the statement and sitting in tests/samples/*.out, so there is
        # nothing here to give away — and "Run Code" that will not show you why a
        # sample failed is the one button on a real OA that always does.
        p, t, _, _ = execute(c, argv, ts, len(ts) if a.reveal is None else a.reveal, "Samples")
        # `and t`: a suite that scored nothing has not passed, and p == t == 0 would
        # otherwise exit 0 and read as green.
        sys.exit(0 if p == t and t else 1)

    if a.cmd == "case":
        pool = {n: (n, i, e) for n, i, e in samples() + (hidden() if HIDDEN.exists() else [])}
        if a.name not in pool:
            die(f"no such test {a.name!r}; have: {', '.join(sorted(pool))}")
        # Naming a test is an explicit request to see it, so `case` explains by default
        # where `judge` does not. This is the deliberate way past the score-only wall.
        p, t, _, _ = execute(c, argv, [pool[a.name]], 1 if a.reveal is None else a.reveal, "Case")
        sys.exit(0 if p == t and t else 1)

    # judge
    generate(c, force=a.force)
    answers(c, force=a.force)
    ts = samples() + hidden()
    # Count what can actually be scored, so the header agrees with the denominator
    # below it when a sample has no .out.
    print(f"{B}Judging {c.get('name', 'solution')} — "
          f"{sum(1 for _, _, e in ts if e is not None)} tests{X}")
    # Submit returns a score. The expected output of a hidden test *is* the answer, so
    # a real OA hands back a percentage and leaves you to work out which case broke you
    # — and a harness that volunteers the diff has quietly turned Submit into Run.
    p, t, stats, _ = execute(c, argv, ts, 0 if a.reveal is None else a.reveal, "Score")
    if p == t and t:
        complexity_report(c, stats)
    elif a.reveal is None:
        # But this is still a practice tool, and a score with no route to a diff is a
        # dead end. Name the two ways through, once, without printing any of it.
        print(f"{DIM}  --reveal 1 explains the first failure; "
              f"`case <name>` replays one test in full{X}")
    sys.exit(0 if p == t and t else 1)


if __name__ == "__main__":
    main()
