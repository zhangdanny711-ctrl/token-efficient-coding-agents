# Task: partial config overrides crash report generation

## Goal
`generate_report(rows, user_config)` must accept partial user configs: any
option the user does not specify keeps its default value.

## Current behavior
Passing a partial override crashes or misbehaves. For example
`generate_report(rows, {"format": {"decimals": 0}})` raises
`KeyError: 'thousands_sep'` inside the renderer, and
`generate_report(rows, {"sections": {"details": False}})` raises
`KeyError: 'summary'`. Full configs and the no-config path work fine.
`pytest tests/ -q` reproduces the failures.

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the `reportgen/` package. Do not modify the tests.
