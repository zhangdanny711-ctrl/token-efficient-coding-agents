# Task: ISO 8601 parser: wrong day for 24:00 midnight, and invalid time strings accepted

## Symptoms (from user reports)
Two defects in `dateutil.parser.isoparse` / `isoparser`:

1. The ISO 8601 standard allows hour 24 to denote midnight at the END
   of a day. Datetimes written with `24:00` currently come out on the
   wrong calendar day.

2. Time strings that mix separated and unseparated components — using
   the `:` separator between some time components but omitting it
   between others — are invalid ISO 8601, but the parser currently
   accepts some of them silently and returns a wrong time. Fully
   separated and fully compact time forms are both valid and must keep
   parsing exactly as before.

## Goal
Fix both defects. Valid inputs must keep parsing exactly as before —
there is a large existing regression suite.

## Acceptance
Verification runs a frozen holdout test suite (NOT included in this
workspace) against your `dateutil/` source. It contains the existing
regression tests plus enabled tests for BOTH defects. The workspace
tests do not fully cover these bugs — them passing does not mean you
are done.

## Scope
Fix the `dateutil/` package source. Do not modify the tests.
