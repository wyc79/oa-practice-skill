#!/usr/bin/env bash
# Submit: run every hidden test and print a score. This is your "Submit" button.
cd "$(dirname "$0")" && exec python3 oa.py judge "$@"
