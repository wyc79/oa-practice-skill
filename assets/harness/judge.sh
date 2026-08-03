#!/usr/bin/env sh
# Submit: run every hidden test and print a score. Your "Submit" button.  (Windows: judge.cmd)
cd "$(dirname "$0")" || exit 1

# See run.sh — neither `python3` nor `python` nor `py` is reliably an interpreter, so
# probe by running each, then fall back to the one that scaffolded this workspace.
RECORDED=""
[ -f .oa/python-path ] && RECORDED=$(cat .oa/python-path)

for py in "$OA_PYTHON" python3 python py "$RECORDED"; do
    [ -n "$py" ] || continue
    "$py" -c "import sys; sys.exit(sys.version_info[0] < 3)" >/dev/null 2>&1 \
        && exec "$py" oa.py judge "$@"
done

echo "No working Python 3 found (tried python3, python, py)." >&2
echo "Install Python 3, or set OA_PYTHON to the interpreter's path." >&2
exit 127
