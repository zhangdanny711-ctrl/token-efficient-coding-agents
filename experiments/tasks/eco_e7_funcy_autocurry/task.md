# Task: @autocurry loses the decorated function's metadata

## Goal
Functions decorated with `@autocurry` must keep their `__name__`,
`__doc__` and other metadata, like well-behaved decorators do.

## Current behavior
After decorating a function with `@autocurry`, its `__doc__` is `None`
and its name is lost, which breaks `help()` and introspection.

`python3 -m pytest tests/ -q` reproduces the problem (1 failure).

## Acceptance
All tests under `tests/` pass.

## Scope
Fix the `funcy/` package. Do not modify the tests.
