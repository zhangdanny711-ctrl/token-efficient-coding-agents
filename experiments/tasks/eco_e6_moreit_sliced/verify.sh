#!/usr/bin/env bash
# Holdout functional check: run the FROZEN test suite against the agent's
# more_itertools/ package. The pristine tests are copied in, so test tampering
# cannot help.
set -u
ws="$1"
here="$(dirname "$0")"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cp -r "$ws/more_itertools" "$tmp/more_itertools"
cp -r "$here/repo/tests" "$tmp/tests"
find "$tmp" \( -name '__pycache__' -o -name '*.pyc' -o -name '.pytest_cache' \) -exec rm -rf {} + 2>/dev/null

cd "$tmp" && python3 -m pytest tests/ -q -p no:cacheprovider
