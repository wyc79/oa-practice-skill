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

```sh
npx skills add wyc79/oa-practice-skill
```

That finds the skill in [`oa-practice/`](oa-practice/) and installs it to
`~/.claude/skills/`. Add `--list` to look before installing, or `-a claude-code` to
pin the target agent.

By hand instead — clone and copy that one directory, since everything beside it is
repo scaffolding:

```sh
git clone https://github.com/wyc79/oa-practice-skill
cp -r oa-practice-skill/oa-practice ~/.claude/skills/
```

To have `git pull` update the installed skill, symlink instead of copying:

```sh
git clone https://github.com/wyc79/oa-practice-skill ~/src/oa-practice-skill
ln -s ~/src/oa-practice-skill/oa-practice ~/.claude/skills/oa-practice
```

On Windows use `mklink /D "%USERPROFILE%\.claude\skills\oa-practice" "<clone>\oa-practice"`,
which needs an elevated prompt or Developer Mode.

Either way, start a new Claude Code session afterwards so the skill is picked up.

## Use

Paste a problem statement with its samples and say what you want:

> Here's an OA question I got — set it up so I can practise it.

Claude scaffolds a folder and hands it back. From then on it is just:

| | macOS / Linux | Windows |
|---|---|---|
| Run the samples | `./run.sh` | `.\run.cmd` |
| Submit for a score | `./judge.sh` | `.\judge.cmd` |
| Submit, explain the first failure | `./judge.sh --reveal 1` | `.\judge.cmd --reveal 1` |
| Replay one test in full | `./oa.sh case t07-max` | `.\oa.cmd case t07-max` |

`run` explains every failing sample; the statement prints those anyway. `judge` returns
a score and which tests were red, and no diffs — on a real OA the expected output of a
hidden test *is* the answer. The last two rows are the deliberate way past that when
you would rather learn than be scored.

## Requirements

- **Python 3.8+** — runs the harness. The wrappers search PATH and then fall back to
  whichever interpreter built the workspace, so they work even where `python3` is a
  Microsoft Store stub. If one still can't find anything, set `OA_PYTHON`.
- **A C++ compiler**, if you want to solve in C++ (the default). `g++`, `clang++` or
  `c++` on PATH — `xcode-select --install` on macOS, MSYS2 on Windows. Solving in
  Python needs nothing extra.

Other languages go through `build_cmd` / `run_cmd` in `problem.json`; see
[oa-practice/references/authoring.md](oa-practice/references/authoring.md).

## Layout

```
oa-practice/              # <- this is the skill; copy this into ~/.claude/skills/
├── SKILL.md              # the workflow Claude follows
├── references/           # authoring reference: parsing, generators, checkers
├── scripts/scaffold.py   # stamps out a new problem folder
└── assets/
    ├── harness/          # oa.py and the run/judge/oa wrappers
    └── stubs/            # main.cpp, main.py
README.md  LICENSE        # repo scaffolding, not part of the skill
```

## License

MIT — see [LICENSE](LICENSE).
