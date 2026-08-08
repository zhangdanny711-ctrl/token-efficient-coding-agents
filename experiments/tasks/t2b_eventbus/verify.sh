#!/usr/bin/env bash
set -u
ws="$1"
here="$(dirname "$0")"
if ! diff -rq -x '__pycache__' -x '*.pyc' "$ws/tests" "$here/repo/tests" >/dev/null 2>&1; then
    echo "FAIL: tests were modified"
    exit 1
fi
cd "$ws" && python3 -m pytest tests/ -q
