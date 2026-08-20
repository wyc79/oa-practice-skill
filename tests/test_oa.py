"""End-to-end tests for the OA harness.

Everything here drives `oa.py` as a subprocess against a real scaffolded workspace,
because the failures worth catching are the ones where a command exits 0 over a suite
that proves nothing — a stale cache, an unreached bound, a reference for the wrong
problem, an entry file that reads a format nobody generates. Those are invisible to a
unit test of any single function; they are only wrong at the exit code.

The problem under test is "sum an array", small enough that a full judge run is a
fraction of a second and every reference is exact.
"""
import http.server
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCAFFOLD = REPO / "oa-practice" / "scripts" / "scaffold.py"


# ------------------------------------------------------------------ workspace

GEN = '''
LIMITS = {"n": (0, 100), "a_i": (-1000, 1000)}


def measure(data):
    t = data.split()
    n = int(t[0])
    return {"n": n, "a_i": [int(x) for x in t[1:1 + n]]}


def fmt(xs):
    return f"{len(xs)}\\n" + " ".join(map(str, xs)) + "\\n"


def cases(rng):
    yield "nzero", "0\\n\\n"
    yield "vmin", fmt([-1000, 5])
    yield "three", fmt([1, 2, 3])
    for _ in range(3):
        yield fmt([rng.randint(-10, 10) for _ in range(rng.randint(1, 4))])
    yield "max", fmt([1000] * 100)
'''

REF = '''
def solve(data):
    t = data.split()
    n = int(t[0])
    return str(sum(int(x) for x in t[1:1 + n]))
'''

# A correct solution, so a green judge run means the harness agreed with itself.
MAIN = '''
import sys


def solve(a):
    return sum(a)


def main():
    d = sys.stdin.read().split()
    n = int(d[0])
    print(solve([int(x) for x in d[1:1 + n]]))


main()
'''

# Wrong on every input, for the tests about how failures are reported.
WRONG = MAIN.replace("return sum(a)", "return 999999")

PRINT = "    print(solve([int(x) for x in d[1:1 + n]]))"
FLOAT_OK = MAIN.replace(PRINT, "    print('%.8f' % solve([int(x) for x in d[1:1 + n]]))")
FLOAT_OFF = MAIN.replace(PRINT, "    print('%.8f' % (solve([int(x) for x in d[1:1 + n]]) + 0.001))")
assert FLOAT_OK != MAIN and FLOAT_OFF != MAIN, "PRINT no longer matches MAIN"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def oa(ws, *args, expect=None, env=None):
    """Run a harness command. `expect` asserts the exit code, since for most of these
    the exit code *is* the behaviour under test."""
    # utf-8 explicitly: oa.py pins its streams to utf-8, so decoding by the system
    # locale would turn every em-dash into mojibake on a cp936/cp1252 console and make
    # any assertion about the wording quietly unreliable.
    # OA_REVIEW_* is stripped rather than inherited: a developer with a real key
    # exported must not have the suite quietly phone home and bill them. Tests that
    # want the review layer configured pass `env` explicitly.
    clean = {k: v for k, v in os.environ.items() if not k.startswith("OA_REVIEW_")}
    p = subprocess.run([sys.executable, "oa.py", *args], cwd=ws, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env={**clean, "NO_COLOR": "1", **(env or {})})
    if expect is not None:
        assert p.returncode == expect, (
            f"expected exit {expect}, got {p.returncode}\n--- stdout ---\n{p.stdout}"
            f"\n--- stderr ---\n{p.stderr}")
    return p


def out(p):
    return p.stdout + p.stderr


def cfg(ws, **kw):
    path = ws / "problem.json"
    c = json.loads(path.read_text(encoding="utf-8-sig"))
    c.update(kw)
    write(path, json.dumps(c, indent=2) + "\n")


def sample(ws, i, inp, expected=None):
    write(ws / "tests" / "samples" / f"sample{i}.in", inp)
    if expected is not None:
        write(ws / "tests" / "samples" / f"sample{i}.out", expected)


def answers(ws):
    return sorted(p.name for p in (ws / "tests" / "hidden").glob("*.out"))


@pytest.fixture
def raw(tmp_path):
    """Straight out of scaffold.py — gen.py and reference.py still the worked example."""
    subprocess.run([sys.executable, str(SCAFFOLD), "p", "--dir", str(tmp_path),
                    "--lang", "python"], check=True, capture_output=True)
    return tmp_path / "p"


@pytest.fixture
def ws(raw):
    """A finished workspace: real generator, real reference, correct solution, samples."""
    write(raw / ".oa" / "gen.py", GEN)
    write(raw / ".oa" / "ref" / "reference.py", REF)
    write(raw / "main.py", MAIN)
    sample(raw, 1, "3\n1 2 3\n", "6\n")
    sample(raw, 2, "0\n\n", "0\n")
    return raw


# ------------------------------------------------------------------- packaging
# Skill packaging drops dot-entries: an installed copy of the skill arrives with no
# assets/harness/.oa at all, and the workspace it stamps out has no generator, no
# references and no python-path. So the template carries them undotted and scaffold
# renames them on the way out. An asset that drifts back to a dotted name works from
# a git clone and breaks for everyone who installed the skill instead.

def test_assets_carry_no_dot_entries():
    dotted = sorted(str(p.relative_to(REPO))
                    for p in (REPO / "oa-practice" / "assets").rglob(".*"))
    assert dotted == [], f"these will not survive packaging: {dotted}"


def test_scaffold_dots_the_internal_directory(raw):
    assert (raw / ".oa" / "gen.py").exists()
    assert (raw / ".oa" / "ref" / "reference.py").exists()
    assert (raw / ".oa" / "python-path").exists()
    assert not (raw / "oa-internal").exists()


# --------------------------------------------------- the skeletons scaffold writes
# The README is the problem and HINTS.md is everything known about it. The split only
# works if the README skeleton does not prompt for the answer, so the wording of that
# one section is worth a test — it is the thing that quietly drifts back.

def test_scaffold_writes_hints_beside_the_readme(tmp_path):
    subprocess.run([sys.executable, str(SCAFFOLD), "zigzag-walk", "--dir", str(tmp_path),
                    "--lang", "python"], check=True, capture_output=True)
    ws = tmp_path / "zigzag-walk"
    readme, hints = (ws / "README.md").read_text(), (ws / "HINTS.md").read_text()
    assert readme.startswith("# zigzag-walk\n")
    assert hints.startswith("# zigzag-walk — hints\n")
    assert "PROBLEM_SLUG" not in readme and "PROBLEM_SLUG" not in hints


def test_the_hints_skeleton_asks_for_its_three_sections(raw):
    hints = (raw / "HINTS.md").read_text()
    assert "Spoilers ahead" in hints
    for section in ("## Knowledge point", "## Why the constraints force it",
                    "## Related problems on LeetCode"):
        assert section in hints, section
    # The bilingual entry is shown rather than described, so the shape — both titles,
    # both hosts, one slug — is on hand instead of remembered.
    assert "leetcode.com/problems/course-schedule-ii/" in hints
    assert "leetcode.cn/problems/course-schedule-ii/" in hints
    assert "课程表 II" in hints


def test_the_readme_skeleton_keeps_its_sections(raw):
    readme = (raw / "README.md").read_text()
    for section in ("## Input", "## Output", "## Constraints", "## Target",
                    "## Running it"):
        assert section in readme, section


def test_the_readme_target_section_gives_nothing_away(raw):
    readme = (raw / "README.md").read_text()
    target = readme.split("## Target", 1)[1].split("\n## ", 1)[0]
    # It points at the spoiler door rather than being one...
    assert "HINTS.md" in target
    # ...and still asks for the one honest admission that belongs on this side of it.
    assert "lowered" in target
    # The two things that hand over the answer: a complexity, or a name for the method.
    assert "O(" not in target
    assert "complexity" not in target.lower()
    assert not re.search(r"sort|greedy|dynamic programming|two.pointer|binary search"
                         r"|Dijkstra|topological|sliding window", target, re.I)


# ------------------------------------------------------- the template must block
# The scaffold ships a *working* generator and reference for a different problem.
# Left in place they produce a green suite that grades nothing anyone asked about,
# which is the failure the whole design exists to prevent.

def test_scaffold_refuses_to_generate(raw):
    assert "TEMPLATE" in out(oa(raw, "gen", expect=2))


def test_scaffold_refuses_to_compute_answers(raw):
    assert "TEMPLATE" in out(oa(raw, "answers", expect=2))


def test_scaffold_refuses_to_selfcheck(raw):
    assert "TEMPLATE" in out(oa(raw, "selfcheck", expect=2))


def test_templated_reference_blocks_even_with_a_real_generator(raw):
    write(raw / ".oa" / "gen.py", GEN)
    assert "reference.py" in out(oa(raw, "answers", expect=2))


# --------------------------------------------------------------- ground truth
# selfcheck against the statement's samples is the only place a reference meets
# truth the harness did not generate itself.

def test_selfcheck_without_samples_is_not_green(ws):
    for f in (ws / "tests" / "samples").glob("*"):
        f.unlink()
    p = oa(ws, "selfcheck", expect=1)
    assert "NOTHING TO CHECK" in out(p)


def test_selfcheck_catches_a_reference_that_misreads_the_statement(ws):
    write(ws / ".oa" / "ref" / "reference.py", REF.replace("sum(", "1 + sum("))
    assert "MISMATCH" in out(oa(ws, "selfcheck", expect=1))


def test_selfcheck_checks_the_fast_reference_too(ws):
    write(ws / ".oa" / "ref" / "reference_fast.py", REF.replace("sum(", "1 + sum("))
    p = oa(ws, "selfcheck", expect=1)
    assert "reference_fast vs samples" in out(p) and "MISMATCH" in out(p)


# ---------------------------------------------------------- boundary coverage

def test_coverage_passes_on_a_suite_that_reaches_its_bounds(ws):
    assert "joint max corner" in out(oa(ws, "gen", expect=0))


def test_coverage_fails_when_an_endpoint_is_never_reached(ws):
    write(ws / ".oa" / "gen.py", GEN.replace('yield "max", fmt([1000] * 100)',
                                             'yield "max", fmt([1000] * 99)'))
    p = oa(ws, "gen", expect=2)
    assert "MISSING max" in out(p)


def test_coverage_fails_on_a_value_outside_its_declared_bound(ws):
    write(ws / ".oa" / "gen.py", GEN.replace('yield "vmin", fmt([-1000, 5])',
                                             'yield "vmin", fmt([-5000, 5])'))
    p = oa(ws, "gen", expect=2)
    assert "VIOLATION" in out(p) and "-5000" in out(p)


def test_coverage_fails_when_no_test_attains_every_bound_at_once(ws):
    # n reaches 100 and a_i reaches 1000, but never in the same test — which is
    # exactly where a 32-bit accumulator would have overflowed.
    write(ws / ".oa" / "gen.py", GEN.replace(
        'yield "max", fmt([1000] * 100)',
        'yield "nmax", fmt([1] * 100)\n    yield "vmax", fmt([1000, 1000])'))
    p = oa(ws, "gen", expect=2)
    assert "joint max corner" in out(p) and "MISSING" in out(p)


def test_limits_without_measure_is_a_hard_failure(ws):
    src = GEN.replace("def measure(data):", "def _unused(data):")
    write(ws / ".oa" / "gen.py", src)
    assert "no measure()" in out(oa(ws, "gen", expect=2))


def test_measure_without_limits_is_a_hard_failure(ws):
    write(ws / ".oa" / "gen.py", GEN.replace("LIMITS =", "_LIMITS ="))
    assert "no LIMITS" in out(oa(ws, "gen", expect=2))


def test_declaring_neither_is_a_warning_not_a_failure(ws):
    src = GEN.replace("LIMITS =", "_LIMITS =").replace("def measure(data):", "def _m(data):")
    write(ws / ".oa" / "gen.py", src)
    assert "boundaries unchecked" in out(oa(ws, "gen", expect=0))


def test_no_corner_exempts_a_key_from_the_joint_maximum(ws):
    # A budget shared between two keys makes the corner unsatisfiable as declared, so
    # the exemption has to actually drop the key rather than merely soften the message.
    src = GEN.replace('"a_i": (-1000, 1000)}', '"a_i": (-1000, 1000, "no-corner")}')
    src = src.replace('yield "max", fmt([1000] * 100)',
                      'yield "nmax", fmt([1] * 100)\n    yield "vmax", fmt([1000, -1000])')
    write(ws / ".oa" / "gen.py", src)
    p = oa(ws, "gen", expect=0)
    assert "corner exempt" in out(p)


UNSATURATED = GEN.replace('yield "max", fmt([1000] * 100)',
                          'yield "max", fmt([1000] * 99 + [5])')
assert UNSATURATED != GEN, "the corner case in GEN has moved"


def test_no_saturate_drops_the_hint(ws):
    # The corner attains a_i's maximum but cannot hold every element there. The hint
    # has no legal answer, so there has to be a way to say so.
    write(ws / ".oa" / "gen.py", UNSATURATED)
    assert "not saturated" in out(oa(ws, "gen", expect=0))

    write(ws / ".oa" / "gen.py",
          UNSATURATED.replace('"a_i": (-1000, 1000)}', '"a_i": (-1000, 1000, "no-saturate")}'))
    p = oa(ws, "gen", expect=0)
    assert "not saturated" not in out(p) and "saturation exempt" in out(p)


def test_no_saturate_still_requires_the_joint_corner(ws):
    # The whole point of it being weaker than no-corner: the maximum is still required
    # to be attained somewhere, by a single test, alongside every other maximum.
    src = GEN.replace('"a_i": (-1000, 1000)}', '"a_i": (-1000, 1000, "no-saturate")}')
    src = src.replace('yield "max", fmt([1000] * 100)',
                      'yield "nmax", fmt([1] * 100)\n    yield "vmax", fmt([1000, 1000])')
    write(ws / ".oa" / "gen.py", src)
    p = oa(ws, "gen", expect=2)
    assert "joint max corner" in out(p) and "MISSING" in out(p)


# ------------------------------------------------------------ the answer cache
# tests/hidden is a cache of two expensive things. Both were once keyed on nothing
# but existence, so an edit could be silently overridden and score a green nobody
# earned; and `gen` used to discard every answer whether or not anything changed.

def test_gen_is_idempotent_and_keeps_answers(ws):
    oa(ws, "answers", expect=0)
    before = answers(ws)
    assert before
    oa(ws, "gen", expect=0)
    assert answers(ws) == before


def test_gen_force_discards_answers(ws):
    oa(ws, "answers", expect=0)
    assert answers(ws)
    oa(ws, "gen", "--force", expect=0)
    assert answers(ws) == []


def test_gen_reports_coverage_even_when_nothing_needed_rebuilding(ws):
    # Otherwise a `gen` that failed coverage, rerun, prints nothing and exits 0 —
    # which reads as the failure having cleared itself.
    oa(ws, "gen", expect=0)
    assert "Boundary coverage" in out(oa(ws, "gen", expect=0))


def test_appending_a_case_costs_one_reference_run(ws):
    oa(ws, "answers", expect=0)
    n_before = len(answers(ws))
    write(ws / ".oa" / "gen.py", GEN.replace(
        'yield "max", fmt([1000] * 100)',
        'yield "max", fmt([1000] * 100)\n    yield "extra", fmt([7, 8])'))
    p = oa(ws, "gen", expect=0)
    assert "cached answers still valid" in out(p)
    p = oa(ws, "answers", expect=0)
    assert "1 to compute" in out(p)
    assert len(answers(ws)) == n_before + 1


def test_removing_a_case_drops_its_answer(ws):
    oa(ws, "answers", expect=0)
    assert "vmin.out" in " ".join(answers(ws))
    write(ws / ".oa" / "gen.py", GEN.replace('    yield "vmin", fmt([-1000, 5])\n', ""))
    # vmin was the only test reaching a_i's minimum, so coverage must now fail —
    # and the input must still be gone.
    oa(ws, "gen", expect=2)
    assert "vmin.out" not in " ".join(answers(ws))


def test_editing_a_reference_discards_every_answer(ws):
    oa(ws, "answers", expect=0)
    write(ws / ".oa" / "ref" / "reference.py", REF + "\n# touched\n")
    p = oa(ws, "answers", expect=0)
    assert "recomputing all" in out(p)


def test_changing_the_seed_rebuilds_the_inputs(ws):
    oa(ws, "gen", expect=0)
    before = (ws / "tests" / "hidden" / "t04.in").read_text()
    cfg(ws, seed=999)
    oa(ws, "gen", expect=0)
    assert (ws / "tests" / "hidden" / "t04.in").read_text() != before


def test_judge_picks_up_an_edited_generator(ws):
    oa(ws, "answers", expect=0)
    write(ws / ".oa" / "gen.py", GEN.replace(
        'yield "max", fmt([1000] * 100)',
        'yield "max", fmt([1000] * 100)\n    yield "late", fmt([4, 4])'))
    p = oa(ws, "judge", expect=0)
    assert "t08-late" in out(p)


def test_a_coverage_failure_stays_failed(ws):
    # It used to be laundered into a green: `gen` stamped the cache before checking
    # it, so the next judge took the silent fast path and printed 100% over a suite
    # that never reached its own declared bounds. A hard failure that two of the four
    # commands forget is the exact shape of failure this harness exists to prevent.
    write(ws / ".oa" / "gen.py", GEN.replace("fmt([1000] * 100)", "fmt([1000] * 99)"))
    assert "MISSING" in out(oa(ws, "gen", expect=2))
    p = oa(ws, "judge", expect=2)
    assert "MISSING" in out(p) and "Score" not in out(p)


def test_timings_survive_an_interrupted_answer_pass(ws):
    # answers is resumable by design and expected to be interrupted, but _timings.json
    # was written only after the whole loop — so every timing that had already landed
    # was lost, and the resumed pass never recomputes those tests.
    write(ws / ".oa" / "ref" / "reference.py", REF + '''
_real = solve


def solve(data):
    if data.split()[0] == "100":     # blow up on the max-size test, mid-pass
        raise ValueError("boom")
    return _real(data)
''')
    oa(ws, "answers", expect=2)
    landed = answers(ws)
    assert landed, "answers before the crash should have been written"
    timings = json.loads((ws / "tests" / "hidden" / "_timings.json").read_text())
    assert sorted(timings) == sorted(f[:-4] for f in landed)


def test_selfcheck_refuses_to_pass_on_a_stale_cache(ws):
    oa(ws, "answers", expect=0)
    write(ws / ".oa" / "gen.py", GEN.replace(
        'yield "max", fmt([1000] * 100)',
        'yield "max", fmt([1000] * 100)\n    yield "late", fmt([4, 4])'))
    assert "stale" in out(oa(ws, "selfcheck", expect=1))


# ------------------------------------------------------------------- checkers

def test_token_checker_ignores_whitespace(ws):
    write(ws / "main.py", MAIN.replace("print(solve(", "print('  %d  ' % solve("))
    oa(ws, "judge", expect=0)


def test_exact_checker_does_not(ws):
    cfg(ws, checker="exact")
    write(ws / "main.py", MAIN.replace("print(solve(", "print('%d ' % solve("))
    oa(ws, "judge", expect=1)


def test_float_checker_accepts_within_eps(ws):
    cfg(ws, checker="float", float_eps=1e-6)
    write(ws / "main.py", FLOAT_OK)
    oa(ws, "judge", expect=0)


def test_float_checker_rejects_beyond_eps(ws):
    cfg(ws, checker="float", float_eps=1e-9)
    write(ws / "main.py", FLOAT_OFF)
    # It has to fail as a wrong *answer*, not as a crash — an earlier version of this
    # test built a main file with unbalanced parentheses and passed on the SyntaxError.
    assert "token 0" in out(oa(ws, "judge", "--reveal", "1", expect=1))


def test_custom_checker_is_consulted(ws):
    cfg(ws, checker="custom")
    write(ws / ".oa" / "checker.py", "def check(inp, expected, actual):\n    return True\n")
    write(ws / "main.py", WRONG)
    oa(ws, "judge", expect=0)


def test_custom_checker_reason_reaches_the_report(ws):
    cfg(ws, checker="custom")
    write(ws / ".oa" / "checker.py",
          "def check(inp, expected, actual):\n    return False, 'nope-sentinel'\n")
    assert "nope-sentinel" in out(oa(ws, "judge", "--reveal", "1", expect=1))


# --------------------------------------------------- can the checker ever say no?
# `checker: custom` replaces the harness's own comparison outright, and the file
# doing the replacing is hand-written per problem. Nothing else here ever asks it to
# reject anything: samples, coverage and the plumbing check all consult it, and all
# three stay green while it accepts everything — so a checker that never says no
# scores an empty solution at 100%.

PERMISSIVE = "def check(inp, expected, actual):\n    return True\n"
DISCRIMINATING = ("def check(inp, expected, actual):\n"
                  "    return expected.split() == actual.split()\n")

# Every case sums to zero, so every expected output is "0" and no two tests can be
# crossed against each other.
FLAT_GEN = '''
LIMITS = {"n": (0, 100), "a_i": (-1000, 1000)}


def measure(data):
    t = data.split()
    n = int(t[0])
    return {"n": n, "a_i": [int(x) for x in t[1:1 + n]]}


def fmt(xs):
    return f"{len(xs)}\\n" + " ".join(map(str, xs)) + "\\n"


def cases(rng):
    yield "nzero", "0\\n\\n"
    yield "pair", fmt([-1000, 1000])
    yield "max", fmt([1000] * 50 + [-1000] * 50)
'''


def test_a_permissive_custom_checker_is_caught(ws):
    oa(ws, "answers", expect=0)
    cfg(ws, checker="custom")
    write(ws / ".oa" / "checker.py", PERMISSIVE)
    write(ws / "_check.py", MAIN)
    p = oa(ws, "selfcheck", "--entry", "_check.py", expect=1)
    assert "accepted another test's answer" in out(p)


def test_a_discriminating_custom_checker_passes_the_control(ws):
    oa(ws, "answers", expect=0)
    cfg(ws, checker="custom")
    write(ws / ".oa" / "checker.py", DISCRIMINATING)
    write(ws / "_check.py", MAIN)
    p = oa(ws, "selfcheck", "--entry", "_check.py", expect=0)
    assert "rejects another test's answer" in out(p)


def test_a_checker_that_raises_on_a_crossed_answer_counts_as_rejecting(ws):
    # A real checker may well blow up on an answer that makes no sense for the input
    # it is handed. That is a rejection, not a reason to take the harness down.
    oa(ws, "answers", expect=0)
    cfg(ws, checker="custom")
    write(ws / ".oa" / "checker.py",
          "def check(inp, expected, actual):\n"
          "    if expected.split() != actual.split():\n"
          "        raise ValueError('nonsense')\n"
          "    return True\n")
    write(ws / "_check.py", MAIN)
    oa(ws, "selfcheck", "--entry", "_check.py", expect=0)


def test_the_checker_control_is_skipped_when_no_two_answers_differ(ws):
    # Nothing to cross, so there is no edit that would satisfy the control. Say so
    # and carry on rather than failing a workspace nobody can fix.
    write(ws / ".oa" / "gen.py", FLAT_GEN)
    sample(ws, 1, "2\n-5 5\n", "0\n")
    oa(ws, "answers", expect=0)
    cfg(ws, checker="custom")
    write(ws / ".oa" / "checker.py", PERMISSIVE)
    write(ws / "_check.py", MAIN)
    p = oa(ws, "selfcheck", "--entry", "_check.py", expect=0)
    assert "same expected output" in out(p)


# ------------------------------------------------------------- reveal budgets
# Submit returns a score. The expected output of a hidden test *is* the answer, so a
# judge that volunteers the diff has quietly turned Submit into Run.

def test_judge_gives_away_nothing_by_default(ws):
    write(ws / "main.py", WRONG)
    text = out(oa(ws, "judge", expect=1))
    assert "FAIL" in text
    assert "expected:" not in text
    assert "token 0:" not in text


def test_judge_reveal_one_explains_exactly_one(ws):
    write(ws / "main.py", WRONG)
    text = out(oa(ws, "judge", "--reveal", "1", expect=1))
    assert text.count("expected:") == 1


def test_judge_names_the_escape_hatch_when_something_failed(ws):
    write(ws / "main.py", WRONG)
    assert "--reveal 1" in out(oa(ws, "judge", expect=1))


def test_run_explains_every_failing_sample(ws):
    # The statement prints these anyway, so there is nothing here to protect.
    write(ws / "main.py", WRONG)
    sample(ws, 3, "2\n5 5\n", "10\n")
    text = out(oa(ws, "run", expect=1))
    assert text.count("FAIL") == 3 and text.count("expected:") == 3


def test_case_explains_by_default(ws):
    write(ws / "main.py", WRONG)
    oa(ws, "answers", expect=0)
    assert "expected:" in out(oa(ws, "case", "t03-three", expect=1))


# ------------------------------------------------------- verdicts & exit codes

def test_runtime_error_is_reported_as_re(ws):
    write(ws / "main.py", "import sys\nsys.stdin.read()\nraise SystemExit('boom')\n")
    assert "RE" in out(oa(ws, "run", expect=1))


def test_over_the_limit_is_reported_as_tle(ws):
    cfg(ws, time_limit_ms=100)
    write(ws / "main.py", "import sys, time\nsys.stdin.read()\ntime.sleep(0.6)\nprint(0)\n")
    assert "TLE" in out(oa(ws, "run", expect=1))


def test_a_sample_without_an_expected_output_is_skipped_not_scored(ws):
    sample(ws, 3, "2\n1 1\n")
    text = out(oa(ws, "run", expect=0))
    assert "SKIP" in text and "2/2" in text and "1 skipped" in text


def test_a_suite_that_scored_nothing_is_not_green(ws):
    for f in (ws / "tests" / "samples").glob("*.out"):
        f.unlink()
    assert "nothing to score" in out(oa(ws, "run", expect=1))


def test_judge_exits_zero_only_on_a_full_pass(ws):
    oa(ws, "judge", expect=0)
    write(ws / "main.py", WRONG)
    oa(ws, "judge", expect=1)


# -------------------------------------------------------- two-tier references

def test_fast_reference_disagreeing_with_brute_stops_the_pass(ws):
    write(ws / ".oa" / "ref" / "reference_fast.py", REF.replace("sum(", "1 + sum("))
    p = oa(ws, "answers", expect=2)
    assert "disagrees" in out(p)


def test_brute_force_timeout_without_a_fast_reference_is_fatal(ws):
    cfg(ws, ref_time_limit_ms=300)
    write(ws / ".oa" / "ref" / "reference.py", "import time\n" + REF.replace(
        "    t = data.split()", "    time.sleep(2)\n    t = data.split()"))
    p = oa(ws, "answers", expect=2)
    assert "reference_fast" in out(p)


def test_a_fast_reference_answers_what_brute_force_cannot(ws):
    cfg(ws, ref_time_limit_ms=300)
    write(ws / ".oa" / "ref" / "reference.py", "import time\n" + REF.replace(
        "    t = data.split()", "    time.sleep(2)\n    t = data.split()"))
    write(ws / ".oa" / "ref" / "reference_fast.py", REF)
    p = oa(ws, "answers", expect=0)
    assert "beyond brute force" in out(p)
    assert len(answers(ws)) == 7


# ---------------------------------------------------------------- the plumbing
# A main file that reads a format nobody generates, or prints a shape the reference
# does not, turns every hidden test red at once — and from the user's side that is
# indistinguishable from a wrong algorithm.

def test_selfcheck_before_answers_does_not_demand_a_plumbing_check(ws):
    # Step 7 runs selfcheck here on purpose, to catch a misread statement before
    # paying for the slow pass. Not applicable is not the same as unchecked.
    oa(ws, "gen", expect=0)
    p = oa(ws, "selfcheck", expect=0)
    assert "not checkable until answers exist" in out(p)


def test_selfcheck_after_answers_fails_without_a_plumbing_check(ws):
    oa(ws, "answers", expect=0)
    assert "OUTPUT SHAPE UNCHECKED" in out(oa(ws, "selfcheck", expect=1))


def test_plumbing_passes_on_a_correct_stand_in(ws):
    oa(ws, "answers", expect=0)
    write(ws / "_check.py", MAIN)
    p = oa(ws, "selfcheck", "--entry", "_check.py", expect=0)
    assert "100%" in out(p)


def test_plumbing_catches_a_wrong_output_shape(ws):
    oa(ws, "answers", expect=0)
    write(ws / "_check.py", MAIN.replace("print(solve(", "print('sum =', solve("))
    p = oa(ws, "selfcheck", "--entry", "_check.py", expect=1)
    text = out(p)
    assert "the workspace is broken, not the solution" in text
    # Everything red is the signature of a format mismatch, so the author gets sent to
    # the entry file rather than made to hunt through the reference.
    assert "format" in text and "main.py" in text


# ------------------------------------------------------------- the answer key
# The samples are the only external ground truth in the workspace, and they are small.
# Past their reach reference.py *is* the definition of correct, so a misreading it
# shares with nothing else writes itself into every hidden answer unchallenged. The
# --entry gate is the only thing that can contradict it — and only when the stand-in's
# algorithm came from the statement rather than from a port of the reference.

# Agrees with both samples (n = 3 and n = 0) and wrong from n >= 4 up, so the answer
# key is wrong on a subset of the suite and right on everything with ground truth.
BIASED = REF.replace("return str(sum(int(x) for x in t[1:1 + n]))",
                     "return str(sum(int(x) for x in t[1:1 + n]) + (1 if n >= 4 else 0))")
assert BIASED != REF, "REF's return has moved"


def test_a_reference_wrong_past_the_samples_still_passes_selfcheck(ws):
    # The premise of everything below: sample agreement is not answer-key correctness,
    # and the sample gate has no way to notice on its own. It reports `consistent`,
    # which is true of the two tests it can see and says nothing about the other seven.
    write(ws / ".oa" / "ref" / "reference.py", BIASED)
    assert "consistent" in out(oa(ws, "selfcheck", expect=0))


def test_plumbing_blames_the_reference_when_only_a_subset_fails(ws):
    # A wrong output shape fails everything at once; this fails some. That difference
    # is the whole diagnosis, and getting it wrong sends the author to reconcile
    # parsing in a file whose parsing is fine.
    write(ws / ".oa" / "ref" / "reference.py", BIASED)
    oa(ws, "answers", expect=0)
    write(ws / "_check.py", MAIN)
    text = out(oa(ws, "selfcheck", "--entry", "_check.py", expect=1))
    assert "answer key and the stand-in disagree" in text
    assert "reference.py" in text
    assert "the workspace is broken" not in text


def test_a_stand_in_sharing_the_references_bug_scores_full_marks(ws):
    # The hole no harness can close: two implementations of the same misreading agree
    # everywhere, so the gate reports 100% over an answer key that is wrong. It is
    # pinned here because the only defence is the instruction to re-derive the
    # stand-in's algorithm, and a silent regression would take that instruction's
    # justification with it.
    write(ws / ".oa" / "ref" / "reference.py", BIASED)
    oa(ws, "answers", expect=0)
    write(ws / "_check.py", MAIN.replace(
        "return sum(a)", "return sum(a) + (1 if len(a) >= 4 else 0)"))
    assert "100%" in out(oa(ws, "selfcheck", "--entry", "_check.py", expect=0))


def test_answer_key_names_its_only_ground_truth(ws):
    oa(ws, "answers", expect=0)
    write(ws / "_check.py", MAIN)
    text = out(oa(ws, "selfcheck", "--entry", "_check.py", expect=0))
    assert "Answer key" in text
    assert "reference.py alone" in text


def test_answer_key_reports_the_range_the_samples_never_reach(ws):
    # Samples run to n = 3; the suite runs to n = 100. Everything that discriminates
    # lives in the gap, and the report has to say so rather than let a green selfcheck
    # imply the answers were checked.
    oa(ws, "answers", expect=0)
    write(ws / "_check.py", MAIN)
    text = out(oa(ws, "selfcheck", "--entry", "_check.py", expect=0))
    assert "0 .. 100" in text
    assert "outside the sampled range" in text and "n" in text


def test_answer_key_notes_when_two_references_cross_check(ws):
    write(ws / ".oa" / "ref" / "reference_fast.py", REF)
    oa(ws, "answers", expect=0)
    write(ws / "_check.py", MAIN)
    text = out(oa(ws, "selfcheck", "--entry", "_check.py", expect=0))
    assert "cross-check" in text and "reference.py alone" not in text


def test_answer_key_survives_a_workspace_without_limits(ws):
    src = GEN.replace("LIMITS =", "_LIMITS =").replace("def measure(data):", "def _m(data):")
    write(ws / ".oa" / "gen.py", src)
    oa(ws, "answers", expect=0)
    write(ws / "_check.py", MAIN)
    text = out(oa(ws, "selfcheck", "--entry", "_check.py", expect=0))
    assert "Answer key" in text and "ground truth" in text


def test_plumbing_catches_an_entry_that_dies_on_generated_input(ws):
    oa(ws, "answers", expect=0)
    write(ws / "_check.py", MAIN)
    # The stand-in is fine; the file that actually ships is not. Only the half of the
    # check that runs the real entry can see this.
    write(ws / "main.py", MAIN.replace("n = int(d[0])", "n = int(d[0]); d[10 ** 6]"))
    p = oa(ws, "selfcheck", "--entry", "_check.py", expect=1)
    assert "dies on" in out(p)


def test_plumbing_refuses_the_workspaces_own_entry(ws):
    oa(ws, "answers", expect=0)
    p = oa(ws, "selfcheck", "--entry", "main.py", expect=2)
    assert "known-correct" in out(p)


def test_plumbing_rejects_a_missing_file(ws):
    oa(ws, "answers", expect=0)
    assert "no such file" in out(oa(ws, "selfcheck", "--entry", "nope.py", expect=2))


# --entry goes through the same build() as the entry file, so the stand-in the harness
# asks for has to be one this workspace's toolchain accepts. The default language is
# C++, where a hardcoded _check.py is a compile error rather than a gate. A run_cmd
# workspace is stranger still: build() hands run_cmd back untouched, so --entry would
# be ignored and the stub scored in its place.

def foreign_entry(ws):
    """An entry file the harness never compiles, driven by run_cmd. Lets both of these
    be tested without a second toolchain on the machine."""
    write(ws / "main.rs", "// never compiled: run_cmd runs main.py\n")
    cfg(ws, entry="main.rs", run_cmd=[sys.executable, "main.py"])


def test_the_stand_in_name_follows_the_entry_suffix(ws):
    oa(ws, "answers", expect=0)
    foreign_entry(ws)
    p = oa(ws, "selfcheck", expect=1)
    assert "_check.rs" in out(p) and "_check.py" not in out(p)


def test_plumbing_refuses_to_redirect_a_custom_run_cmd(ws):
    oa(ws, "answers", expect=0)
    foreign_entry(ws)
    write(ws / "_check.rs", "// stand-in\n")
    p = oa(ws, "selfcheck", "--entry", "_check.rs", expect=2)
    assert "run_cmd" in out(p)


# ------------------------------------------------------- the redo loop
# A 100% judge files the entry file under solutions/; wipe puts the stub back. The
# rule tying them together is that wipe never destroys an attempt the archive has not
# already seen — every test below is about that rule holding.

def solutions(ws):
    return sorted(p.name for p in (ws / "solutions").glob("*.py"))


def test_scaffold_saves_a_pristine_stub(raw):
    stub = raw / ".oa" / "stub.py"
    assert stub.exists()
    assert stub.read_text() == (raw / "main.py").read_text()


def test_a_hundred_percent_judge_archives_the_entry_file(ws):
    oa(ws, "judge", expect=0)
    assert len(solutions(ws)) == 1
    assert (ws / "solutions" / solutions(ws)[0]).read_text() == MAIN


def test_a_failing_judge_archives_nothing(ws):
    write(ws / "main.py", MAIN.replace("sum(", "1 + sum("))
    oa(ws, "judge", expect=1)
    assert solutions(ws) == []


def test_a_reformatted_solution_is_not_archived_twice(ws):
    oa(ws, "judge", expect=0)
    first = solutions(ws)
    # Same code, run through something that moved the whitespace around. The archive
    # is a record of attempts, and a reformat is not one.
    write(ws / "main.py", MAIN.replace("\n", "\n\n").replace("    ", "\t"))
    p = oa(ws, "judge", expect=0)
    assert solutions(ws) == first
    assert "already archived" in out(p)


def test_a_genuinely_different_solution_is_archived_alongside(ws):
    oa(ws, "judge", expect=0)
    other = MAIN.replace("return sum(a)", "return sum(x for x in a)")
    assert other != MAIN
    write(ws / "main.py", other)
    oa(ws, "judge", expect=0)
    assert len(solutions(ws)) == 2


def test_wipe_restores_the_stub_once_the_attempt_is_archived(ws):
    oa(ws, "judge", expect=0)
    p = oa(ws, "wipe", expect=0)
    assert (ws / "main.py").read_text() == (ws / ".oa" / "stub.py").read_text()
    assert "solutions/solution-" in out(p).replace("\\", "/")


def test_wipe_refuses_an_unarchived_attempt(ws):
    p = oa(ws, "wipe", expect=2)
    assert "not in solutions/" in out(p)
    assert (ws / "main.py").read_text() == MAIN


def test_wipe_force_discards_an_unarchived_attempt(ws):
    oa(ws, "wipe", "--force", expect=0)
    assert (ws / "main.py").read_text() == (ws / ".oa" / "stub.py").read_text()
    assert solutions(ws) == []


def test_wipe_on_an_untouched_stub_is_harmless(raw):
    p = oa(raw, "wipe", expect=0)
    assert "already the stub" in out(p)


def test_wipe_needs_the_saved_stub(ws):
    oa(ws, "judge", expect=0)
    (ws / ".oa" / "stub.py").unlink()
    assert "stub.py" in out(oa(ws, "wipe", expect=2))


def test_wipe_does_not_need_a_compilable_entry(ws):
    # The moment you most want to start over is when what you have does not build.
    # wipe runs before build(), so a broken entry file is not a reason it can refuse.
    oa(ws, "judge", expect=0)
    write(ws / "main.py", "this is not python(")
    oa(ws, "wipe", "--force", expect=0)
    assert (ws / "main.py").read_text() == (ws / ".oa" / "stub.py").read_text()


# ------------------------------------------------------------- LLM review
# `judge --llm` and `review` are the only network in the harness, and the property
# worth pinning is that they cannot cost anything: whatever happens to the endpoint,
# the score and the exit code are the ones the judge already computed. The happy path
# runs against a local server, so none of this needs a key or a bill.

REPLY = "## Complexity\n\nO(n) time, O(n) space, which is the stated target.\n"


@pytest.fixture
def fake_llm():
    """A local OpenAI-compatible endpoint. Yields (base_url, requests_seen, control);
    set control["status"] to make it answer with an error instead."""
    seen, control = [], {"status": 200}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("content-length") or 0)
            seen.append({"path": self.path,
                         "auth": self.headers.get("Authorization"),
                         "body": json.loads(self.rfile.read(n) or b"{}")})
            if control["status"] != 200:
                body = b'{"error": {"message": "nope"}}'
            else:
                body = json.dumps({"choices": [{"message": {"content": REPLY}}]}).encode()
            self.send_response(control["status"])
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}/v1", seen, control
    finally:
        srv.shutdown()
        srv.server_close()


def dotenv(path, url, key="test-key", model="test-model"):
    write(path / ".env", f"OA_REVIEW_API_KEY={key}\nOA_REVIEW_BASE_URL={url}\n"
                         f"OA_REVIEW_MODEL={model}\n")


def reviews(ws):
    return sorted(p.name for p in (ws / "solutions").glob("*.review.md"))


def test_llm_review_prints_the_reply_and_saves_it(ws, fake_llm):
    url, seen, _ = fake_llm
    dotenv(ws, url)
    p = oa(ws, "judge", "--llm", expect=0)
    assert REPLY.strip() in out(p)
    assert "leaves this machine" in out(p)
    assert len(reviews(ws)) == 1
    assert REPLY.strip() in (ws / "solutions" / reviews(ws)[0]).read_text()
    # The review sits beside the solution it is about, sharing its stamp.
    assert reviews(ws)[0] == solutions(ws)[0].replace(".py", ".review.md")
    assert len(seen) == 1


def test_the_review_prompt_carries_readme_solution_and_timings(ws, fake_llm):
    url, seen, _ = fake_llm
    dotenv(ws, url)
    write(ws / "README.md", "# p\n\n## Target\n\nO(n) for n <= 100.\n")
    oa(ws, "judge", "--llm", expect=0)
    sent = seen[0]["body"]["messages"][0]["content"]
    assert "O(n) for n <= 100" in sent          # the README
    assert "def solve(a)" in sent                # the solution that passed
    assert "Scaling" in sent                     # judge's own timing report
    assert seen[0]["auth"] == "Bearer test-key"
    assert seen[0]["path"].endswith("/chat/completions")


def test_a_red_suite_gets_no_review(ws, fake_llm):
    url, seen, _ = fake_llm
    dotenv(ws, url)
    write(ws / "main.py", WRONG)
    p = oa(ws, "judge", "--llm", expect=1)
    assert "only runs on a 100% score" in out(p)
    assert seen == []
    # ...and judge is otherwise exactly what it was: score, and the route to a diff.
    assert "--reveal 1" in out(p)


def test_the_flag_is_the_only_thing_that_reviews(ws, fake_llm):
    url, seen, _ = fake_llm
    dotenv(ws, url)
    oa(ws, "judge", expect=0)
    assert seen == []
    assert reviews(ws) == []


def test_review_reads_the_latest_archived_solution(ws, fake_llm):
    url, seen, _ = fake_llm
    dotenv(ws, url)
    oa(ws, "judge", expect=0)
    oa(ws, "wipe", expect=0)          # entry file is the stub again
    p = oa(ws, "review", expect=0)     # ...and review still has something to talk about
    assert REPLY.strip() in out(p)
    assert "def solve(a)" in seen[0]["body"]["messages"][0]["content"]
    assert len(reviews(ws)) == 1


def test_review_without_an_archived_solution_exits_zero(ws, fake_llm):
    url, _, _ = fake_llm
    dotenv(ws, url)
    assert "nothing to review" in out(oa(ws, "review", expect=0))


def test_the_nearest_env_wins(ws, fake_llm):
    url, seen, _ = fake_llm
    dotenv(ws.parent, "http://127.0.0.1:1/v1", key="parent-key")
    dotenv(ws, url, key="folder-key")
    oa(ws, "judge", "--llm", expect=0)
    assert seen[0]["auth"] == "Bearer folder-key"


def test_the_parent_env_serves_a_folder_without_one(ws, fake_llm):
    url, seen, _ = fake_llm
    dotenv(ws.parent, url, key="bank-key")
    oa(ws, "judge", "--llm", expect=0)
    assert seen[0]["auth"] == "Bearer bank-key"


def test_real_env_vars_work_without_any_dotenv(ws, fake_llm):
    url, seen, _ = fake_llm
    oa(ws, "judge", "--llm", expect=0,
       env={"OA_REVIEW_API_KEY": "env-key", "OA_REVIEW_BASE_URL": url,
            "OA_REVIEW_MODEL": "m"})
    assert seen[0]["auth"] == "Bearer env-key"


# Everything below is a way for the review to fail. None of them may cost a score.

def test_no_key_costs_one_line_not_the_score(ws):
    p = oa(ws, "judge", "--llm", expect=0)
    assert "Score: 9/9 (100%)" in out(p)
    assert "OA_REVIEW_API_KEY" in out(p)
    assert len(solutions(ws)) == 1     # archiving is unaffected


def test_no_key_leaves_review_exiting_zero(ws):
    oa(ws, "judge", expect=0)
    p = oa(ws, "review", expect=0)
    assert "OA_REVIEW_API_KEY" in out(p)
    assert ".env" in out(p)


def test_an_unreachable_endpoint_costs_one_line(ws):
    env = {"OA_REVIEW_API_KEY": "k", "OA_REVIEW_BASE_URL": "http://127.0.0.1:1/v1",
           "OA_REVIEW_MODEL": "m"}
    p = oa(ws, "judge", "--llm", expect=0, env=env)
    assert "Score: 9/9 (100%)" in out(p)
    assert "no review" in out(p)
    assert reviews(ws) == []
    assert out(oa(ws, "review", expect=0, env=env)).count("no review") == 1


def test_a_non_2xx_response_costs_one_line(ws, fake_llm):
    url, _, control = fake_llm
    control["status"] = 500
    dotenv(ws, url)
    p = oa(ws, "judge", "--llm", expect=0)
    assert "Score: 9/9 (100%)" in out(p)
    assert "500" in out(p) and "no review" in out(p)


def test_an_unparseable_env_is_ignored_rather_than_fatal(ws):
    write(ws / ".env", "this is not a key=value file\n\x00\x00\n[section]\n")
    p = oa(ws, "judge", "--llm", expect=0)
    assert "Score: 9/9 (100%)" in out(p)
    assert "OA_REVIEW_API_KEY" in out(p)


def test_a_custom_endpoint_without_a_model_says_so(ws):
    p = oa(ws, "judge", "--llm", expect=0,
           env={"OA_REVIEW_API_KEY": "k", "OA_REVIEW_BASE_URL": "http://127.0.0.1:1/v1"})
    assert "OA_REVIEW_MODEL" in out(p)
    assert "Score: 9/9 (100%)" in out(p)
