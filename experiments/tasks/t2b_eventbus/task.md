# Task: add subscribe_once to the event bus

## Goal
Add a `subscribe_once(event_name, handler)` method: the handler runs for the
next matching publish only, then is automatically removed. The `LoggingBus`
wrapper must expose the same method.

## Current behavior
`pytest tests/ -q`: tests in `tests/test_once.py` fail with AttributeError
(`subscribe_once` does not exist). Tests in `tests/test_bus.py` pass and must
keep passing.

## Acceptance
All tests under `tests/` pass.

## Scope
Modify the `eventbus/` package. Do not modify the tests.
