---
name: oa-practice
description: Turn any coding-assessment problem into a local, runnable OA workspace — parsed I/O main file, sample tests with a one-click runner, and a hidden judge that scores the user's solution on ~20+ generated tests as a pass percentage. Use this whenever the user pastes a problem statement with sample input/output and wants to solve it themselves, or mentions OA, online assessment, 笔试, 机考, take-home coding test, HackerRank/Codility/牛客/Codeforces-style problems, or says a problem "isn't on LeetCode" so there's nothing to run their code against. Trigger even for casual asks like "set this one up for me", "make me a test harness for this", "I want to practice this problem", or when they drop a screenshot/paste of a problem with constraints and examples. The user writes the algorithm; this skill builds everything around it and never fills in the solution unless asked.
---

# OA Practice Harness

The user wants the OA experience for a problem that has no online judge: write code,
hit run on the samples, hit submit, get a score. This skill builds that workspace.

The one rule that makes the whole thing worth doing: **never write the solution.**
The `solve()` body stays a `// TODO`. Everything else — parsing, printing, samples,
hidden tests, scoring — is yours to build. If the user later asks for hints or the
answer, that is a separate request and fine to fulfill.

## What gets produced

```
<slug>/
├── main.cpp            # I/O parsed and printed; solve() is a stub for the user
├── problem.json        # language, time limit, checker mode
├── README.md           # restated statement, constraints, complexity target
├── run.sh              # ./run.sh   → samples only, with diffs      ("Run Code")
├── judge.sh            # ./judge.sh → all tests, prints k/n (p%)     ("Submit")
├── oa.py               # harness engine (run / judge / gen / answers / case / selfcheck)
├── tests/samples/      # sample1.in, sample1.out, sample2.in, ...
└── .oa/
    ├── gen.py          # declared constraint bounds + edge cases + randoms + stress
    ├── checker.py      # only when multiple outputs are valid
    └── ref/            # SPOILERS — one level down so they are not sitting in the way
        ├── reference.py       # brute force: the oracle
        └── reference_fast.py  # intended algorithm; only when brute can't reach the limits
```

The hidden tests are not shipped as files — `.oa/gen.py` produces the inputs and
`.oa/ref/reference.py` produces the expected outputs, deterministically from a seed.
That is what makes a 20+ test suite cheap to build and impossible to hardcode against.

## Workflow

### 1. Read the statement and pin down I/O

Everything downstream depends on the exact input format, so resolve it before writing
anything. Most of it is inferable from the samples — match the sample input text
token by token against the prose. Ask the user only about what genuinely isn't there:

- **No sample I/O at all** → ask for at least one example, or offer to invent samples and flag that they're unverified.
- **Function-signature style** (LeetCode-ish: "implement `int maxProfit(vector<int>& prices)`") → keep the same shape: `main()` reads stdin and calls their function, so the file still runs standalone but the signature is what they'd paste into the real OA.
- **Multiple test cases per input file** (`T` on the first line) → common in 笔试; check the samples for it.
- **Ambiguous output formatting** (float precision, trailing spaces, ordering) → default to `"checker": "token"` (whitespace-insensitive), `"float"` with an eps, or a custom checker. Say which you picked.

### 2. Scaffold

```bash
python3 <skill>/scripts/scaffold.py <slug> --dir <dest> --lang cpp --tl 3000
```

Default to C++17. Time limit: 3000 ms unless the statement says otherwise; tighten to
1000–2000 ms when the point of the problem is that the naive approach is too slow.

### 3. Write `main.cpp` — plumbing only

Parse into clean types, call `solve()`, print. The user should be able to write the
algorithm without ever thinking about `cin`. Keep the stub honest — a `return 0;`
placeholder that fails the samples is correct behaviour, not a bug.

See `references/authoring.md` for parsing patterns (graphs, grids, multi-test, queries)
and stub shapes.

### 4. Samples

Copy them verbatim from the statement into `tests/samples/sampleN.in` / `.out`.
Verbatim matters: a "corrected" sample hides a misreading of the statement.

### 5. `.oa/ref/reference.py` — the brute force

`solve(data: str) -> str` takes the whole input file, returns the whole output.
Write the dumbest correct thing: exponential enumeration, O(n³) DP, simulation.
Its only job is to disagree with the user when the user is wrong, so clarity beats
speed. `oa.py answers` gives it `ref_time_limit_ms` per test (default 120 s) and
caches every answer, so slow is genuinely fine — at that budget an O(n²) Python brute
force reaches n ≈ 3000 and anything cheaper reaches the real limits.

If it still can't answer the largest generated case, add `.oa/ref/reference_fast.py`
with the intended algorithm. It answers only the tests the brute force times out on,
and the harness runs both on every test the brute force *can* finish and fails if they
ever disagree — so the shortcut is validated everywhere it's checkable before it is
trusted anywhere it isn't. Never write only a fast reference: with nothing to
cross-check against, a wrong one silently sets wrong answers on the hardest tests.

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
endpoint must be reached by some test, one test must attain every upper bound at once,
and nothing may fall outside a declared bound. Declare derived limits too — `Σn` over a
multi-test file, `n*m` for grids, `T`, alphabet size — those are the ones that get
skipped. Boundaries are now mechanical; what still takes judgement is everything else.

`cases(rng)` yields input strings, or `(label, data)` pairs so a failure reads
`FAIL t01-nzero`. Aim for **22–30 tests**:

1. **Shape edges** (~6–10, hand-written): all-equal, already-sorted and reverse-sorted, duplicates, disconnected graph, answer-is-zero, answer-is-the-whole-input. No bound declaration can express these.
2. **Small randoms** (~8–10): sizes 1–8 with a tiny value range, so collisions and duplicates happen constantly. These catch the most bugs per byte — with the brute force as an oracle this is effectively random differential testing.
3. **A geometric size ladder** (~4–5): n = 1000, 4000, 16000 … up to the limit. Without a spread of sizes the scaling report at the end of `judge` has nothing to fit and says so.
4. **Max-size stress** (~2–4) **and the joint max corner**: the largest input the constraints allow, plus one test with *every* declared bound maxed at once. That corner is where the 32-bit accumulator overflows.

Use only `rng` — reproducibility is what makes a failing test debuggable.

### 7. Verify before handing over

```bash
cd <slug> && python3 oa.py gen         # boundary coverage must come back clean
python3 oa.py selfcheck                # references must reproduce every sample
python3 oa.py answers                  # the slow pass; resumable, cached
./run.sh                               # stub must compile and fail loudly
```

`selfcheck` failing means the statement was misread. Fix it there — otherwise the user
spends an hour debugging correct code against a wrong oracle, which is the single worst
failure mode of this whole setup. It is also the only place either reference meets
ground truth the harness did not produce itself, so it covers the fast one too.

Optionally sanity-check the judge by pointing `entry` at a throwaway correct solution,
confirming 100%, then deleting it. Do this when the I/O format is at all unusual.

### 8. Hand it over

Present the folder and keep it short:

```
./run.sh      # samples
./judge.sh    # submit — scores you on 24 tests
```

Mention the time limit, the complexity target if the constraints imply one, and that
`.oa/` contains spoilers. Worth one line: a passing `judge` also prints a scaling
report — measured time and peak memory against input size, with a fitted growth
exponent — so they can see whether they hit the intended complexity rather than just
squeaking under the limit. Then get out of the way.

## Modes worth knowing

**Multiple valid answers** (any shortest path, any valid arrangement): set
`"checker": "custom"` and write `.oa/checker.py` with
`check(inp, expected, actual) -> bool | (bool, reason)`. Validate the user's output
against the input and compare its *score* to the reference's — never string-compare.

**Interactive / stateful problems**: out of scope for the harness as-is. Say so and
offer a fixed-transcript approximation instead.

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
