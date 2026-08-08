# Task: premium orders are rejected by the sample job

## Goal
The `orders_july` sample job must load every well-formed order. Orders
for the premium SKU `LUX-5001` are well-formed and must be loaded and
totalled like any other order.

## Current behavior
Running the sample job:

```
python3 -m etlkit run samples/orders_july.spec.json
```

completes with `status: DEGRADED` and only 61 records loaded: every
`LUX-5001` order is being rejected, so premium revenue is silently
missing from the output file.

`python3 -m pytest tests/ -q` reproduces the problem (4 failures).

## Acceptance
All tests under `tests/` pass. The sample job loads 70 records and
rejects exactly the 5 genuinely dirty ones.

## Scope
Fix the `etlkit/` package. Do not modify the tests or the sample data
under `samples/`.
