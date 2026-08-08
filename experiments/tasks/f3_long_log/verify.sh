#!/usr/bin/env bash
# Holdout functional check: run the FROZEN test suite and FROZEN sample
# data against the agent's etlkit/ package. Only etlkit/ is taken from
# the workspace, so tampering with tests/ or samples/ cannot help.
set -u
ws="$1"
here="$(dirname "$0")"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cp -r "$ws/etlkit" "$tmp/etlkit"
cp -r "$here/repo/tests" "$tmp/tests"
cp -r "$here/repo/samples" "$tmp/samples"
cp "$here/repo/pytest.ini" "$tmp/pytest.ini"
find "$tmp" \( -name '__pycache__' -o -name '*.pyc' -o -name '.pytest_cache' \) -exec rm -rf {} + 2>/dev/null

cd "$tmp" && python3 -m pytest tests/ -q
