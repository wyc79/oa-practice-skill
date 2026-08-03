#!/usr/bin/env sh
# Run the sample tests only. This is your "Run Code" button.  (Windows: run.cmd)
cd "$(dirname "$0")" || exit 1

# `python3` is not a safe assumption. Windows ships a python3.exe that only
# advertises the Microsoft Store, macOS has no /usr/bin/python at all since 12.3, and
# `py` may not exist — so probe by actually running each candidate rather than by
# name. .oa/python-path records the interpreter that scaffolded this workspace, which
# is a working Python 3 by construction; PATH is tried first so the folder stays
# portable, and the recorded path is the backstop.
RECORDED=""
[ -f .oa/python-path ] && RECORDED=$(cat .oa/python-path)

for py in "$OA_PYTHON" python3 python py "$RECORDED"; do
    [ -n "$py" ] || continue
    "$py" -c "import sys; sys.exit(sys.version_info[0] < 3)" >/dev/null 2>&1 \
        && exec "$py" oa.py run "$@"
done

echo "No working Python 3 found (tried python3, python, py)." >&2
echo "Install Python 3, or set OA_PYTHON to the interpreter's path." >&2
exit 127
