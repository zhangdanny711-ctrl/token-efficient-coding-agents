# Task: fix slugify separator collapsing

## Goal
`slugify` must collapse any run of non-alphanumeric characters into a single
hyphen (e.g. `"a  --  b"` -> `"a-b"`).

## Current behavior
`pytest tests/ -q` shows failures: consecutive separator characters produce
multiple hyphens (e.g. `"Hello, World!"` becomes `"hello--world"`).

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the library code. Do not modify the tests.
