# PROBLEM_SLUG

<!-- Restate the problem in your own words: what goes in, what comes out, what is
     being asked. Enough that you can practise this again in a month without the
     original tab open. -->

## Input

<!-- Line-by-line format, exactly as the samples show it. -->

## Output

<!-- Format, and any tie-breaking or precision rule. If more than one output is
     accepted, say so here as well as in the Samples table. -->

## Samples

<!-- Every file in tests/samples/ appears here, verbatim — the statement's own examples
     first, then any you worked out by hand. Byte-faithful to the files: a tidied copy
     here and a different one on disk is an afternoon of confusion.

     Note records where each came from ("from the statement" / "hand-made: makes n a
     multiple of k") and any caveat, such as several outputs being accepted.

     Single-line I/O goes in the cell, in backticks. Anything longer gets a "see below"
     cell and a fenced block after the table — pipes and <br> inside a cell are
     unreadable in a terminal and unreliable in a diff. So:

     | 1 | `3 1 2` | `6` | from the statement |
     | 2 | see below | see below | hand-made: the empty case |

     ### Sample 2
     ...then an Input fenced block and an Output one, byte for byte from the files. -->

| # | Input | Output | Note |
|---|-------|--------|------|

## Constraints

<!-- Transcribed from the statement, same numbers as LIMITS in .oa/gen.py. -->

## Target

<!-- How comfortably the limit is meant to be met, in words: whether a straightforward
     approach is expected to fit, or whether the generator's sizes were picked to shut
     one out. No algorithm names and no big-O — both hand over the answer, and they are
     in HINTS.md instead, behind a spoiler line, for after your first attempt.

     Note here if a bound was lowered from the statement because no reference could
     reach it. That is the harness admitting a limitation, not a hint. -->

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

`HINTS.md` is the spoiler door, and it is meant to be opened — eventually. It names the
knowledge point, shows why the constraints rule out the naive approach, and lists
related problems to practise next. Try the problem cold first; it will still be there.

Two places will spoil you without meaning to: `.oa/` holds the generator and the
reference solutions, and `tests/hidden/*.out` holds the expected answers.
