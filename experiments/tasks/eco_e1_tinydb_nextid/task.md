# Task: documents silently overwritten after reopening a database

## Goal
Inserting documents into a TinyDB database that already contains data
(e.g. after closing and reopening a JSON file) must assign fresh,
consecutive document IDs to each insert.

## Current behavior
Create a database with one document, close it, reopen the same file and
insert two more documents: both inserts are assigned the SAME document
ID, so the second insert silently overwrites the first — the database
ends up with 2 documents instead of 3 and data is lost.

`python3 -m pytest tests/ -q -o addopts=""` reproduces the problem (1 failure).

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the `tinydb/` package. Do not modify the tests.
