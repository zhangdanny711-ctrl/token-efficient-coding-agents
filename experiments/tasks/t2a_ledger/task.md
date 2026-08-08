# Task: fix ledger aggregation bugs

## Goal
1. `by_month(transactions, year, month)` must select transactions whose date
   falls in the given calendar month.
2. `totals_by_category(transactions, currency)` must only sum transactions in
   the given currency.

## Current behavior
`pytest tests/ -q` shows multiple failures: month filtering matches the wrong
transactions, and category totals mix currencies together.

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the library code (the `ledger/` package). Do not modify the tests.
