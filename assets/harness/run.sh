#!/usr/bin/env bash
# Run the sample tests only. This is your "Run Code" button.
cd "$(dirname "$0")" && exec python3 oa.py run "$@"
