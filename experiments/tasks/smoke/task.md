# Task: fix failing test in textstats

## Goal
`average_word_length` should return the mean length of whitespace-separated
words. Currently one unit test fails.

## Current behavior
```
pytest tests/ -q
```
reports `test_average_word_length_simple` failing:
expected 2.0, got 1.0 for the input "ab cd".

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the bug in the library code. Do not modify the tests.
