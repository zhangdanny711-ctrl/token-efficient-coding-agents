"""Injectable clocks.

Library code never calls ``datetime.now()`` directly; callers pass a
clock object so that time is controllable in tests and reproducible in
benchmarks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


class FixedClock:
    """A clock frozen at a fixed instant, advanced only explicitly.

    The instant is parsed once from an ISO-8601 string at construction
    time; subsequent calls to :meth:`now` return the same value until
    :meth:`advance` is called.
    """

    def __init__(self, iso: str) -> None:
        self._now = datetime.fromisoformat(iso)

    def now(self) -> datetime:
        """Return the current (fixed) instant."""
        return self._now

    def advance(self, seconds: int) -> None:
        """Move the clock forward by ``seconds`` seconds."""
        self._now = self._now + timedelta(seconds=seconds)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"FixedClock({self._now.isoformat()!r})"


class SystemClock:
    """A clock backed by the real system time (UTC)."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(timezone.utc)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "SystemClock()"
