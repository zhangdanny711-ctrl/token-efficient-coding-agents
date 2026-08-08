"""Acceptance tests for the subscribe_once feature (currently failing)."""

from eventbus import EventBus, LoggingBus


def test_subscribe_once_fires_single_time():
    bus = EventBus()
    seen = []
    bus.subscribe_once("x", seen.append)
    bus.publish("x", 1)
    bus.publish("x", 2)
    assert seen == [1]


def test_subscribe_once_counts_as_handler_on_first_publish():
    bus = EventBus()
    bus.subscribe_once("x", lambda p: None)
    assert bus.publish("x") == 1
    assert bus.publish("x") == 0


def test_subscribe_once_alongside_regular():
    bus = EventBus()
    seen = []
    bus.subscribe("x", lambda p: seen.append(("reg", p)))
    bus.subscribe_once("x", lambda p: seen.append(("once", p)))
    bus.publish("x", 1)
    bus.publish("x", 2)
    assert seen == [("reg", 1), ("once", 1), ("reg", 2)]


def test_logging_bus_exposes_subscribe_once():
    bus = LoggingBus(EventBus())
    seen = []
    bus.subscribe_once("x", seen.append)
    bus.publish("x", 5)
    bus.publish("x", 6)
    assert seen == [5]
    assert bus.log == [("x", 5), ("x", 6)]
