# Bootstrapping a problem-bank repo

Read this when the user asks for a problem bank ("mother repo", "my OA repo"), or when
the first scaffold is about to land in a directory that is empty or a bare `git init`.
It is one-time setup. Afterwards, adding a problem is `scaffold.py` plus one row in
`CATALOGUE.md`, and none of these files is touched again.

Five files at the repo root. The harness reads none of them — they are for the human
and for git. **Create what is missing and append to what exists; replace nothing.** A
repo that already has a `.gitignore`, a README or a `.env.example` has them for a
reason.

```
<bank>/
├── README.md         # what the repo is and how to work a problem — static
├── CATALOGUE.md      # one row per problem — the only file that grows
├── .gitattributes    # CRLF for .cmd, LF for everything the harness reads
├── .gitignore        # the review key, and not much else
├── .env.example      # the review key names, so nobody has to guess the spelling
└── <slug>/           # one scaffolded workspace per problem
```

## README.md

Written once. It describes the repo, not any problem in it — if you find yourself
editing it because a problem was added, the row belonged in `CATALOGUE.md`.

```markdown
# <name>

<One line: whose bank this is, and what kind of problems land here.>

Every folder is one problem with its own harness — statement, samples, hidden tests,
and a scorer. [CATALOGUE.md](CATALOGUE.md) is the index.

## Working a problem

    cd <slug>

| | macOS / Linux | Windows |
|---|---|---|
| Run Code — samples only | `./run.sh` | `.\run.cmd` |
| Submit — score on every test | `./judge.sh` | `.\judge.cmd` |
| Submit, and explain the first failure | `./judge.sh --reveal 1` | `.\judge.cmd --reveal 1` |
| Submit, then have an LLM review it | `./judge.sh --llm` | `.\judge.cmd --llm` |
| Replay one test in full | `./oa.sh case t07-max` | `.\oa.cmd case t07-max` |
| Start over from the stub | `./oa.sh wipe` | `.\oa.cmd wipe` |

`run` explains every failing sample, because the statement prints those anyway.
`judge` gives you a percentage and which tests were red and nothing else, because the
expected output of a hidden test is the answer. `--reveal` and `case` are the ways
through that when you would rather learn than be scored.

`--llm` is opt-in and runs only after a 100% score: it sends the problem's README,
your solution and the timing summary to an LLM and prints what it says about
complexity, idiom, edge cases and likely follow-ups. It needs `OA_REVIEW_API_KEY` in a
`.env` at this root — which is gitignored and must stay that way.

## Solve it, then solve it again

A `judge` that scores 100% files your solution in a folder of its own,
`<slug>/solutions/<date>-<time>/solution.<ext>`, skipping it if an equivalent one is
already archived, and drops a `results.md` beside it — what you scored, how fast each
test ran, and how the solution scaled. `review.md` joins them when you run `--llm`. `./oa.sh wipe` then restores the stub and hands the problem back cold. It refuses
while what you have is neither the stub nor something already archived, so nothing you
have not saved can be lost; `wipe --force` overrides that.

Your entry files are committed, so an attempt you left half-finished is waiting for you
on the next machine you clone this to. When you want a problem cold again — a fresh
clone, or a month later — `./oa.sh wipe` is the way to ask for it.

That first 100% also flips this problem's row in [CATALOGUE.md](CATALOGUE.md) from
`unsolved` to `solved <date>`; later passes leave the date alone, because it records
the first time you got there. `Category` and `Notes` in that table are yours to fill —
nothing here writes to them.

## Spoilers, and where they live

- `<slug>/HINTS.md` — the knowledge point, why the constraints force it, and related
  problems. A deliberate door: open it after your first real attempt.
- `<slug>/.oa/` — the generator and the reference solutions.
- `<slug>/tests/hidden/*.out` — the expected answers.

## Adding a problem

Ask Claude with the oa-practice skill; it scaffolds the folder and appends the
CATALOGUE row. By hand:

    python3 <skill>/scripts/scaffold.py <slug> --dir . --lang cpp --tl 3000
```

Fill the placeholders in rather than shipping them. Trim rows the bank will not use.

## CATALOGUE.md

A heading and an empty table. **Nothing else** — no note about how the columns work,
no explanation of what is missing from them. This is the file that grows by a line per
problem forever, and every line that is not a row is one more thing to scroll past.

```markdown
# Catalogue

| # | Problem | Folder | Lang | Source | Added | Status | Category | Notes |
|---|---------|--------|------|--------|-------|--------|----------|-------|
```

`Status` is written `unsolved` when the row is appended, and the first `judge` that
scores 100% in that folder rewrites it to `solved <date>`. Nothing else writes it.

`Category` and `Notes` are created empty and stay empty: they belong to whoever owns
the repo, for whatever classification and remarks they keep, and neither the skill nor
the harness ever fills or reorders them.

There is deliberately **no topic column** — it would name the knowledge point of every
problem in the repo at once, which is the thing each folder's `HINTS.md` exists to keep
behind a spoiler line. That reasoning stays here, in the skill's own documentation; do
not write it into the catalogue as a note. Titles carry both languages when the
statements are bilingual (`210. Course Schedule II / 课程表 II`).

## .gitattributes

Copy verbatim. Both halves are load-bearing: a batch file normalized to LF executes
fragments of its own source, and a test file normalized to CRLF makes the same seed
produce different bytes on Windows than on macOS.

```
# cmd.exe seeks through a batch file as it runs; an LF-only file with a `for` block
# and a `goto` inside it can jump to the wrong offset. Keep the wrappers CRLF.
*.cmd text eol=crlf

# Everything the harness reads or writes is LF, on every platform, so the same seed
# produces byte-identical tests on Windows and macOS.
*.sh   text eol=lf
*.py   text eol=lf
*.md   text eol=lf
*.json text eol=lf
*.in   text eol=lf
*.out  text eol=lf
```

## .gitignore

Append these to whatever is already there.

```
# The LLM review key. Never committed — .env.example, which is only the names, is.
.env

__pycache__/
*.pyc
```

Short on purpose. `solutions/` is **not** ignored — the archive is the point of the
repo. Neither is `.oa/`, which has to travel: it carries the generator, the references,
and the stub that `wipe` restores from. Nor are the entry files: committing `main.cpp`
and `main.py` is what lets a half-finished attempt follow the user to another machine,
and `./oa.sh wipe` is how they choose to start cold instead.

Add `main.cpp` and `main.py` here only if they want the opposite — a repo holding clean
workspaces plus `solutions/`, where a clone has no entry file until `wipe` writes one
from the committed stub.

## .env.example

This one is committed — it holds names, not values, and it is the only place the
spelling of them is written down. It doubles as the reminder that its unsuffixed
sibling is never committed. If the repo already has one, leave it alone.

```
# Copy this file to .env and fill in a key to enable `./judge.sh --llm`.
# .env is gitignored: never commit the real one. This file holds names, not secrets.
OA_REVIEW_API_KEY=

# Both optional. The default is the Anthropic Messages API; setting a base URL
# switches to OpenAI-compatible chat completions, which then needs a model name too.
# OA_REVIEW_MODEL=
# OA_REVIEW_BASE_URL=
```

Those three names and no others: they are what `oa.py`'s `review_config()` looks up,
and a template naming a variable the harness does not read is worse than no template.

## Before handing it over

- `git check-ignore -v .env` names the `.gitignore` line, and `.env.example` is *not*
  ignored — the names are meant to travel, only the values stay home.
- `git status` in a solved folder shows `solutions/` and the entry file as
  untracked-and-addable, not ignored.
- Only if they chose to ignore entry files: `git check-ignore -v <slug>/main.py` names
  the line, and the file is not already tracked — an ignore rule does nothing to a
  tracked file until `git rm --cached` takes it out of the index.
- The CATALOGUE table has no topic column, and its `Category` / `Notes` columns are
  empty.
- The README's placeholders are filled in.
