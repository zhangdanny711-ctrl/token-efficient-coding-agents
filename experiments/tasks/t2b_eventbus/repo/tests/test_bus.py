from eventbus import EventBus, LoggingBus


def test_publish_calls_handlers():
    bus = EventBus()
    seen = []
    bus.subscribe("x", seen.append)
    n = bus.publish("x", 42)
    assert n == 1
    assert seen == [42]


def test_unsubscribe():
    bus = EventBus()
    seen = []
    bus.subscribe("x", seen.append)
    bus.unsubscribe("x", seen.append)
    # note: bound method identity differs; unsubscribe with same object
    bus2 = EventBus()
    handler = seen.append
    bus2.subscribe("y", handler)
    bus2.unsubscribe("y", handler)
    assert bus2.publish("y", 1) == 0


def test_logging_bus_records():
    bus = LoggingBus(EventBus())
    bus.publish("a", 1)
    bus.publish("b", None)
    assert bus.log == [("a", 1), ("b", None)]
