# Task: sliced() silently returns wrong data for a negative slice size

## Goal
`sliced(seq, n)` must reject invalid (negative) values of `n` with a
`ValueError` instead of silently yielding truncated data.

## Current behavior
`list(sliced('ABCDEFG', -1))` returns `['ABCDEF']` — no error, just a
silently wrong result. With `strict=True` it raises a misleading
"not divisible" error instead.

`python3 -m pytest tests/ -q` reproduces the problem (1 failure).

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the `more_itertools/` package. Do not modify the tests.
