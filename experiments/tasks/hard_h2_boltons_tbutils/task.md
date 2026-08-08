# Task: parsing truncated tracebacks crashes with IndexError

## Symptom (from a user report)
We use `boltons.tbutils.ParsedException.from_string()` to parse Python
tracebacks scraped from log files. Log lines are often cut off mid-way
(rotation, buffering), so the traceback text can end early — sometimes
before the final exception line. On some of these truncated inputs
`from_string` raises `IndexError` instead of returning a result.

## Goal
`ParsedException.from_string()` must never crash on a traceback that is
merely truncated: it should parse the frames that are present and
return a ParsedException; whatever is missing (e.g. the trailing
exception type/message line) is represented as empty strings. Parsing
of complete, well-formed tracebacks (including ones with caret/anchor
underline lines) must keep working exactly as before.

## Acceptance
Verification runs a frozen holdout test suite (NOT included in this
workspace) against your `boltons/` source. It contains the existing
regression tests plus new tests for the behavior described above.
The tests in the workspace do not cover this bug — them passing does
not mean you are done. Make sure ALL the ways a traceback can be cut
off are handled.

## Scope
Fix the `boltons/` package. Do not modify the tests.
