# Task: OrderedMultiDict compares equal to dicts with different values

## Goal
Comparing an `OrderedMultiDict` with a plain `dict` must compare the
values, not just the keys.

## Current behavior
`OMD([('a', 1)]) == {'a': 999}` evaluates to `True` — any mapping with
the same keys is considered equal regardless of its values.

`python3 -m pytest tests/ -q` reproduces the problem (2 failures).

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the `boltons/` package. Do not modify the tests.
