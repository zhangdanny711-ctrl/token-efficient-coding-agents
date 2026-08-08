# Task: fix date_range off-by-one

## Goal
`date_range(start, end)` must return every date from start to end **inclusive**.

## Current behavior
`pytest tests/ -q` shows failures: the returned range stops one day short
(e.g. `date_range(2026-01-01, 2026-01-03)` is missing 2026-01-03).

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the library code. Do not modify the tests.
