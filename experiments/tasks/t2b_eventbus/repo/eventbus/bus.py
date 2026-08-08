"""A minimal synchronous event bus."""


class EventBus:
    def __init__(self):
        self._handlers = {}  # event_name -> list of callables

    def subscribe(self, event_name, handler):
        self._handlers.setdefault(event_name, []).append(handler)

    def unsubscribe(self, event_name, handler):
        handlers = self._handlers.get(event_name, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event_name, payload=None):
        """Call every handler subscribed to event_name. Returns handler count."""
        handlers = list(self._handlers.get(event_name, []))
        for h in handlers:
            h(payload)
        return len(handlers)
