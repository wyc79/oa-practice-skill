"""Hidden test generator.

`cases(rng)` yields input strings, one per test — or `(label, data)` pairs, where the
label lands in the test name so a failure reads `FAIL t01-nzero` instead of `FAIL t01`.
Use only `rng` for randomness so runs are reproducible.

`LIMITS` and `measure()` declare the statement's constraints so the harness can check
that the suite actually reaches them. Transcribe the constraint line verbatim into the
comment, fill in LIMITS, and let `oa.py gen` tell you which boundary you missed.
"""

# Constraints, transcribed verbatim from the statement:
#   0 <= n <= 2*10^5
#   -10^9 <= a[i] <= 10^9
LIMITS = {
    "n":   (0, 200000),
    "a_i": (-10**9, 10**9),
}

MAXN = LIMITS["n"][1]
LO, HI = LIMITS["a_i"]


def measure(data):
    """Read the declared quantities back off a generated input.

    Mirrors the parsing in ref/reference.py. Each value may be a scalar or a list; a
    list contributes its own min and max. A key may be missing when it does not apply
    — an n = 0 input has no a_i at all, and that is fine.
    """
    t = data.split()
    n = int(t[0])
    return {"n": n, "a_i": [int(x) for x in t[1:1 + n]]}


def fmt(xs):
    return f"{len(xs)}\n" + " ".join(map(str, xs)) + "\n"


def cases(rng):
    # --- boundary cases: every endpoint in LIMITS has to be reached by something ---
    yield "nzero", "0\n\n"              # n at its minimum: the degenerate empty input
    yield "one", fmt([0])
    yield "vmin", fmt([LO] * 5)         # a_i at its minimum
    yield "vmax", fmt([HI] * 5)         # a_i at its maximum

    # --- shape cases: the edges no bound declaration can express ---
    yield "alleq", fmt([7] * 50)
    yield "sorted", fmt(list(range(1, 51)))
    yield "rsorted", fmt(list(range(50, 0, -1)))

    # --- small randoms: tiny value range, so ties and duplicates happen constantly ---
    for _ in range(8):
        n = rng.randint(1, 5)
        yield fmt([rng.randint(-10, 10) for _ in range(n)])

    # --- medium ---
    for _ in range(4):
        n = rng.randint(50, 200)
        yield fmt([rng.randint(-10**6, 10**6) for _ in range(n)])

    # --- size ladder: geometric, so `judge` can fit a growth curve to the timings.
    # Without a spread of sizes there is nothing to fit and the scaling report says
    # so instead of guessing. ---
    n = 1000
    while n < MAXN:
        yield f"n{n}", fmt([rng.randint(-10**6, 10**6) for _ in range(n)])
        n *= 4

    # --- max-size stress: separates O(n^2) from O(n log n) ---
    for _ in range(2):
        yield fmt([rng.randint(LO, HI) for _ in range(MAXN)])

    # --- joint max corner: every declared upper bound at once ---
    # n at MAXN *and* every a_i at HI, so the sum reaches 2*10^14. If a 32-bit
    # accumulator is going to overflow anywhere, it overflows here.
    yield "max", fmt([HI] * MAXN)
