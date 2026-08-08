"""Entity-oriented repositories layered on top of :class:`InMemoryStore`.

Each repository binds one domain entity to one store table via the
explicit serializer pair from :mod:`storefront.persistence.serializers`.
The base :class:`Repository` implements the generic CRUD surface; the
concrete subclasses add domain-specific finders that scan the table and
deserialize records back into entities.

Finder methods deliberately deserialize before filtering rather than
poking at raw records, so all schema knowledge stays inside the
serializer module.  For an in-memory store the extra work is trivial,
and it means a change to the record layout can never silently break a
finder.

Inventory levels are not a domain entity; they are handled by the
lightweight :class:`InventoryRecords` accessor at the bottom of this
module, which works directly with plain dict records.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, TypeVar

from storefront.domain.errors import NotFoundError
from storefront.domain.models import (
    Cart,
    Customer,
    Discount,
    Order,
    Payment,
    Product,
    Shipment,
)
from storefront.persistence.serializers import (
    deserialize_cart,
    deserialize_customer,
    deserialize_discount,
    deserialize_order,
    deserialize_payment,
    deserialize_product,
    deserialize_shipment,
    serialize_cart,
    serialize_customer,
    serialize_discount,
    serialize_order,
    serialize_payment,
    serialize_product,
    serialize_shipment,
)
from storefront.persistence.store import InMemoryStore

E = TypeVar("E")


class Repository(Generic[E]):
    """Generic CRUD data-access object for one entity type.

    Args:
        store: The backing :class:`InMemoryStore`.
        table: The store table this repository owns.
        serialize_fn: Converts an entity into its stored record.
        deserialize_fn: Converts a stored record back into an entity.
        key_attr: Name of the entity attribute used as the storage key
            (for example ``"product_id"`` or ``"code"``).
    """

    def __init__(
        self,
        store: InMemoryStore,
        table: str,
        serialize_fn: Callable[[E], Dict[str, Any]],
        deserialize_fn: Callable[[Dict[str, Any]], E],
        key_attr: str,
    ) -> None:
        self._store = store
        self._table = table
        self._serialize = serialize_fn
        self._deserialize = deserialize_fn
        self._key_attr = key_attr

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _key_of(self, entity: E) -> str:
        """Return the storage key for ``entity`` via ``key_attr``."""
        return getattr(entity, self._key_attr)

    def _scan(self) -> List[E]:
        """Deserialize every record in the table, in insertion order."""
        return [self._deserialize(record) for record in self._store.all(self._table)]

    # ------------------------------------------------------------------
    # CRUD surface
    # ------------------------------------------------------------------
    def add(self, entity: E) -> None:
        """Persist a new entity.

        Raises:
            ValidationError: If an entity with the same key already
                exists in the table.
        """
        self._store.insert(self._table, self._key_of(entity), self._serialize(entity))

    def get(self, key: str) -> E:
        """Load the entity stored under ``key``.

        Raises:
            NotFoundError: If no entity exists for ``key``.
        """
        return self._deserialize(self._store.get(self._table, key))

    def update(self, entity: E) -> None:
        """Replace the stored copy of an existing entity.

        Raises:
            NotFoundError: If the entity has never been added.
        """
        self._store.update(self._table, self._key_of(entity), self._serialize(entity))

    def delete(self, key: str) -> None:
        """Remove the entity stored under ``key``.

        Raises:
            NotFoundError: If no entity exists for ``key``.
        """
        self._store.delete(self._table, key)

    def list(self) -> List[E]:
        """Return every entity in the table, in insertion order."""
        return self._scan()

    def exists(self, key: str) -> bool:
        """Return ``True`` if an entity is stored under ``key``."""
        try:
            self._store.get(self._table, key)
        except NotFoundError:
            return False
        return True


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

class ProductRepository(Repository[Product]):
    """Repository for :class:`Product` entities, keyed by ``product_id``."""

    def __init__(self, store: InMemoryStore) -> None:
        super().__init__(
            store=store,
            table="products",
            serialize_fn=serialize_product,
            deserialize_fn=deserialize_product,
            key_attr="product_id",
        )

    def find_by_sku(self, sku: str) -> Product:
        """Return the product with the given SKU.

        SKUs are unique in practice, so the first match wins.

        Raises:
            NotFoundError: If no product carries ``sku``.
        """
        for product in self._scan():
            if product.sku == sku:
                return product
        raise NotFoundError(f"No product with sku {sku!r}")

    def list_by_category(self, category: str) -> List[Product]:
        """Return every product in ``category``, in insertion order."""
        return [
            product for product in self._scan() if product.category == category
        ]

    def list_active(self) -> List[Product]:
        """Return every product currently available for sale."""
        return [product for product in self._scan() if product.active]

    def search_name(self, term: str) -> List[Product]:
        """Return products whose name contains ``term``, case-insensitively.

        A simple substring scan; adequate for the in-memory catalog
        sizes this store is designed for.
        """
        needle = term.lower()
        return [
            product for product in self._scan() if needle in product.name.lower()
        ]


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

class CustomerRepository(Repository[Customer]):
    """Repository for :class:`Customer` entities, keyed by ``customer_id``."""

    def __init__(self, store: InMemoryStore) -> None:
        super().__init__(
            store=store,
            table="customers",
            serialize_fn=serialize_customer,
            deserialize_fn=deserialize_customer,
            key_attr="customer_id",
        )

    def find_by_email(self, email: str) -> Customer:
        """Return the customer registered under ``email``.

        Email comparison is case-insensitive, matching how addresses
        are treated at sign-in.

        Raises:
            NotFoundError: If no customer uses ``email``.
        """
        normalized = email.lower()
        for customer in self._scan():
            if customer.email.lower() == normalized:
                return customer
        raise NotFoundError(f"No customer with email {email!r}")

    def list_by_tier(self, tier: str) -> List[Customer]:
        """Return every customer in the given loyalty tier."""
        return [
            customer for customer in self._scan() if customer.loyalty_tier == tier
        ]


# ---------------------------------------------------------------------------
# Carts
# ---------------------------------------------------------------------------

class CartRepository(Repository[Cart]):
    """Repository for :class:`Cart` entities, keyed by ``cart_id``."""

    def __init__(self, store: InMemoryStore) -> None:
        super().__init__(
            store=store,
            table="carts",
            serialize_fn=serialize_cart,
            deserialize_fn=deserialize_cart,
            key_attr="cart_id",
        )

    def list_by_customer(self, customer_id: str) -> List[Cart]:
        """Return every cart belonging to ``customer_id``.

        A customer normally has at most one open cart, but abandoned
        carts are retained, so this may return several.
        """
        return [
            cart for cart in self._scan() if cart.customer_id == customer_id
        ]


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

class OrderRepository(Repository[Order]):
    """Repository for :class:`Order` entities, keyed by ``order_id``."""

    def __init__(self, store: InMemoryStore) -> None:
        super().__init__(
            store=store,
            table="orders",
            serialize_fn=serialize_order,
            deserialize_fn=deserialize_order,
            key_attr="order_id",
        )

    def list_by_customer(self, customer_id: str) -> List[Order]:
        """Return every order placed by ``customer_id``."""
        return [
            order for order in self._scan() if order.customer_id == customer_id
        ]

    def list_by_status(self, status: str) -> List[Order]:
        """Return every order currently in ``status``.

        Useful for fulfilment queues, e.g. all ``"paid"`` orders that
        still need a shipment.
        """
        return [order for order in self._scan() if order.status == status]

    def placed_between(self, start: datetime, end: datetime) -> List[Order]:
        """Return orders placed within ``[start, end]``, inclusive.

        Args:
            start: Earliest ``placed_at`` timestamp to include.
            end: Latest ``placed_at`` timestamp to include.
        """
        return [
            order for order in self._scan() if start <= order.placed_at <= end
        ]


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

class PaymentRepository(Repository[Payment]):
    """Repository for :class:`Payment` entities, keyed by ``payment_id``."""

    def __init__(self, store: InMemoryStore) -> None:
        super().__init__(
            store=store,
            table="payments",
            serialize_fn=serialize_payment,
            deserialize_fn=deserialize_payment,
            key_attr="payment_id",
        )

    def list_by_order(self, order_id: str) -> List[Payment]:
        """Return every payment attempt recorded against ``order_id``.

        Includes failed and refunded attempts; callers filter by
        ``status`` when they need only the successful capture.
        """
        return [
            payment for payment in self._scan() if payment.order_id == order_id
        ]


# ---------------------------------------------------------------------------
# Shipments
# ---------------------------------------------------------------------------

class ShipmentRepository(Repository[Shipment]):
    """Repository for :class:`Shipment` entities, keyed by ``shipment_id``."""

    def __init__(self, store: InMemoryStore) -> None:
        super().__init__(
            store=store,
            table="shipments",
            serialize_fn=serialize_shipment,
            deserialize_fn=deserialize_shipment,
            key_attr="shipment_id",
        )

    def list_by_order(self, order_id: str) -> List[Shipment]:
        """Return every shipment created for ``order_id``.

        Orders that were split across boxes will have multiple
        shipments, each with its own carrier tracking code.
        """
        return [
            shipment for shipment in self._scan() if shipment.order_id == order_id
        ]


# ---------------------------------------------------------------------------
# Discounts
# ---------------------------------------------------------------------------

class DiscountRepository(Repository[Discount]):
    """Repository for :class:`Discount` entities, keyed by ``code``.

    Discount codes are their own natural primary key, so ``key_attr``
    is ``"code"`` rather than a synthetic identifier.
    """

    def __init__(self, store: InMemoryStore) -> None:
        super().__init__(
            store=store,
            table="discounts",
            serialize_fn=serialize_discount,
            deserialize_fn=deserialize_discount,
            key_attr="code",
        )

    def find_by_code(self, code: str) -> Discount:
        """Return the discount registered under ``code``.

        Raises:
            NotFoundError: If no discount uses ``code``.
        """
        return self.get(code)

    def list_active(self) -> List[Discount]:
        """Return every discount currently eligible for redemption."""
        return [discount for discount in self._scan() if discount.active]


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

class InventoryRecords:
    """Accessor for stock-level records in the ``inventory`` table.

    Inventory is operational state rather than a domain entity, so it
    bypasses the serializer layer and works with plain dict records of
    the form::

        {
            "product_id": str,
            "available":  int,  # units on hand and sellable
            "reserved":   int,  # units held for unpaid orders
        }
    """

    TABLE = "inventory"

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def get_level(self, product_id: str) -> Dict[str, Any]:
        """Return the stock-level record for ``product_id``.

        Raises:
            NotFoundError: If no inventory level has been set for the
                product.
        """
        return self._store.get(self.TABLE, product_id)

    def set_level(self, product_id: str, available: int, reserved: int = 0) -> None:
        """Create or replace the stock-level record for ``product_id``.

        Args:
            product_id: The product whose stock is being set.
            available: Units on hand and sellable.
            reserved: Units held against unpaid orders. Defaults to 0.
        """
        record = {
            "product_id": product_id,
            "available": available,
            "reserved": reserved,
        }
        try:
            self._store.get(self.TABLE, product_id)
        except NotFoundError:
            self._store.insert(self.TABLE, product_id, record)
        else:
            self._store.update(self.TABLE, product_id, record)

    def update_level(
        self,
        product_id: str,
        available: int | None = None,
        reserved: int | None = None,
    ) -> Dict[str, Any]:
        """Partially update the stock-level record for ``product_id``.

        Only the fields passed as non-``None`` are changed; the rest of
        the record is preserved.  Returns the updated record.

        Raises:
            NotFoundError: If no inventory level exists for the product.
        """
        record = self._store.get(self.TABLE, product_id)
        if available is not None:
            record["available"] = available
        if reserved is not None:
            record["reserved"] = reserved
        self._store.update(self.TABLE, product_id, record)
        return record
