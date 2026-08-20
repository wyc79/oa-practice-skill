# Authoring reference

Contents: [problem.json](#problemjson) · [main file patterns](#main-file-patterns) ·
[constraint boundaries](#constraint-boundaries) · [reference solutions](#reference-solutions) ·
[generator recipes](#generator-recipes) · [checkers](#checkers) ·
[harness commands](#harness-commands)

## problem.json

| field | meaning |
|---|---|
| `name` | slug, shown in judge output |
| `language` | `cpp` or `python` — anything else goes through `run_cmd` |
| `entry` | source file the user edits |
| `time_limit_ms` | per test; TLE verdict above this |
| `checker` | `token` (default, whitespace-insensitive) \| `exact` \| `float` \| `custom` |
| `float_eps` | relative tolerance for `float` |
| `seed` | generator seed; changing it reshuffles the hidden tests |
| `ref_time_limit_ms` | per-test budget for the reference during `answers` (default 120000) |
| `build_cmd` / `run_cmd` | escape hatch for any other language |

C++ and Python are the two the harness compiles and launches itself. Anything else is
a pair of commands — no stub is shipped, so write the main file by hand:

```json
{ "entry": "Main.java",
  "build_cmd": "javac -d .oa/build Main.java",
  "run_cmd": ["java", "-cp", ".oa/build", "Main"] }

{ "entry": "main.rs",
  "build_cmd": "rustc -O -o .oa/build/main main.rs",
  "run_cmd": [".oa/build/main"] }
```

## Main file patterns

Parse into clean types and hand them to `solve()`. The user should never touch `cin`.

**Multi-test (`T` on the first line)** — the loop lives in `main`, not in `solve`:

```cpp
int T; cin >> T;
while (T--) {
    int n; cin >> n;
    vector<long long> a(n);
    for (auto& x : a) cin >> x;
    cout << solve(a) << "\n";
}
```

**Graph (n nodes, m edges, 1-indexed)** — convert to 0-indexed adjacency here, so the
user isn't debugging off-by-ones in the plumbing:

```cpp
int n, m; cin >> n >> m;
vector<vector<int>> g(n);
for (int i = 0; i < m; i++) {
    int u, v; cin >> u >> v;
    g[--u].push_back(--v);
    g[v].push_back(u);
}
cout << solve(n, g) << "\n";
```

**Grid**: read `vector<string>` rows directly. **Queries**: parse into a
`vector<array<int,3>>` and pass the whole batch, so the user can answer offline if they
want. **Vector output**: print space-separated on one line unless the statement says
otherwise, and set `"checker": "token"`.

**Function-signature style**: keep the exact signature the OA gave, and have `main`
adapt stdin to it:

```cpp
class Solution {
public:
    int maxProfit(vector<int>& prices) {
        // TODO
        return 0;
    }
};
```

## Constraint boundaries

SKILL.md step 6 has the shape of `LIMITS` and `measure`. What it does not have:

Each value is a scalar or a list; a list contributes its own min and max. A key may be
absent when it does not apply — an `n = 0` input has no `a_i`, and that is fine.
`measure` mirrors the parsing in `reference.py`, so write it right after that one.

`oa.py gen` then hard-fails on three things: an endpoint no test reaches, a value
outside its declared bound, and no single test attaining every upper bound at once.
It warns, but does not fail, when that joint corner is not *saturated* — `n = 10^6`
with one `a_i = 10^9` is a much weaker overflow probe than all of them at `10^9`, but
only you know whether saturating is legal here.

Declaring *neither* `LIMITS` nor `measure` skips the whole check with a warning, which
is what keeps folders scaffolded before it existed working. Declaring one without the
other is a fourth hard failure: it is an unfinished edit rather than a choice, and
"boundaries unchecked" over a file that visibly declares boundaries is the one message
guaranteed to be read as fine.

Declare derived quantities, not just the ones with a letter in the statement. These
are the limits that get skipped:

| constraint | key |
|---|---|
| `Σn <= 2*10^5` across a multi-test file | `sum_n` |
| `n + m <= 10^5` | `n_plus_m` |
| grid `n*m <= 10^6` | `n_times_m` |
| `1 <= T <= 100` | `T` |
| total string length, edge count, weight range, alphabet size | one key each |

**Coupled bounds.** A budget shared between two variables — `n + m <= 10^5`,
`n*m <= 10^6` — means no input can max both, so the joint corner is unsatisfiable as
stated. Mark those keys `(lo, hi, "no-corner")` to drop them from the corner
requirement, and declare the derived key so the real limit is still enforced
somewhere. Endpoint coverage still applies to each, the coverage table prints which
keys were exempted, and the saturation hint skips them too — nagging that an
unsaturable key is unsaturated is the complaint the exemption already answered.

**Attainable but not saturable.** The weaker version of the same thing: the corner
*can* reach a key's maximum, it just cannot hold every element there. `k <= 10^4` lists
of `len <= 500` under `Σlen <= 10^4` permits exactly one list of 500 in a 10^4-list
input and nothing beyond it. `no-corner` is the wrong tool — it would also drop the
requirement that some test attain 500, which is a check worth keeping. Mark the key
`(lo, hi, "no-saturate")` instead: it stays required in the joint corner, and only the
saturation hint — which has no legal answer here, and no edit that would silence it —
is dropped. The coverage table prints `(saturation exempt)`, so the waiver stays as
visible as the corner one.

Where several tests attain every upper bound, the corner check reports the most
saturated one, not the first.

The catch: under a shared budget the *effective* max of each variable is lower than
the number in the statement. With `1 <= n, m` and `n + m <= 100`, the statement may
say `n <= 100`, but `m >= 1` puts n's real ceiling at 99. Declare the effective bound
— and if you copy the printed one by mistake, coverage fails with `MISSING max` on a
bound nothing can reach, which is the check doing its job:

```
  n                 1 .. 100  MISSING max  reached 1 .. 99
  m                 1 .. 100  MISSING max  reached 1 .. 99
  n_plus_m          2 .. 100  min t04-min  max t01-nmax  OK
```

One more thing the corner check cannot know: a shared budget has several distinct
worst shapes — `n=99, m=1`, `n=1, m=99`, `n=m=50` — that exercise different code
paths, and only one is needed to satisfy the corner. Yield all of them.

Per family, `measure` is a few lines:

```python
# graph: n, m, and the largest weight
def measure(data):
    t = data.split()
    n, m = int(t[0]), int(t[1])
    w = [int(t[4 + 3 * i]) for i in range(m)]
    return {"n": n, "m": m, "w": w}

# multi-test: T and the sum of n, which is usually the binding constraint
def measure(data):
    lines = data.split("\n")
    T = int(lines[0])
    ns = [int(lines[1 + 2 * i]) for i in range(T)]
    return {"T": T, "n": ns, "sum_n": sum(ns)}

# grid: both dimensions and their product
def measure(data):
    r, c = (int(x) for x in data.split("\n")[0].split())
    return {"r": r, "c": c, "area": r * c}
```

## Reference solutions

`solve(data: str) -> str`, whole input in, whole output out. Correct and obvious beats
fast.

The scaffold ships this file and `.oa/gen.py` as a worked example for a different
problem, each with a `TEMPLATE = True` line. `gen`, `answers` and `selfcheck` all
refuse to run while that line is present — an example generator paired with an example
reference produces a suite that passes every check and grades the wrong problem, so it
fails closed rather than quietly.

Useful shapes:

- **Enumerate everything**: `itertools.permutations` / `combinations` / bitmask over subsets — fine when the generator keeps n ≤ 10.
- **Simulate literally**: follow the statement operation by operation.
- **Cubic DP** where the intended solution is a clever O(n log n).
- **Library shortcut**: `networkx`-free Dijkstra by hand, `functools.lru_cache` recursion, `fractions.Fraction` for exact arithmetic.

Raise `sys.setrecursionlimit(1 << 25)` for deep recursion. Return a string (or anything
`str()`-able); the harness normalizes the trailing newline.

### Two tiers

`oa.py answers` runs `ref/reference.py` in a subprocess under `ref_time_limit_ms` and
caches each answer as it lands, so slow is fine and only *hopeless* is a problem.
Beyond what that budget reaches, add `ref/reference_fast.py` with the intended
algorithm:

- The brute force answers every test it can finish, and stays the oracle.
- The fast one answers only the tests the brute force times out on.
- On every test the brute force *did* finish, both run and must agree. A disagreement
  fails the pass and names the input — one of the two is wrong, and which one is not
  yet known.
- `oa.py selfcheck` checks both against the statement's samples. That is the only
  ground truth the harness did not generate itself, so neither reference skips it —
  and it is why a sample's expected output is never produced by running a reference,
  however convenient that is when the statement did not supply one. SKILL.md step 4
  has what to do instead.

Never ship a fast reference alone — see SKILL.md step 5 for why.

If even a fast reference is impractical, lower the bound in `LIMITS` and say so in the
README. There is no waiver flag on purpose: a shrunken bound is a visible edit, while a
config toggle reads as covered when it is not.

## Generator recipes

Keep labels short — the user types them into `oa.py case`. Order the suite: boundary →
shape → small random → size ladder → max stress and the joint corner.

**Array**

```python
for _ in range(8):
    n = rng.randint(1, 6)
    yield f"{n}\n" + " ".join(str(rng.randint(-5, 5)) for _ in range(n)) + "\n"
```

Small value ranges are the point — duplicates and ties are where the bugs live.

**Permutation**: `p = list(range(1, n+1)); rng.shuffle(p)`

**String**: draw from `"ab"` for tiny alphabets (forces repeats), `"abc…z"` for realistic ones.

**Tree (n−1 edges, connected)**

```python
edges = [(rng.randint(1, i - 1), i) for i in range(2, n + 1)]
```

Mix shapes deliberately: path (`i-1, i`), star (`1, i`), random. Path and star are the
ones that blow recursion depth and quadratic diameter code.

**Connected graph**: tree first, then add `m - (n-1)` random extra edges, skipping
self-loops and (if simple) duplicates.

**DAG**: random permutation as topological order, edges only forward.

**Grid**: `rng.choice("..#")` with a density knob; guarantee start/end are free if the
statement requires it.

**Weighted**: keep weights small in random tests (collisions), then one max-weight case
to catch overflow.

**Size ladder**: a geometric run of sizes, up to the limit.

```python
n = 1000
while n < MAXN:
    yield f"n{n}", fmt([rng.randint(-10**6, 10**6) for _ in range(n)])
    n *= 4
```

**Max stress**: exactly the constraint limit. Build with `"".join`/`" ".join`, not
`+=` in a loop. If Python generation is slow, remember it only runs once —
`tests/hidden/` is cached until `oa.py gen` or `--force`.

You no longer need to assert the constraints by hand: any value outside a declared
`LIMITS` bound fails `oa.py gen` with the test name and the offending value. A
generated input that violates the statement produces a "failure" the user cannot fix,
which destroys trust in the score — so this one is enforced rather than remembered.

## Checkers

`.oa/checker.py`:

```python
def check(inp: str, expected: str, actual: str):
    """Return bool, or (bool, reason)."""
    exp_val = int(expected.split()[0])
    toks = actual.split()
    if not toks:
        return False, "empty output"
    ...
    return True
```

Use it when:

- **Any optimal answer accepted** — verify the user's answer is valid *and* scores equal to the reference's.
- **Order-independent output** — compare `sorted()` or multisets.
- **Constructive problems** ("output any string with property P") — verify P, ignore `expected` entirely.
- **Yes/No + witness** — check the witness only when the answer is Yes.

Return a reason string; it shows up next to the FAIL line and saves the user a debugging round.

`selfcheck` runs one control over this file, because a hand-written checker is the one
comparison the harness cannot check for you: it feeds the checker one test's input
paired with a *different* test's expected output and requires at least one such pair to
be rejected. A checker raising on nonsense counts as rejecting it. Failing the control
means the checker is not comparing anything — and since the sample check, the coverage
table and the plumbing check all consult that same checker, nothing else would have
noticed. It is skipped, with a note, when every scored test has the same answer and
there is nothing to cross.

## HINTS.md

The README is the problem; `HINTS.md` is everything you know about it. Nothing that
would shorten the user's search belongs on the README side of that line — not the
algorithm family, not the intended big-O, not "this is the classic two-pointer one".
Write both at authoring time; the user opens the second one when they choose to.

Tone: you are teaching after the attempt, not briefing before it. Say what the topic
is and how it is normally implemented, then be concrete about the traps — *this* is
where the value is, because the traps are what separate knowing the algorithm from
getting it accepted. **List the ones `gen.py` actually generates a test for.** A trap
with a test behind it is one the user will meet and can go and reproduce with
`oa.sh case`; a trap you remembered from somewhere else is trivia, and padding the
section with it makes the whole file cheaper to skim past.

"Why the constraints force it" is a transcript of arithmetic you have already done: the
naive complexity, the operation count it implies at the largest declared bound, why
that misses the time limit, and what the intended complexity brings it down to. It is
the answer to the question the user will actually ask, which is not "what is the
algorithm" but "how was I supposed to know that from the constraint line".

The related problems come from your own knowledge — three to six, closest first, each
one a number, a title, and a one-line hook naming what it shares with this problem
rather than restating it. Mark premium ones so nobody hits a paywall mid-practice. If
this problem is a reskin of a LeetCode original, put that one first and label it, since
it is the one place the user can compare their solution against everyone else's.

Bilingual links when the statement is in Chinese, or when the user is working across
both languages: give both titles (`210. Course Schedule II / 课程表 II`) and both links.
The slug is identical on `leetcode.com` and `leetcode.cn`, so the second link is the
first with the host swapped. English-only otherwise — an unasked-for second link on
every row is noise.

## Harness commands

```
./run.sh                  # samples only, explains every failure
./judge.sh                # samples + hidden, prints Score: k/n (p%) — no diffs
./judge.sh --force        # discard cached tests and answers first
./judge.sh --reveal 1     # ...and explain the first failure after all
./oa.sh case t07-max      # rerun one test with full detail
./oa.sh gen               # refresh tests/hidden/*.in + boundary coverage (fast)
./oa.sh gen --force       # ...from scratch, discarding every cached answer
./oa.sh answers           # compute the expected outputs (slow, resumable)
./oa.sh selfcheck         # references vs samples + coverage + staleness + checker
./oa.sh selfcheck --entry _check.cpp  # ...and the plumbing — the last gate before hand-over
./oa.sh wipe              # entry file back to the stub, to solve the problem cold again
./oa.sh wipe --force      # ...discarding an attempt that never reached solutions/
./judge.sh --llm          # ...and, on a 100% score only, an LLM post-mortem
./oa.sh review            # that post-mortem on the latest archived solution, no re-judge
```

Windows: `.\run.cmd`, `.\judge.cmd`, `.\oa.cmd <cmd>`. All three wrappers forward to
`oa.py`, which you can also call directly if you already know your interpreter's name.

A `judge` run that scores 100% copies the entry file to
`solutions/<YYYYMMDD-HHMMSS>/solution.<ext>`, with that run's `results.md` beside it —
a folder per attempt, holding the code and what is known about it — unless an
equivalent solution is already archived — the comparison strips every whitespace character first, so a reformat of a
solution already on file is recognised as the same one. `wipe` restores the entry file
from `.oa/stub.<ext>`, the untouched copy scaffold left behind, and refuses while the
current file is neither that stub nor something `solutions/` already holds. That is the
whole safety rule: nothing deletes an attempt the archive has not seen, and `--force`
is the only way past it.

`tests/hidden/` records what built it in `_stamp.json` — a hash of `.oa/gen.py`, the
seed, and a hash of each reference — and every command checks it, so an edit takes
effect on the next run rather than being quietly overridden by the cache. Editing
`gen.py` or changing the seed rebuilds the inputs but keeps the answer to every test
whose input came out byte-identical: appending a case costs one reference run, not the
suite. `--force` is the only thing that discards answers wholesale. Editing a reference
discards all of them, because there is no knowing which it would have changed, and
answers the current oracle disagrees with grade the user against a solution nobody is
running. `selfcheck` refuses to pass on a stale cache.

`selfcheck --entry <file>` is the second-implementation gate: it scores `<file>` — a
known-correct stand-in for the main file — through the real tests and checker and
demands 100%, and separately feeds every generated input to the real entry and demands
it not die. Without `--entry` it reports the output shape as unchecked and fails, once
there are answers to check against. SKILL.md step 7 has why it is not optional.

It is the only thing in the workspace that can contradict `reference.py`, so it is
carrying the answer key as well as the plumbing. Which failure it reports says which:
every scored test failing is a format mismatch and the fix is in the entry file; a
subset failing means the stand-in and the reference agree on the shape of an answer
and disagree on its value, and the samples cannot arbitrate because both reproduce
them. The harness prints them as two different messages for that reason.

The stand-in shares the entry file's extension, because `--entry` goes through the same
`build()` and so to the same toolchain: `_check.cpp` for the default C++ workspace,
`_check.py` for a Python one. Its two halves come from different places, and mixing
that up costs the gate its point:

- *Plumbing*: a **copy** of the main file. Written from scratch it re-implements the parsing, which is the half of the plumbing the gate was supposed to be checking.
- *Algorithm*: **re-derived from the statement**, never ported from `reference.py`. A port shares the reference's misreadings, so it agrees on every test and scores 100% over an answer key that is wrong.

A workspace driven by `build_cmd` / `run_cmd` cannot use `--entry` at all: those name
their own files, so the stand-in would be ignored and the stub scored in its place.
`selfcheck` says so rather than reporting the stub's score; point `run_cmd` at the
stand-in for the length of the check.

`selfcheck` also prints an **Answer key** block: how many samples back the suite, how
many answers rest on `reference.py` alone, and — from `LIMITS` and `measure` — the
range of each declared quantity the samples reach against the range the tests reach.
It never fails on a gap there, because no statement ships a max-size example and a gate
that failed on one would fail every workspace ever built. It is a disclosure, in the
same spirit as the scaling report declining an exponent it cannot stand behind.

`--reveal N` explains the first N failures and no more, where "explains" covers the
one-line reason as well as the input/expected/actual block — `token 0: got '0', want
'200000000000000'` is the answer, so at `--reveal 0` a failing test prints its name and
timing and nothing else.

The default differs by command, because what a failure may safely say about itself
differs by command:

| | default | why |
|---|---|---|
| `run` | every sample | the statement already prints these; hiding them helps nobody |
| `judge` | none | the expected output of a hidden test *is* the answer |
| `case <name>` | 1 | naming a test is an explicit request to see it |

That makes `judge` a real submit button rather than a generous one, and leaves two
deliberate ways back out for a user who wants to learn rather than be scored:
`judge --reveal 1`, and `case <name>` on whichever test the score said was red. A
failing `judge` prints that pair as a one-line reminder — the escape hatch is no use
if only the person who built the folder knows it is there.

Verdicts: `PASS` · `FAIL` (wrong answer, with the first differing token) · `TLE` ·
`RE` (nonzero exit / crash, with stderr) · `SKIP` (a `tests/samples/*.in` with no
matching `.out` — unscorable, so it leaves the denominator). Every command that scores
something — `run`, `judge` and `case` alike — exits 0 only when everything passes *and*
something was scored, so `judge.sh` drops straight into a git hook or CI step.

The `slowest` figure in the summary line counts only runs that finished inside the
limit. A killed process reports three times the limit by construction and a crash on
Windows spends seconds in the error reporter, so folding either in would print a
number that appears in none of the rows above it; tests over the limit are counted
separately instead.

Each wrapper probes for a working Python 3 rather than assuming `python3` resolves to
one — it does not on Windows, where `python3.exe` is usually the Microsoft Store stub
and `py` may not exist at all. `oa.sh`/`oa.cmd` exist so the authoring commands get the
same probe the two buttons get. Set `OA_PYTHON` to override.

## LLM review

`judge --llm` and `review` are the only two commands that touch the network, and both
are opt-in. `--llm` runs the post-mortem after a 100% score and prints one line instead
on any lower one; `review` does the same for the newest file in `solutions/` without
re-running anything. What goes out is the folder's `README.md`, the solution itself, and
judge's timing and scaling summary; what comes back is printed and written to
`review.md` inside that solution's folder. A line naming the host is printed before the
request, because sending someone's code somewhere should never be silent.

| Variable | |
|---|---|
| `OA_REVIEW_API_KEY` | required; nothing is sent without it |
| `OA_REVIEW_MODEL` | optional on the Anthropic API, required with a custom base URL |
| `OA_REVIEW_BASE_URL` | optional; set it to speak OpenAI-compatible chat completions |

Each is looked up in `<problem>/.env`, then `<parent>/.env`, then the real environment,
nearest first — so one key at the root of a problem bank serves every folder under it,
and a single problem can still point somewhere else. **Neither `.env` is ever
committed**; a problem-bank repo must gitignore it.

Every failure in this layer is one line of output and nothing else. A missing key, an
unreadable `.env`, a bad endpoint, a non-2xx reply, a timeout, a refusal: `judge --llm`
still prints its score and exits with the status the suite earned, and `review` exits
zero. Scoring never depends on any of it — the review is an opinion printed after the
grading is over, and it is not allowed to become a way for a submit to fail.

## Scaling report

A `judge` run that passes everything ends with measured time and peak memory against
input size, and a fitted growth exponent:

```
Scaling — largest tests, by input size
    19.5 KB       95 ms     12.6 MB   t06-n2700
    87.0 KB      545 ms     13.3 MB   t07-max
  time   ~ n^1.69  — above linear  (34 ms startup subtracted, 5 points, R²=0.99)
  memory ~ n^0.95  (12.3 MB runtime baseline subtracted, R²=0.97)
```

Peak memory is exact on Windows and sampled on Linux and macOS; anywhere else it is
`n/a` rather than a number that would quietly mean something else. Both curves have a
large constant term — process startup, and the runtime's baseline heap — subtracted
before fitting, or a perfectly linear solution reads as sub-linear. Points carrying no
signal are then dropped by two floors: absolute (the clock's own resolution, an
allocator rounding) and relative (a sixteenth of the largest signal). The relative one
is what keeps run-to-run jitter out — CPython's startup wanders by ten-odd
milliseconds, so without it a suite of fast tests enters the fit as a band of noise and
outnumbers the points that did real work.

What survives is fitted only if the fit means something, and `R²` — the share of the
variance the exponent explains — is the check that matters. Tests of the same size but
different *shape* cost visibly different time, so a line drawn through them can report
a merge sort as `n^0.60`. A fit is declined when too few of the largest tests clear the
floor, when the ones that do span too little input size, when nothing rises far enough
to measure, or when `R²` is under 0.9.

Each declines with its own sentence, because they call for different things. "Nothing
rose far enough above the floor" on a solution that passed comfortably is the expected
outcome for anything fast. "Span too little input size" is a suite problem: widen the
ladder. A low `R²` on a suite that already has a ladder is neither, and widening will
not help — the max-stress and joint-corner tests are typically the *largest inputs by
bytes* and being degenerate is their entire job, so they sit at the top of the ordering
the fit works from while costing what their shape costs rather than what their size
implies. To get an exponent out of such a problem, make the ladder itself reach the
maximum size.

Expect the estimate to be sharper for C++ (millisecond startup) than for Python, and
expect exponents fitted against input *bytes* to understate: a true O(n²) solution
reads around `n^1.5`, which is why 1.35 is the threshold for flagging "above linear".

Reference timings recorded during `answers` are shown alongside for scale. They are
Python, so treat the ratio as a sanity check rather than a benchmark.
