# etlkit

A small batch data-pipeline toolkit in pure Python (standard library
only). A *job* is described by a JSON spec and executed as a fixed
chain of stages; every intermediate result is a plain dict, so the
whole pipeline can be inspected, logged, and tested without framework
machinery.

## Running a job

```
python3 -m etlkit run samples/orders_july.spec.json
python3 -m etlkit check samples/orders_july.spec.json   # validate spec only
```

Exit code 0 means the run finished (status `OK` or `DEGRADED`);
exit code 2 means it failed (`FAILED`).

## Pipeline architecture

```
extract -> validate -> transform -> load
                                      \-> cleanup -> report
```

- **extract** (`etlkit/stages/extract.py`) reads the source file into
  a fresh batch. CSV headers are normalized to snake_case.
- **validate** (`stages/validate.py`) applies the spec's `checks`
  (rules in `etlkit/rules.py`). Failing records go to the reject pile;
  the run continues.
- **transform** (`stages/transform.py`) applies the spec's `ops`
  (`etlkit/ops.py`) in order to each surviving record.
- **load** (`stages/load.py`) enforces the reject-rate guard, then
  writes survivors to the target and rejects to the reject file.
- **cleanup** (`etlkit/cleanup.py`) sweeps stale work files; advisory
  only, never fails a run.
- **report** (`etlkit/report.py`) prints the fixed-format summary
  block that CI greps, ending with `status: OK|DEGRADED|FAILED`.

Stages hand data to each other through the *batch contract*
(`etlkit/contracts.py`): a plain dict with `job`, `stage`, `records`,
`rejects`, and `meta` keys. `ensure_batch` fails loudly on a malformed
hand-off.

## Error model

Per-record problems (`RecordError`, `CheckFailure`) become reject
entries and the run finishes `DEGRADED`. Fatal problems (`SpecError`,
`ExtractError`, `LoadError`, contract violations) abort the stage
chain, but cleanup and the report still run, so the log always ends
with the same summary block.

## Module inventory

- `etlkit/__main__.py` — CLI (`run`, `check`)
- `etlkit/runner.py` — orchestrates the stage chain
- `etlkit/spec.py` — spec loading and structural validation
- `etlkit/contracts.py` — the batch contract
- `etlkit/rules.py` — validation rules (`required`, `type`, `range`,
  `one_of`, `unique`, `matches`)
- `etlkit/ops.py` — transform ops (`cast`, `rename`, `default`,
  `drop`, `derive`)
- `etlkit/stages/` — one module per stage
- `etlkit/io/` — CSV/JSONL readers and writers
- `etlkit/cleanup.py`, `etlkit/report.py` — post-run phases
- `etlkit/utils/` — logging, text, and number helpers

## Logging

Run logs are deterministic (see `etlkit/utils/log.py`): no wall-clock
timestamps, just a simulated elapsed-time tick, so identical inputs
produce byte-identical logs that CI can diff. With `options.verbose`
(the default) every record gets a DEBUG line per stage, which makes
run logs long but replayable.

## Tests

```
python3 -m pytest tests/ -q
```

Pure stdlib; only pytest itself is required.
