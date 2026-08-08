# Task: partition_all silently returns corrupt data for sequences with a broken __len__

## Symptom (from a user report)
We pass collection objects to `toolz.partition_all`. One of them had a
buggy `__len__` that misreported its true length, and `partition_all`
silently produced a wrong final chunk — we only noticed because
downstream data was corrupt. No exception was raised anywhere.

## Goal
When the sequence's reported length is inconsistent with its actual
contents, `partition_all` must raise `LookupError` instead of yielding
bad data, so the broken iterable can be found and fixed. Correct
sequences — including iterators that have no `__len__` at all — must
keep behaving exactly as before.

## Acceptance
Verification runs a frozen holdout test suite (NOT included in this
workspace) against your `toolz/` source. It contains the existing
regression tests plus new tests for the behavior described above.
The tests in the workspace do not cover this bug — them passing does
not mean you are done.

## Scope
Fix the `toolz/` package source. Do not modify the tests.
