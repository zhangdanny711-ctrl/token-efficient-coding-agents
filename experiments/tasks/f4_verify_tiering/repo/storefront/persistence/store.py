"""Generic in-memory key/value store used by the persistence layer.

The store is deliberately dumb: it manages named tables of plain-dict
records keyed by string identifiers and enforces only structural
invariants (known table names, unique keys, existing keys on reads and
writes).  All domain knowledge lives in the serializers and
repositories built on top of it.

Records are stored and returned as *shallow copies* so that callers can
mutate the dicts they hold without corrupting the store's internal
state (and vice versa).
"""

from __future__ import annotations

from typing import Any, Dict, List

from storefront.domain.errors import NotFoundError, ValidationError

#: The set of tables the store manages.  Attempting to touch any other
#: table name raises :class:`ValidationError`.
TABLES = (
    "products",
    "customers",
    "carts",
    "orders",
    "payments",
    "shipments",
    "discounts",
    "inventory",
)


class InMemoryStore:
    """A dict-of-dicts storage backend with a table/key/record model.

    Each table maps string keys to plain-dict records.  The store never
    inspects record contents; it is the persistence layer's equivalent
    of a schemaless document database.

    Example::

        store = InMemoryStore()
        store.insert("products", "prod-1", {"name": "Kettle"})
        record = store.get("products", "prod-1")
    """

    def __init__(self) -> None:
        self._tables: Dict[str, Dict[str, Dict[str, Any]]] = {
            name: {} for name in TABLES
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _table(self, table: str) -> Dict[str, Dict[str, Any]]:
        """Return the backing dict for ``table``.

        Raises:
            ValidationError: If ``table`` is not one of :data:`TABLES`.
        """
        try:
            return self._tables[table]
        except KeyError:
            raise ValidationError(
                "Unknown table {table!r}; expected one of: {names}".format(
                    table=table, names=", ".join(TABLES)
                )
            ) from None

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def insert(self, table: str, key: str, record: Dict[str, Any]) -> None:
        """Insert a new record under ``key``.

        Args:
            table: One of :data:`TABLES`.
            key: Unique identifier for the record within the table.
            record: A plain, JSON-safe dict.  A shallow copy is stored.

        Raises:
            ValidationError: If the table is unknown or the key already
                exists in the table.
        """
        rows = self._table(table)
        if key in rows:
            raise ValidationError(
                f"Duplicate key {key!r} in table {table!r}"
            )
        rows[key] = dict(record)

    def get(self, table: str, key: str) -> Dict[str, Any]:
        """Return a shallow copy of the record stored under ``key``.

        Raises:
            ValidationError: If the table is unknown.
            NotFoundError: If no record exists for ``key``.
        """
        rows = self._table(table)
        try:
            return dict(rows[key])
        except KeyError:
            raise NotFoundError(
                f"No record with key {key!r} in table {table!r}"
            ) from None

    def update(self, table: str, key: str, record: Dict[str, Any]) -> None:
        """Replace the record stored under an *existing* ``key``.

        Raises:
            ValidationError: If the table is unknown.
            NotFoundError: If no record exists for ``key``.
        """
        rows = self._table(table)
        if key not in rows:
            raise NotFoundError(
                f"No record with key {key!r} in table {table!r}"
            )
        rows[key] = dict(record)

    def delete(self, table: str, key: str) -> None:
        """Remove the record stored under ``key``.

        Raises:
            ValidationError: If the table is unknown.
            NotFoundError: If no record exists for ``key``.
        """
        rows = self._table(table)
        if key not in rows:
            raise NotFoundError(
                f"No record with key {key!r} in table {table!r}"
            )
        del rows[key]

    # ------------------------------------------------------------------
    # Bulk / introspection operations
    # ------------------------------------------------------------------
    def all(self, table: str) -> List[Dict[str, Any]]:
        """Return shallow copies of every record in ``table``.

        The list is ordered by insertion order (dict ordering), which
        gives deterministic scans for the repository finders.

        Raises:
            ValidationError: If the table is unknown.
        """
        rows = self._table(table)
        return [dict(record) for record in rows.values()]

    def count(self, table: str) -> int:
        """Return the number of records currently stored in ``table``.

        Raises:
            ValidationError: If the table is unknown.
        """
        return len(self._table(table))

    def clear(self) -> None:
        """Remove every record from every table."""
        for rows in self._tables.values():
            rows.clear()
