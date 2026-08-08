"""Deterministic identifier generation.

Identifiers are produced by :class:`IdSequence` objects that emit
monotonically increasing, zero-padded ids such as ``"ord-000001"``.
Sequences are plain objects (no global state) so tests and services can
inject fresh, predictable generators.
"""

from __future__ import annotations


class IdSequence:
    """A monotonically increasing id generator with a fixed prefix.

    Each call to :meth:`next` returns a string of the form
    ``"<prefix>-<six digit zero-padded counter>"`` and advances the
    counter by one.
    """

    def __init__(self, prefix: str, start: int = 1) -> None:
        if not prefix:
            raise ValueError("prefix must be a non-empty string")
        if start < 0:
            raise ValueError("start must be non-negative")
        self.prefix = prefix
        self._start = start
        self._counter = start

    def next(self) -> str:
        """Return the next id in the sequence, e.g. ``"ord-000001"``."""
        value = f"{self.prefix}-{self._counter:06d}"
        self._counter += 1
        return value

    def peek(self) -> str:
        """Return the id that the next call to :meth:`next` would produce."""
        return f"{self.prefix}-{self._counter:06d}"

    def reset(self) -> None:
        """Rewind the sequence back to its starting counter."""
        self._counter = self._start

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"IdSequence(prefix={self.prefix!r}, next={self._counter})"


def make_sequences() -> dict[str, IdSequence]:
    """Build the standard set of id sequences used across the storefront.

    Returns a mapping from entity name to a fresh :class:`IdSequence`.
    """
    return {
        "product": IdSequence("prd"),
        "customer": IdSequence("cus"),
        "cart": IdSequence("crt"),
        "order": IdSequence("ord"),
        "payment": IdSequence("pay"),
        "shipment": IdSequence("shp"),
    }
