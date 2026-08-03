# PROBLEM_SLUG

<!-- Restate the problem in your own words: what goes in, what comes out, what is
     being asked. Enough that you can practise this again in a month without the
     original tab open. -->

## Input

<!-- Line-by-line format, exactly as the samples show it. -->

## Output

<!-- Format, and any tie-breaking or precision rule. Note here if any sample in
     tests/samples/ was worked out by hand rather than taken from the statement —
     those are the ones to distrust first if the judge and you disagree. -->

## Constraints

<!-- Transcribed from the statement, same numbers as LIMITS in .oa/gen.py. -->

## Target

<!-- Intended complexity, if the constraints imply one, e.g. O(n log n) for
     n <= 2*10^5 in 3s. Note here if any bound was lowered from the statement
     because no reference could reach it. -->

## Running it

| | macOS / Linux | Windows |
|---|---|---|
| Run Code — samples only | `./run.sh` | `.\run.cmd` |
| Submit — score on every test | `./judge.sh` | `.\judge.cmd` |
| Strict: score only, no hints | `./judge.sh --reveal 0` | `.\judge.cmd --reveal 0` |

`judge` scores you out of the full suite and, on a clean pass, prints how your
solution scales with input size.

Two places will spoil you: `.oa/` holds the generator and the reference solutions, and
`tests/hidden/*.out` holds the expected answers.
