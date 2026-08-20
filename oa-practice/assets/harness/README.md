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
| Submit, but explain the first failure | `./judge.sh --reveal 1` | `.\judge.cmd --reveal 1` |
| Replay one test in full | `./oa.sh case t07-max` | `.\oa.cmd case t07-max` |
| Start over from the stub | `./oa.sh wipe` | `.\oa.cmd wipe` |

`run` shows you everything about a failing sample — input, expected, yours — because
the statement prints those anyway. `judge` shows you a score and which tests were red,
and nothing else, because the expected output of a hidden test is the answer. The
`--reveal` and `case` rows are the way through that when you would rather learn than
be scored.

On a clean pass `judge` also prints how your solution scales with input size.

A run that scores 100% files your solution under `solutions/`. `wipe` then hands the
problem back cold — it restores the stub, and refuses if what you have now is not
already archived there.

Two places will spoil you: `.oa/` holds the generator and the reference solutions, and
`tests/hidden/*.out` holds the expected answers.
