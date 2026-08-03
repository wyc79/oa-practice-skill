"""Hidden test generator.

`cases(rng)` yields input strings, one per test. Yield hand-written edge cases
first (they are the ones that actually catch bugs), then randomized ones.
Use only `rng` for randomness so runs are reproducible.
"""


def cases(rng):
    # --- edge cases ---
    yield "1\n0\n"
    yield "1\n-1000000000\n"

    # --- small randoms: dense enough to hit odd shapes ---
    for _ in range(8):
        n = rng.randint(1, 5)
        yield f"{n}\n" + " ".join(str(rng.randint(-10, 10)) for _ in range(n)) + "\n"

    # --- medium ---
    for _ in range(8):
        n = rng.randint(50, 200)
        yield f"{n}\n" + " ".join(str(rng.randint(-10**6, 10**6)) for _ in range(n)) + "\n"

    # --- max-size stress: this is the one that separates O(n^2) from O(n log n) ---
    for _ in range(2):
        n = 200000
        yield f"{n}\n" + " ".join(str(rng.randint(-10**9, 10**9)) for _ in range(n)) + "\n"
