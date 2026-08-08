"""Middleware helpers that wrap an EventBus."""


class LoggingBus:
    """Wraps a bus and records every published event."""

    def __init__(self, bus):
        self._bus = bus
        self.log = []  # list of (event_name, payload)

    def subscribe(self, event_name, handler):
        self._bus.subscribe(event_name, handler)

    def unsubscribe(self, event_name, handler):
        self._bus.unsubscribe(event_name, handler)

    def publish(self, event_name, payload=None):
        self.log.append((event_name, payload))
        return self._bus.publish(event_name, payload)
