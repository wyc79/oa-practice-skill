"""Hidden reference solution. Correctness matters, speed does not (within reason).
Write it the dumbest way that is obviously right — brute force is ideal, since its
whole job is to disagree with the user's clever solution when the clever one is wrong.

`oa.py answers` gives this a generous per-test budget (ref_time_limit_ms, default
120s), so slow is fine. If it still cannot reach the largest generated case, add
reference_fast.py next to this file with the intended algorithm: it answers only the
tests this one times out on, and must agree with this one everywhere this one finishes.
"""


def solve(data: str) -> str:
    it = iter(data.split())
    n = int(next(it))
    xs = [int(next(it)) for _ in range(n)]
    return str(sum(xs))
