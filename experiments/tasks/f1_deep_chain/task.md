# Task: some product prices come back a cent short

## Goal
Prices and money amounts served by the storefront API must exactly match
what was stored. A product priced at $79.99 must be listed, quoted, and
billed at $79.99.

## Current behavior
For certain products the API returns a price one cent lower than the
catalog price. For example, `GET /products/{id}` for the "Aurora Wireless
Earbuds" (list price $79.99) returns `"amount": "79.98"`, and placing an
order for it produces a subtotal of $79.98 and a wrong grand total. Cart
line items snapshot the same wrong price. Most products are unaffected,
which is why this went unnoticed for a while.

`python3 -m pytest tests/ -q` reproduces the problem (5 failures).

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the `storefront/` package. Do not modify the tests.
