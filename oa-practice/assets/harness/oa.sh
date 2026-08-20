#!/usr/bin/env sh
# Any harness command, with the interpreter probe run.sh/judge.sh use:
#   ./oa.sh gen | answers | selfcheck | case <name> | wipe | run | judge  (Win: oa.cmd)
#
# run.sh and judge.sh are the two buttons; this is everything else, and it exists so
# the authoring steps are not the ones that assume `python3` resolves to a Python 3.
cd "$(dirname "$0")" || exit 1

RECORDED=""
[ -f .oa/python-path ] && RECORDED=$(cat .oa/python-path)

for py in "$OA_PYTHON" python3 python py "$RECORDED"; do
    [ -n "$py" ] || continue
    "$py" -c "import sys; sys.exit(sys.version_info[0] < 3)" >/dev/null 2>&1 \
        && exec "$py" oa.py "$@"
done

echo "No working Python 3 found (tried python3, python, py)." >&2
echo "Install Python 3, or set OA_PYTHON to the interpreter's path." >&2
exit 127
