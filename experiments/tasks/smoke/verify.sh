#!/usr/bin/env bash
# Holdout verification for the smoke task.
# Usage: bash verify.sh <workspace>
set -u
ws="$1"

# Tests must not have been modified (scope rule).
if ! diff -rq -x '__pycache__' -x '*.pyc' "$ws/tests" "$(dirname "$0")/repo/tests" >/dev/null 2>&1; then
    echo "FAIL: tests were modified"
    exit 1
fi

cd "$ws" && python3 -m pytest tests/ -q
