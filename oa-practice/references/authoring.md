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

## Harness commands

```
./run.sh                  # samples only, explains every failure
./judge.sh                # samples + hidden, prints Score: k/n (p%) — no diffs
./judge.sh --force        # discard cached tests and answers first
./judge.sh --reveal 1     # ...and explain the first failure after all
./oa.sh case t07-max      # rerun one test with full detail
./oa.sh gen               # rebuild tests/hidden/*.in + boundary coverage (fast)
./oa.sh answers           # compute the expected outputs (slow, resumable)
./oa.sh selfcheck         # both references vs samples + coverage — before handing over
```

Windows: `.\run.cmd`, `.\judge.cmd`, `.\oa.cmd <cmd>`. All three wrappers forward to
`oa.py`, which you can also call directly if you already know your interpreter's name.

`tests/hidden/` records what built it in `_stamp.json` — a hash of `.oa/gen.py`, the
seed, and a hash of each reference — and every command checks it, so an edit you make
takes effect on the next run instead of being quietly overridden by the cache. Editing
`gen.py` or changing the seed rebuilds the inputs, keeping the answer to every test
whose input came out byte-identical: appending a case costs one reference run, not the
suite. Editing either reference discards every answer, because there is no way to know
which ones it would have changed and keeping answers the current oracle disagrees with
grades the user against a solution nobody is running. `selfcheck` refuses to pass on a
stale cache rather than describing tests the next `judge` will replace.

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

Wrappers: `./run.sh`, `./judge.sh` and `./oa.sh <cmd>` on macOS/Linux; `run.cmd`,
`judge.cmd` and `oa.cmd <cmd>` on Windows. Each probes for a working Python 3 rather
than assuming `python3` resolves to one — it does not on Windows, where `python3.exe`
is usually the Microsoft Store stub and `py` may not exist at all. `oa.sh`/`oa.cmd`
exist so the authoring commands get the same probe the two buttons get; without them
`gen`, `answers` and `selfcheck` are the steps that fail on a machine where `run.sh`
and `judge.sh` are fine. Set `OA_PYTHON` to override.

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

Peak memory is exact on Windows and sampled on Linux and macOS (SKILL.md, "Windows and
macOS", covers what that costs you); anywhere else it is `n/a` rather than a number
that would quietly mean something else. Both curves have a large constant term
— process startup, and the runtime's baseline heap — which is subtracted before
fitting; without that, a perfectly linear solution reads as sub-linear. Points that
carry no signal are then dropped: for time, anything within 3 ms of the floor, which
is the clock's own resolution; for memory, anything under a sixteenth of the largest
reading, since near the baseline the difference is an allocator rounding rather than
anything the input did.

What survives is fitted only if the fit means something, and `R²` — the share of the
variance the exponent explains — is the check that matters. Tests of the same size but
different *shape* cost visibly different time: a sorted 2 MB input and a random one are
not two samples of one curve, and a line drawn through them reports a merge sort as
`n^0.60`. A low `R²` is the report saying exactly that, and it is worth reading as a
fact about the suite: it usually means the largest tests differ in kind, not in size.

So a fit is declined when too few of the largest tests clear the floor, when the ones
that do span too little input size, when nothing rises far enough above the floor to
measure, or when `R²` is under 0.9. Each declines with its own sentence — they call for
different things. "Nothing rose far enough above the floor" on a solution that passed
comfortably is the expected outcome for anything fast, not a failure. "Span too little
input size" is a suite problem: widen the geometric ladder. Expect the time estimate to
be far sharper for C++ (millisecond startup) than for Python (tens of milliseconds of
it), and expect exponents fitted against input *bytes* to understate: a true O(n²)
solution reads around `n^1.5`, which is why 1.35 is the threshold for flagging
"above linear" rather than something nearer 2.

Reference timings recorded during `answers` are shown alongside for scale. They are
Python, so treat the ratio as a sanity check rather than a benchmark.
