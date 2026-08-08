# Task: premium orders are being rejected by the pipeline

## Goal
The `orders_july` sample job must load every well-formed order. Orders
for the premium SKU `LUX-5001` are well-formed and must be loaded and
totalled like any other order.

## Current behavior
Running the sample job:

```
python3 -m etlkit run samples/orders_july.spec.json
```

completes with `status: DEGRADED`, but the reject count is far higher
than the handful of genuinely dirty rows in the sample data: every
`LUX-5001` order is being rejected as well, so premium revenue is
silently missing from the output file.

`python3 -m pytest tests/ -q` reproduces the problem (3 failures).

## Acceptance
All tests under `tests/` pass. The sample job loads 70 records and
rejects exactly the 5 dirty ones.

## Scope
Fix the `etlkit/` package. Do not modify the tests or the sample data
under `samples/`.
