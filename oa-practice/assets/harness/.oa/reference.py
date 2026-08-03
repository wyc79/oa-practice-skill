"""Hidden reference solution. Correctness matters, speed does not (within reason).
Write it the dumbest way that is obviously right — brute force is ideal, since its
whole job is to disagree with the user's clever solution when the clever one is wrong.
"""


def solve(data: str) -> str:
    it = iter(data.split())
    n = int(next(it))
    xs = [int(next(it)) for _ in range(n)]
    return str(sum(xs))
