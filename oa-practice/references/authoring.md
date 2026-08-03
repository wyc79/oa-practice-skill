# Authoring reference

Contents: [problem.json](#problemjson) · [main file patterns](#main-file-patterns) ·
[reference solutions](#reference-solutions) · [generator recipes](#generator-recipes) ·
[checkers](#checkers) · [harness commands](#harness-commands)

## problem.json

| field | meaning |
|---|---|
| `name` | slug, shown in judge output |
| `language` | `cpp` \| `python` \| `java`, or omit and use `run_cmd` |
| `entry` | source file the user edits |
| `time_limit_ms` | per test; TLE verdict above this |
| `checker` | `token` (default, whitespace-insensitive) \| `exact` \| `float` \| `custom` |
| `float_eps` | relative tolerance for `float` |
| `seed` | generator seed; changing it reshuffles the hidden tests |
| `build_cmd` / `run_cmd` | escape hatch for any other language |

Rust example:

```json
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

## Reference solutions

`solve(data: str) -> str`, whole input in, whole output out. Correct and obvious beats
fast. Useful shapes:

- **Enumerate everything**: `itertools.permutations` / `combinations` / bitmask over subsets — fine when the generator keeps n ≤ 10.
- **Simulate literally**: follow the statement operation by operation.
- **Cubic DP** where the intended solution is a clever O(n log n).
- **Library shortcut**: `networkx`-free Dijkstra by hand, `functools.lru_cache` recursion, `fractions.Fraction` for exact arithmetic.

Raise `sys.setrecursionlimit(1 << 25)` for deep recursion. Return a string (or anything
`str()`-able); the harness normalizes the trailing newline.

When you can't brute-force: implement the intended algorithm carefully, note it in the
README so the user knows a shared misreading would go undetected, and lean harder on
edge-case tests.

## Generator recipes

`cases(rng)` yields input strings. Only use `rng`. Order: edge → small random →
medium → max stress.

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

**Max stress**: exactly the constraint limit. Build with `"".join`/`" ".join`, not
`+=` in a loop. If Python generation is slow, remember it only runs once —
`tests/hidden/` is cached until `oa.py gen` or `judge --force`.

Always assert the constraints hold before yielding. A generated input that violates the
statement produces a "failure" the user cannot fix, which destroys trust in the score.

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
python3 oa.py run              # samples only, prints diffs
python3 oa.py judge            # samples + hidden, prints Score: k/n (p%)
python3 oa.py judge --force    # regenerate hidden tests first
python3 oa.py judge --reveal 0 # score only, no diffs — true OA mode
python3 oa.py case t07         # rerun one test with full detail
python3 oa.py gen              # rebuild tests/hidden/
python3 oa.py selfcheck        # reference vs samples — run before handing over
```

Verdicts: `PASS` · `FAIL` (wrong answer, with the first differing token) · `TLE` ·
`RE` (nonzero exit / crash, with stderr). Exit code 0 only when everything passes, so
`judge.sh` drops straight into a git hook or CI step.
