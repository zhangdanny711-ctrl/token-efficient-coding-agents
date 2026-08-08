# Task: len() crashes on a freshly created database

## Goal
`len(TinyDB(...))` must return 0 for a brand-new (empty) database.

## Current behavior
Calling `len()` on a database whose storage has never been written
raises `TypeError: 'NoneType' object is not subscriptable`.

`python3 -m pytest tests/ -q -o addopts=""` reproduces the problem (1 failure).

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the `tinydb/` package. Do not modify the tests.
