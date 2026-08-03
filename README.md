# oa-practice

A Claude Code skill that turns a coding-assessment problem into a local OA workspace —
the kind with a **Run Code** button, a **Submit** button and a score out of *n*.

You paste the problem. Claude builds the workspace around it: a main file with the
input already parsed, the statement's samples wired to a runner, and a hidden judge
that scores your solution on 20+ generated tests. It does not write the algorithm —
`solve()` arrives as a `// TODO` and stays that way unless you ask otherwise.

```
$ ./judge.sh
  PASS t01-nzero        31 ms    12.5 MB
  FAIL t14-max          62 ms    36.8 MB

Score: 23/24 (96%)   slowest 62 ms / limit 3000 ms
```

Pass everything and it also reports how your solution scales — measured time and peak
memory against input size, with a fitted growth exponent, so you can see whether you
actually hit the intended complexity.

## Install

This repo *is* the skill, so clone it straight into your skills directory:

```sh
git clone https://github.com/wyc79/oa-practice ~/.claude/skills/oa-practice
```

Update it later with `git -C ~/.claude/skills/oa-practice pull`. Start a new Claude
Code session and it will pick the skill up.

## Use

Paste a problem statement with its samples and say what you want:

> Here's an OA question I got — set it up so I can practise it.

Claude scaffolds a folder and hands it back. From then on it is just:

| | macOS / Linux | Windows |
|---|---|---|
| Run the samples | `./run.sh` | `.\run.cmd` |
| Submit for a score | `./judge.sh` | `.\judge.cmd` |
| Score only, no hints | `./judge.sh --reveal 0` | `.\judge.cmd --reveal 0` |

## Requirements

- **Python 3.8+** — runs the harness. The wrappers search PATH and then fall back to
  whichever interpreter built the workspace, so they work even where `python3` is a
  Microsoft Store stub. If one still can't find anything, set `OA_PYTHON`.
- **A C++ compiler**, if you want to solve in C++ (the default). `g++`, `clang++` or
  `c++` on PATH — `xcode-select --install` on macOS, MSYS2 on Windows. Solving in
  Python needs nothing extra.

Other languages go through `build_cmd` / `run_cmd` in `problem.json`; see
[references/authoring.md](references/authoring.md).

## Layout

```
SKILL.md              # the workflow Claude follows
references/           # authoring reference: parsing, generators, checkers
scripts/scaffold.py   # stamps out a new problem folder
assets/
├── harness/          # oa.py and the run/judge wrappers
└── stubs/            # main.cpp, main.py
```

## License

MIT — see [LICENSE](LICENSE).
