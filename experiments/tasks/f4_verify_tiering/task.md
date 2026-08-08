# Task: tax and discount amounts come out a cent low

## Goal
Percentage calculations on money (tax, percentage discounts) must round
half-up to the nearest cent, as the pricing documentation promises.
7.25% of $20.68 is $1.4993, which must round to $1.50 — not $1.49.

## Current behavior
Several tax and discount amounts are one cent lower than expected.
For example the NY tax (8.875%) on a $79.99 item comes out as $7.09
instead of $7.10, and a 5% discount on $2.50 shows $0.12 instead of
$0.13.

Running the test suite:

```
python3 -m pytest tests/
```

reproduces the problem (7 failures).

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the `storefront/` package. Do not modify the tests.
