---
name: oa-practice
description: Use when the user has a coding-assessment problem they want to solve themselves rather than be handed — a pasted or screenshotted statement with constraints and sample I/O, or any mention of OA, online assessment, 笔试, 机考, take-home coding test, HackerRank/Codility/牛客/Codeforces-style problems, or a problem that "isn't on LeetCode" so there is nothing to run their code against. Also for "set this one up for me", "make me a test harness for this", "I want to practice this problem".
---

# OA Practice Harness

The user wants the OA experience for a problem that has no online judge: write code,
hit run on the samples, hit submit, get a score. This skill builds that workspace — a
main file with the I/O already parsed, the statement's samples behind a one-click
runner, and a hidden judge that scores their solution on 20+ generated tests.

The one rule that makes it worth doing: **never write the solution.** The `solve()`
body stays a `// TODO`. Everything else — parsing, printing, samples, hidden tests,
scoring — is yours to build. If the user later asks for hints or the answer, that is a
separate request and fine to fulfill.

## What gets produced

```
<slug>/
├── main.cpp / main.py  # I/O parsed and printed; solve() is a stub for the user
├── problem.json        # language, time limit, checker mode
├── README.md           # restated statement, constraints, complexity target
├── run.sh, run.cmd     # samples only, with diffs                    ("Run Code")
├── judge.sh, judge.cmd # all tests, prints k/n (p%) and nothing else  ("Submit")
├── oa.sh, oa.cmd       # any other harness command, same interpreter probe
├── oa.py               # harness engine (run / judge / gen / answers / case / selfcheck)
├── tests/samples/      # sample1.in, sample1.out, sample2.in, ...
└── .oa/
    ├── gen.py          # declared constraint bounds + edge cases + randoms + stress
    ├── checker.py      # only when multiple outputs are valid
    └── ref/            # SPOILERS — one level down so they are not sitting in the way
        ├── reference.py       # brute force: the oracle
        └── reference_fast.py  # intended algorithm; only when brute can't reach the limits
```

Nothing ships the tests themselves: `.oa/gen.py` produces the inputs and
`.oa/ref/reference.py` the expected outputs, deterministically from a seed, which is
what makes a 20+ test suite cheap and reproducible. Be straight with the user about
what "hidden" means — once generated they sit in `tests/hidden/`, so this is
honour-system, not sealed.

## Workflow

### 1. Read the statement and pin down I/O

Everything downstream depends on the exact input format. Most of it is inferable from
the samples — match the sample input token by token against the prose. Ask the user
only about what genuinely isn't there:

- **No sample I/O at all** → ask for at least one example, or write one yourself (step 4 says how, and it matters how) and flag that it is unverified.
- **Function-signature style** (LeetCode-ish: "implement `int maxProfit(vector<int>& prices)`") → keep the same shape: `main()` reads stdin and calls their function, so the file still runs standalone but the signature is what they'd paste into the real OA.
- **Multiple test cases per input file** (`T` on the first line) → common in 笔试; check the samples for it.
- **Ambiguous output formatting** (float precision, trailing spaces, ordering) → default to `"checker": "token"` (whitespace-insensitive), `"float"` with an eps, or a custom checker. Say which you picked.

### 2. Scaffold

```bash
python3 <skill>/scripts/scaffold.py <slug> --dir <dest> --lang cpp --tl 3000
```

`python3` throughout this file means whatever the local Python 3 is — often `py` on
Windows, sometimes only an absolute path into a conda install. The wrappers probe PATH
and then fall back to the interpreter that ran `scaffold.py`, recorded in
`.oa/python-path`. If one still exits 127, set `OA_PYTHON`.

Default to C++17, but **check for a compiler first** — a workspace that cannot build is
worse than a Python one. macOS has `clang++` only after `xcode-select --install`;
Windows has nothing until MSYS2. With no `g++`/`clang++` on PATH, scaffold
`--lang python` and say why.

Time limit: 3000 ms unless the statement says otherwise; tighten to 1000–2000 ms when
the point of the problem is that the naive approach is too slow. Plan C++ at **10⁸
operations per second** — deliberately pessimistic, so the figure stays safe — and
**CPython at ~10⁷**, call it 30x slower.

| n up to | fits in ~1 s of C++ |
|---|---|
| 10⁸ | O(n) |
| 10⁶ | O(n log n) |
| 5·10³ | O(n²) |
| 300 | O(n³) |
| 22 | O(2ⁿ) |
| 11 | O(n!) |

That settles both the `--tl` value and the complexity target for the README. When the
constraints imply the intended solution — `n <= 2*10^5` wants O(n log n) — a limit
generous enough to also let O(n²) through has quietly made the problem easier. If you
fell back to Python, re-derive rather than scale: 30–50 ms is interpreter startup
before a line runs, and at 30x a limit that cleanly separates O(n log n) from O(n²) in
C++ can fail both.

The scaffold also drops in a README skeleton and `.oa/gen.py` + `.oa/ref/reference.py`
as a **worked example for a different problem**, each carrying a `TEMPLATE = True`
line. Nothing runs until you have rewritten them and deleted that line — left alone
they generate a clean, green, entirely wrong suite.

### 3. Write the main file — plumbing only

Parse into clean types, call `solve()`, print. The user should be able to write the
algorithm without ever thinking about `cin` or `sys.stdin`. Keep the stub honest: a
`return 0;` placeholder that fails the samples is correct behaviour, not a bug.

`references/authoring.md` has parsing patterns (graphs, grids, multi-test, queries).

### 4. Samples

**The statement gives the output** → copy it verbatim into `tests/samples/sampleN.in` /
`.out`. Verbatim matters: a "corrected" sample hides a misreading of the statement.

**It doesn't** — no examples, or an answer that lives in a diagram — → work one out by
hand and note in the README that the sample is yours rather than the statement's.

What it must never be is a reference's output. `selfcheck` is the only place either
reference meets ground truth the harness did not generate itself, so a sample filled in
by running the reference collapses that into the reference agreeing with itself: it
passes every time, prints `consistent`, and proves nothing — while the workspace may be
solving a subtly different problem than the one on the page.

### 5. `.oa/ref/reference.py` — the brute force

`solve(data: str) -> str` takes the whole input file, returns the whole output. Rewrite
the scaffold's body and delete its `TEMPLATE = True` line. Write the dumbest correct
thing: exponential enumeration, O(n³) DP, simulation. Its only job is to disagree with
the user when the user is wrong, so clarity beats speed — `oa.py answers` gives it
`ref_time_limit_ms` per test and caches every answer.

Whether it is fast enough is arithmetic: count the iterations it performs on the
largest generated case and divide by the CPython rate above. The 120 s default buys on
the order of 10⁹. **Tune that budget down, not just up** — it is spent in full on every
test the brute force cannot finish *before* `reference_fast` is tried, so five hopeless
tests at the default is ten minutes of dead waiting in step 7.

If it still can't answer the largest case, add `.oa/ref/reference_fast.py` with the
intended algorithm; the harness cross-checks the two wherever the brute force finishes
and only trusts the fast one past that point. **Never write only a fast reference** —
with nothing to cross-check against, a wrong one silently sets wrong answers on exactly
the tests that matter most.

### 6. `.oa/gen.py` — the test suite

**Transcribe the constraint line first**, before writing a single case. It becomes
`LIMITS`, and `measure()` reads those same quantities back off a generated input:

```python
# 0 <= n <= 2*10^5
# -10^9 <= a[i] <= 10^9
LIMITS = {"n": (0, 200000), "a_i": (-10**9, 10**9)}


def measure(data):
    t = data.split()
    n = int(t[0])
    return {"n": n, "a_i": [int(x) for x in t[1:1 + n]]}
```

`oa.py gen` then enforces what used to be a matter of remembering: every declared
endpoint must be reached, one test must attain every upper bound at once, and nothing
may fall outside a declared bound. Declare derived limits too — `Σn` over a multi-test
file, `n*m` for grids, `T`, alphabet size. Those are the ones that get skipped.

`cases(rng)` yields input strings, or `(label, data)` pairs so a failure reads
`FAIL t01-nzero`. Aim for **22–30 hidden tests**; the samples are judged on top:

1. **Shape edges** (~6–10, hand-written): all-equal, already-sorted and reverse-sorted, duplicates, disconnected graph, answer-is-zero, answer-is-the-whole-input. No bound declaration can express these.
2. **Small randoms** (~8–10): sizes 1–8 with a tiny value range, so collisions and duplicates happen constantly. These catch the most bugs per byte — with the brute force as an oracle this is random differential testing.
3. **A geometric size ladder** (~4–5): n = 1000, 4000, 16000 … up to the limit. Without a spread of sizes the scaling report has nothing to fit and says so.
4. **Max-size stress** (~2–4) **and the joint max corner**: the largest input allowed, plus one test with *every* declared bound maxed at once. That corner is where the 32-bit accumulator overflows.

Use only `rng` — reproducibility is what makes a failing test debuggable.

### 7. Verify before handing over

```bash
cd <slug> && ./oa.sh gen               # boundary coverage must come back clean
./oa.sh selfcheck                      # references must reproduce every sample
./oa.sh answers                        # the slow pass; resumable, cached
./oa.sh selfcheck --entry _check.py    # the plumbing check — see below; then delete it
./run.sh                               # stub must compile and fail loudly
```

On Windows, `.\oa.cmd gen` and so on, and `.\run.cmd`.

Iterate freely: `tests/hidden/` records the generator, seed and references it was built
from, so an edit rebuilds what it invalidates on the next command. A new case in
`gen.py` costs one reference run; a change to a reference costs the whole answer pass,
which is the honest price of having changed the oracle. `--force` is the only thing
that discards answers wholesale.

Go through the wrappers rather than calling `oa.py` directly — they probe for a working
interpreter, and a bare `python3` does not. `./run.sh` matters most: it is the only
step that proves the button the user will actually press works here.

`selfcheck` failing means the statement was misread. Fix it there, or the user spends
an hour debugging correct code against a wrong oracle. Step 4 is a prerequisite, not an
ordering preference: with `tests/samples/` empty there is nothing to check against, and
`selfcheck` fails rather than reporting a green it cannot justify.

**The plumbing check is not optional.** `_check.py` is the main file with the algorithm
actually written in — write it, run `selfcheck --entry _check.py`, delete it once
green. That command scores `_check.py` through the real tests and checker and demands
100%, *and* feeds every generated input to the main file itself and demands it not die.
Neither half suffices: the first catches a wrong output shape, which no stub can
demonstrate; the second catches a wrong parse in the file that actually ships.

Everything else here fails closed; this is the gap that failed open. A main file that
reads a different format than `gen.py` writes, or prints a different shape than
`reference.py` returns, turns every hidden test red at once — and from inside the
workspace that is indistinguishable from a wrong algorithm. It is the one failure the
user cannot debug, on a folder whose whole promise is that a red test means their code.

### 8. Hand it over

Present the folder and keep it short:

```
./run.sh      # samples                          (Windows: .\run.cmd)
./judge.sh    # submit — scores you on 24 tests   (Windows: .\judge.cmd)
```

The `.\` matters: neither PowerShell nor `cmd /c` runs a batch file from the current
directory without it.

Say what each button gives back, because they differ on purpose. `run` explains every
failing sample in full — the statement already prints those. `judge` returns a
percentage and a PASS/FAIL list and no diffs at all: on a real OA the expected output
of a hidden test *is* the answer. Name both ways through that wall up front:

```
./judge.sh --reveal 1   # explain the first failure: input, expected, yours
./oa.sh case t07-max    # replay any one test in full     (Windows: .\oa.cmd case ...)
```

Mention the time limit, the complexity target, and that `.oa/` and `tests/hidden/*.out`
will spoil them. Worth one line: a passing `judge` also prints a scaling report — time
and peak memory against input size with a fitted growth exponent — so they can see
whether they hit the intended complexity rather than just squeaking under the limit. It
declines to print an exponent it cannot stand behind, and on a fast solution that is
the usual outcome; say so, or the blank reads as a fault. Then get out of the way.

## Modes worth knowing

**Multiple valid answers** (any shortest path, any valid arrangement): set
`"checker": "custom"` and write `.oa/checker.py` with
`check(inp, expected, actual) -> bool | (bool, reason)`. Validate the user's output
against the input and compare its *score* to the reference's — never string-compare.

**Interactive / stateful problems**: out of scope. Say so and offer a fixed-transcript
approximation instead.

**Windows and macOS** both work, and a workspace built on one behaves identically on
the other — tests are written LF-only and fed to the solution as LF, so a `getline`
never sees a stray `\r`. Three caveats:

- `run.cmd` / `judge.cmd` are the entry points on Windows; the `.sh` ones need Git Bash or WSL. Invoke them as `.\run.cmd`.
- **`run.cmd` and `judge.cmd` are CRLF on purpose — never normalize them.** cmd.exe seeks through a batch file as it runs, and an LF-only one with a `for` block and a `goto` inside jumps to the wrong offset and executes fragments of its own source. `.gitattributes` pins them.
- Peak memory is exact on Windows but sampled on macOS and Linux, so a test finishing in a few milliseconds may report low or `n/a`.

**Very large inputs** (10⁶+ numbers): `gen` writes the inputs quickly; the slow part is
`answers`, which is a separate resumable command for exactly that reason. Run it
yourself before handing over so the user never waits.

**Follow-up problems**: scaffold each into its own folder under the same parent. Reuse
the harness — only `main`, samples, `ref/`, and `gen.py` change.

## Reference

- `references/authoring.md` — parsing patterns, generator recipes per problem family, checker examples, `problem.json` fields.
- `assets/harness/` — the template files scaffold copies.
- `assets/stubs/` — solution stubs per language.
