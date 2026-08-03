import sys


# ============================================================
# YOUR CODE GOES HERE. Input parsing and output are handled below.
# ============================================================
def solve(a):
    # TODO
    return 0


def main():
    data = sys.stdin.read().split()
    it = iter(data)
    n = int(next(it))
    a = [int(next(it)) for _ in range(n)]
    print(solve(a))


if __name__ == "__main__":
    main()
