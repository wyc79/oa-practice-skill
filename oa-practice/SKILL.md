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
├── oa.py               # harness engine (run / judge / gen / case / selfcheck)
├── tests/samples/      # sample1.in, sample1.out, sample2.in, ...
└── .oa/
    ├── reference.py    # brute-force correct solution — SPOILERS
    ├── gen.py          # test generator: edge cases + randoms + max-size stress
    └── checker.py      # only when multiple outputs are valid
```

The hidden tests are not shipped as files — `.oa/gen.py` produces the inputs and
`.oa/reference.py` produces the expected outputs, deterministically from a seed.
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

### 5. `.oa/reference.py` — the brute force

`solve(data: str) -> str` takes the whole input file, returns the whole output.
Write the dumbest correct thing: exponential enumeration, O(n³) DP, simulation.
Its only job is to disagree with the user when the user is wrong, so clarity beats
speed — but it must finish on the largest generated case in a few seconds, which is
what caps the size of the stress tests in step 6.

If brute force isn't feasible even at small sizes, say so and fall back to a
correct-but-slower-than-intended approach, or a validating checker.

### 6. `.oa/gen.py` — the test suite

`cases(rng)` yields input strings. Aim for **22–30 tests** in this order:

1. **Edge cases first** (~6–10, hand-written): minimum size, all-equal, all-negative, empty-ish, single element, max value, duplicates, already-sorted and reverse-sorted, disconnected graph, answer-is-zero, answer-is-the-whole-input.
2. **Small randoms** (~8–10): sizes 1–8 with a tiny value range, so collisions and duplicates happen constantly. These catch the most bugs per byte — with the brute force as an oracle this is effectively random differential testing.
3. **Medium randoms** (~4–6): a few hundred elements, realistic values.
4. **Max-size stress** (~2–4): the largest input the constraints allow. This is the test that fails the O(n²) solution and the 32-bit accumulator, so it must be at the real limit. Cap it only if the reference can't keep up — and if you cap it, put a note in the README so the user knows the harness won't catch their TLE.

Every generated input must satisfy the stated constraints (valid tree, valid
permutation, sum bounds, no self-loops). Use only `rng` — reproducibility is what makes
a failing test debuggable.

### 7. Verify before handing over

```bash
cd <slug> && python3 oa.py selfcheck   # reference must reproduce every sample
python3 oa.py gen                      # generator must run clean at full size
./run.sh                               # stub must compile and fail loudly
```

`selfcheck` failing means the statement was misread. Fix it there — otherwise the user
spends an hour debugging correct code against a wrong oracle, which is the single worst
failure mode of this whole setup.

Optionally sanity-check the judge by pointing `entry` at a throwaway correct solution,
confirming 100%, then deleting it. Do this when the I/O format is at all unusual.

### 8. Hand it over

Present the folder and keep it short:

```
./run.sh      # samples
./judge.sh    # submit — scores you on 24 tests
```

Mention the time limit, the complexity target if the constraints imply one, and that
`.oa/` contains spoilers. Then get out of the way.

## Modes worth knowing

**Multiple valid answers** (any shortest path, any valid arrangement): set
`"checker": "custom"` and write `.oa/checker.py` with
`check(inp, expected, actual) -> bool | (bool, reason)`. Validate the user's output
against the input and compare its *score* to the reference's — never string-compare.

**Interactive / stateful problems**: out of scope for the harness as-is. Say so and
offer a fixed-transcript approximation instead.

**Very large inputs** (10⁶+ numbers): generating these in Python is slow but fine once,
since `tests/hidden/` is cached after the first `judge`. Warn the user the first run
takes a minute.

**Follow-up problems**: scaffold each into its own folder under the same parent so the
user builds up a practice set. Reuse the harness — only `main`, samples, `reference.py`,
and `gen.py` change.

## Reference

- `references/authoring.md` — parsing patterns, generator recipes per problem family, checker examples, `problem.json` fields.
- `assets/harness/` — the template files scaffold copies.
- `assets/stubs/` — solution stubs per language.
