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
| Submit, then have an LLM review it | `./judge.sh --llm` | `.\judge.cmd --llm` |

`run` shows you everything about a failing sample — input, expected, yours — because
the statement prints those anyway. `judge` shows you a score and which tests were red,
and nothing else, because the expected output of a hidden test is the answer. The
`--reveal` and `case` rows are the way through that when you would rather learn than
be scored.

On a clean pass `judge` also prints how your solution scales with input size.

A run that scores 100% files your solution under `solutions/`. `wipe` then hands the
problem back cold — it restores the stub, and refuses if what you have now is not
already archived there.

`--llm` is opt-in and only runs once you have scored 100%: it sends this README, your
solution and the timing summary to an LLM and prints what it says about complexity,
idiom, edge cases and likely follow-up questions, saving it next to the solution. It
needs `OA_REVIEW_API_KEY` in a `.env` here or in the folder above — never commit that
file. Without a key you get one line and your score, unchanged.

Two places will spoil you: `.oa/` holds the generator and the reference solutions, and
`tests/hidden/*.out` holds the expected answers.
