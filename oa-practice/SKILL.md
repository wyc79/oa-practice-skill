---
name: oa-practice
description: Use when the user has a coding-assessment problem they want to solve themselves rather than be handed — a pasted or screenshotted statement with constraints and sample I/O, or any mention of OA, online assessment, 笔试, 机考, take-home coding test, HackerRank/Codility/牛客/Codeforces-style problems, or a problem that "isn't on LeetCode" so there is nothing to run their code against. Also for "set this one up for me", "make me a test harness for this", "I want to practice this problem".
---

# OA Practice Harness

The user wants the OA experience for a problem that has no online judge: write code,
hit run on the samples, hit submit, get a score. This skill builds that workspace:
a main file with the I/O already parsed, the statement's samples behind a one-click
runner, and a hidden judge that scores their solution on 20+ generated tests.

The one rule that makes the whole thing worth doing: **never write the solution.**
The `solve()` body stays a `// TODO`. Everything else — parsing, printing, samples,
hidden tests, scoring — is yours to build. If the user later asks for hints or the
answer, that is a separate request and fine to fulfill.

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

Nothing ships the tests themselves — `.oa/gen.py` produces the inputs and
`.oa/ref/reference.py` the expected outputs, deterministically from a seed. That is
what makes a 20+ test suite cheap to build and reproducible. Be straight with the user
about what "hidden" means here: once generated they sit in `tests/hidden/`, so this is
honour-system, not sealed. `judge` itself behaves like the real thing by default — a
score and a PASS/FAIL list, no diffs and no expected values — and `--reveal N` is the
deliberate step out of that when they would rather learn than be scored.

## Workflow

### 1. Read the statement and pin down I/O

Everything downstream depends on the exact input format, so resolve it before writing
anything. Most of it is inferable from the samples — match the sample input text
token by token against the prose. Ask the user only about what genuinely isn't there:

- **No sample I/O at all** → ask for at least one example, or write one yourself (step 4 says how, and it matters how) and flag that it is unverified.
- **Function-signature style** (LeetCode-ish: "implement `int maxProfit(vector<int>& prices)`") → keep the same shape: `main()` reads stdin and calls their function, so the file still runs standalone but the signature is what they'd paste into the real OA.
- **Multiple test cases per input file** (`T` on the first line) → common in 笔试; check the samples for it.
- **Ambiguous output formatting** (float precision, trailing spaces, ordering) → default to `"checker": "token"` (whitespace-insensitive), `"float"` with an eps, or a custom checker. Say which you picked.

### 2. Scaffold

```bash
python3 <skill>/scripts/scaffold.py <slug> --dir <dest> --lang cpp --tl 3000
```

(`python3` throughout this file means whatever the local Python 3 is — often `py` on
Windows, sometimes only an absolute path into a conda or framework install. The
`run`/`judge` wrappers probe PATH and then fall back to the interpreter that ran
`scaffold.py`, recorded in `.oa/python-path`, so they keep working on machines where
`python3.exe` is only a Microsoft Store stub and `py` was never installed. If one
still exits 127, set `OA_PYTHON`.)

Default to C++17 — but check for a compiler first, because a workspace that cannot
build is worse than a Python one. macOS has `clang++` only after `xcode-select
--install`; Windows has nothing until MSYS2 or similar is installed. If there is no
`g++`/`clang++` on PATH, scaffold `--lang python` and say why.

Time limit: 3000 ms unless the statement says otherwise; tighten to 1000–2000 ms when
the point of the problem is that the naive approach is too slow.

What a limit buys, since every other number in this file follows from it: plan C++ at
**10⁸ operations per second**. That is deliberately pessimistic — it is roughly what
cache-missing, pointer-chasing code manages, while straight-line arithmetic runs 3–5x
that and a loop the compiler can vectorise runs far more. Planning with the floor is
what makes the figure safe. **CPython runs ~10⁷ loop iterations per second**, spanning
about 7·10⁶ when each iteration touches a dict to 3·10⁷ for a bare comparison over a
list — call it 30x slower than C++ for comparable work. Read the statement's constraint
line against that and the intended complexity usually falls out on its own:

| n up to | fits in ~1 s of C++ |
|---|---|
| 10⁸ | O(n) |
| 10⁶ | O(n log n) |
| 5·10³ | O(n²) |
| 300 | O(n³) |
| 22 | O(2ⁿ) |
| 11 | O(n!) |

That table settles two things at once: the limit to pass to `--tl`, and the complexity
target that goes in the README. When the constraints make the intended solution obvious
— `n <= 2*10^5` wants O(n log n) — a limit generous enough to also let O(n²) through has
quietly changed the problem into an easier one.

If you fell back to Python, re-derive the limit rather than scaling it: 30–50 ms is
interpreter startup before a line of the solution runs, and at 30x the constant factor a
limit that cleanly separates O(n log n) from O(n²) in C++ can end up failing both.

The scaffold also drops in a README skeleton to fill in as you go, and `.oa/gen.py` +
`.oa/ref/reference.py` as a **worked example for a different problem**, each carrying
a `TEMPLATE = True` line. The harness refuses to run until you have rewritten them and
deleted that line — left alone they generate a clean, green, entirely wrong suite,
which is the failure this whole design exists to prevent.

### 3. Write the main file — plumbing only

Parse into clean types, call `solve()`, print. The user should be able to write the
algorithm without ever thinking about `cin` or `sys.stdin`. Keep the stub honest — a
`return 0;` placeholder that fails the samples is correct behaviour, not a bug.

See `references/authoring.md` for parsing patterns (graphs, grids, multi-test, queries)
and stub shapes.

### 4. Samples

Two cases, and which one you are in decides everything about how you fill in the `.out`.

**The statement gives the output** → copy it verbatim into `tests/samples/sampleN.in` /
`.out`. Verbatim matters: a "corrected" sample hides a misreading of the statement.

**It doesn't** — no examples at all, or an answer that lives in a diagram or in prose —
→ work one out by hand from the statement and note in the README that the sample is
yours rather than the statement's. That is good enough.

What it must never be is a reference's output. `selfcheck` is the only place either
reference meets ground truth the harness did not generate itself, so a sample filled in
by running the reference collapses that into the reference agreeing with itself: it
passes every time, prints `consistent`, and proves nothing — while the whole workspace
may be solving a subtly different problem than the one on the page. Working the answer
out by hand keeps the check real, because reading a statement and writing an algorithm
are two different acts and the point is to find out when they disagree.

### 5. `.oa/ref/reference.py` — the brute force

`solve(data: str) -> str` takes the whole input file, returns the whole output.
Rewrite the scaffold's body and delete its `TEMPLATE = True` line.
Write the dumbest correct thing: exponential enumeration, O(n³) DP, simulation.
Its only job is to disagree with the user when the user is wrong, so clarity beats
speed. `oa.py answers` gives it `ref_time_limit_ms` per test (default 120 s) and
caches every answer, so slow is genuinely fine.

Whether it is *fast enough* is arithmetic, not a rule of thumb. Count the iterations
your brute force performs at the largest generated case and divide by the CPython rate
in step 2: the 120 s default buys on the order of 10⁹ of them. The same O(n²) bound
lands a factor of four apart on n depending only on what sits in the inner loop, which
is why there is no single number to quote here — do the multiplication for the brute
force you actually wrote, then check it against the clock in step 7.

Tune that budget down, not just up. It is spent in full on every test the brute force
cannot finish *before* `reference_fast` is tried, so five hopeless tests at the default
is ten minutes of dead waiting during step 7. Time the brute force on your largest few
cases and set `ref_time_limit_ms` a little past what it can actually manage.

If it still can't answer the largest generated case, add `.oa/ref/reference_fast.py`
with the intended algorithm — the harness cross-checks the two wherever the brute force
finishes, and only trusts the fast one past that point. Never write only a fast
reference: with nothing to cross-check against, a wrong one silently sets wrong answers
on exactly the tests that matter most. Mechanics in `references/authoring.md`.

### 6. `.oa/gen.py` — the test suite

**Transcribe the constraint line first**, before writing a single case. It becomes
`LIMITS`, and `measure()` reads those same quantities back off a generated input.
Delete the scaffold's `TEMPLATE = True` line once this file is yours:

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
endpoint must be reached by some test, one test must attain every upper bound at once,
and nothing may fall outside a declared bound. Declare derived limits too — `Σn` over a
multi-test file, `n*m` for grids, `T`, alphabet size — those are the ones that get
skipped. Boundaries are now mechanical; what still takes judgement is everything else.

`cases(rng)` yields input strings, or `(label, data)` pairs so a failure reads
`FAIL t01-nzero`. Aim for **22–30 hidden tests** — the statement's samples are judged
on top of these, so the score the user sees is a little higher than that:

1. **Shape edges** (~6–10, hand-written): all-equal, already-sorted and reverse-sorted, duplicates, disconnected graph, answer-is-zero, answer-is-the-whole-input. No bound declaration can express these.
2. **Small randoms** (~8–10): sizes 1–8 with a tiny value range, so collisions and duplicates happen constantly. These catch the most bugs per byte — with the brute force as an oracle this is effectively random differential testing.
3. **A geometric size ladder** (~4–5): n = 1000, 4000, 16000 … up to the limit. Without a spread of sizes the scaling report at the end of `judge` has nothing to fit and says so.
4. **Max-size stress** (~2–4) **and the joint max corner**: the largest input the constraints allow, plus one test with *every* declared bound maxed at once. That corner is where the 32-bit accumulator overflows.

Use only `rng` — reproducibility is what makes a failing test debuggable.

### 7. Verify before handing over

```bash
cd <slug> && ./oa.sh gen               # boundary coverage must come back clean
./oa.sh selfcheck                      # references must reproduce every sample
./oa.sh answers                        # the slow pass; resumable, cached
./run.sh                               # stub must compile and fail loudly
```

On Windows: `.\oa.cmd gen`, `.\oa.cmd selfcheck`, `.\oa.cmd answers`, `.\run.cmd`.

Iterate freely: `tests/hidden/` records the generator, seed and references it was built
from, so an edit to any of them rebuilds what it invalidates on the next command rather
than being silently overridden by the cache. A new case in `gen.py` costs one reference
run; a change to a reference costs the whole answer pass, which is the honest price of
having changed the oracle.

Go through the wrappers rather than calling `oa.py` directly. They probe for a working
interpreter; a bare `python3` does not, and on Windows it usually resolves to a
Microsoft Store stub that exits without running anything — so the authoring steps would
be the ones that fail on a machine where the buttons are fine. `./run.sh` matters most:
it is the only step that proves the button the user will actually press works here. If
anything exits 127 the probe came up empty; set `OA_PYTHON` and say so in the README.

`selfcheck` failing means the statement was misread. Fix it there — otherwise the user
spends an hour debugging correct code against a wrong oracle, which is the single worst
failure mode of this whole setup. It is also the only place either reference meets
ground truth the harness did not produce itself, so it covers the fast one too. Step 4
is a prerequisite, not an ordering preference: with `tests/samples/` empty there is
nothing to check against, and `selfcheck` fails rather than reporting a green it cannot
justify.

Optionally sanity-check the judge by pointing `entry` at a throwaway correct solution,
confirming 100%, then deleting it. Do this when the I/O format is at all unusual.

### 8. Hand it over

Present the folder and keep it short:

```
./run.sh      # samples                          (Windows: .\run.cmd)
./judge.sh    # submit — scores you on 24 tests   (Windows: .\judge.cmd)
```

The `.\` matters: neither PowerShell nor `cmd /c` will run a batch file from the
current directory without it.

Say what each button gives back, because they differ on purpose. `run.sh` explains
every failing sample in full — the statement already prints those, so there is nothing
to protect. `judge.sh` returns a percentage and a per-test PASS/FAIL list, and no diffs
or expected values at all: on a real OA the expected output of a hidden test *is* the
answer. Two ways through that wall when they want to learn rather than be scored, and
both are worth naming up front:

```
./judge.sh --reveal 1   # explain the first failure: input, expected, yours
./oa.sh case t07-max    # replay any one test in full     (Windows: .\oa.cmd case ...)
```

Mention the time limit, the complexity target if the constraints imply one, and that
both `.oa/` and `tests/hidden/*.out` will spoil them — the first holds the algorithm,
the second the answers. Worth one line: a passing `judge` also prints a scaling
report — measured time and peak memory against input size, with a fitted growth
exponent — so they can see whether they hit the intended complexity rather than just
squeaking under the limit. It declines to print an exponent it cannot stand behind, and
on a fast solution that is the usual outcome; say so, or the blank reads as a fault.
Then get out of the way.

## Modes worth knowing

**Multiple valid answers** (any shortest path, any valid arrangement): set
`"checker": "custom"` and write `.oa/checker.py` with
`check(inp, expected, actual) -> bool | (bool, reason)`. Validate the user's output
against the input and compare its *score* to the reference's — never string-compare.

**Interactive / stateful problems**: out of scope for the harness as-is. Say so and
offer a fixed-transcript approximation instead.

**Windows and macOS** both work, and a workspace built on one behaves identically on
the other — tests are written LF-only and fed to the solution as LF, so a `getline`
never sees a stray `\r`. Three caveats:

- `run.cmd` / `judge.cmd` are the entry points on Windows; the `.sh` ones need Git Bash
  or WSL. Invoke them as `.\run.cmd`.
- **`run.cmd` and `judge.cmd` are CRLF on purpose — never normalize them.** cmd.exe
  seeks through a batch file as it runs, and an LF-only one with a `for` block and a
  `goto` inside jumps to the wrong offset and executes fragments of its own source.
  The LF rule above is about test data and Python; batch files are the exception, and
  `.gitattributes` pins them.
- Peak memory is exact on Windows but sampled on macOS and Linux, so a test finishing
  in a few milliseconds may report low or `n/a`.

**Very large inputs** (10⁶+ numbers): `oa.py gen` writes the inputs quickly; the slow
part is `oa.py answers`, which is a separate command for exactly that reason. It writes
each answer the moment it lands, so an interrupt costs one test rather than the suite,
and a rerun picks up where it stopped. Run it yourself before handing over so the user
never waits.

**Follow-up problems**: scaffold each into its own folder under the same parent so the
user builds up a practice set. Reuse the harness — only `main`, samples, `ref/`, and
`gen.py` change.

## Reference

- `references/authoring.md` — parsing patterns, generator recipes per problem family, checker examples, `problem.json` fields.
- `assets/harness/` — the template files scaffold copies.
- `assets/stubs/` — solution stubs per language.
