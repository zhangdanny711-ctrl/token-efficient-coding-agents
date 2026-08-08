#!/usr/bin/env bash
# Holdout functional check: run the FROZEN test suite against the agent's
# toolz/ package. The pristine tests are copied in, so test tampering
# cannot help.
set -u
ws="$1"
here="$(dirname "$0")"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cp -r "$ws/toolz" "$tmp/toolz"
rm -rf "$tmp/toolz/tests"
cp -r "$here/holdout/tests" "$tmp/toolz/tests"
cp -r "$here/repo/tlz" "$tmp/tlz"
find "$tmp" \( -name '__pycache__' -o -name '*.pyc' -o -name '.pytest_cache' \) -exec rm -rf {} + 2>/dev/null

cd "$tmp" && python3 -m pytest toolz/tests/ -q -o addopts="" -p no:cacheprovider
