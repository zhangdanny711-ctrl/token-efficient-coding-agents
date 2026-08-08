# Task: SEPARATING_LINE rendered as a data row in padded tables

## Goal
A `SEPARATING_LINE` row must always render as a horizontal rule, for
every table format and any mix of column types.

## Current behavior
In tables where column values get padded (for example a column that
mixes numbers with strings, or plain multi-column data), the separating
line is rendered as if it were an ordinary data row instead of a rule.

`python3 -m pytest test/ -q` reproduces the problem (1 failure).

## Acceptance
All tests under `test/` pass.

## Scope
Fix the `tabulate/` package. Do not modify the tests.
