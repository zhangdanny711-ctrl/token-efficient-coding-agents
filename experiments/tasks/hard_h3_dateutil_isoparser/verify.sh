#!/usr/bin/env bash
# Holdout functional check: run the FROZEN test suite against the agent's
# dateutil/ package. The pristine tests are copied in, so test tampering
# cannot help.
set -u
ws="$1"
here="$(dirname "$0")"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cp -r "$ws/dateutil" "$tmp/dateutil"
rm -rf "$tmp/dateutil/test"
cp -r "$here/holdout/test" "$tmp/dateutil/test"
find "$tmp" \( -name '__pycache__' -o -name '*.pyc' -o -name '.pytest_cache' \) -exec rm -rf {} + 2>/dev/null

cd "$tmp" && python3 -m pytest dateutil/test/ -q -o addopts="" -p no:warnings -p no:cacheprovider
