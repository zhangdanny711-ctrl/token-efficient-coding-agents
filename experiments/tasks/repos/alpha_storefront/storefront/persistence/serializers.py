"""Explicit converters between domain entities and stored records.

Every entity in :mod:`storefront.domain.models` has a matching pair of
functions here:

* ``serialize_<entity>(entity) -> dict`` produces a JSON-safe record.
* ``deserialize_<entity>(record) -> entity`` reconstructs the entity.

Round-tripping is lossless: for any entity ``e``,
``deserialize_x(serialize_x(e)) == e``.

Storage conventions
-------------------
* :class:`~storefront.domain.money.Money` values are stored as nested
  dicts of the form ``{"amount": "<decimal string>", "currency": "USD"}``
  so that records remain currency-aware and human-readable while
  avoiding any float representation.
* :class:`~datetime.datetime` values are stored as ISO-8601 strings via
  :meth:`datetime.isoformat` and parsed back with
  :meth:`datetime.fromisoformat`.
* Nested entities (addresses on a customer, items on a cart, lines on
  an order) are stored as lists of their own record form, recursively
  using the functions in this module.

Each field is mapped explicitly rather than through ``dataclasses.asdict``
loops.  That keeps the record schema a deliberate, reviewable contract:
renaming a dataclass field cannot silently change the storage format.

The module also exposes :data:`RECORD_SCHEMAS`, the required-key sets
for each record type, and :func:`validate_record`, which raises
:class:`~storefront.domain.errors.ValidationError` when keys are missing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from storefront.domain.errors import ValidationError
from storefront.domain.models import (
    Address,
    Cart,
    CartItem,
    Customer,
    Discount,
    Order,
    OrderLine,
    Payment,
    Product,
    Shipment,
)
from storefront.domain.money import Money

Record = Dict[str, Any]


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------

def money_to_record(m: Money) -> Record:
    """Convert a :class:`Money` value into its stored record form.

    Record schema::

        {
            "amount":   str,  # decimal string, e.g. "12.34"
            "currency": str,  # ISO currency code, e.g. "USD"
        }

    The amount is rendered with :meth:`Money.to_decimal_string` so the
    record never contains binary floating point values.
    """
    return {
        "amount": m.to_decimal_string(),
        "currency": m.currency,
    }


def money_from_record(rec: Record) -> Money:
    """Reconstruct a :class:`Money` value from its stored record form.

    Expects the schema produced by :func:`money_to_record`.  The amount
    string is parsed with :meth:`Money.from_decimal_string`, then the
    currency is applied on top of the parsed value.
    """
    parsed = Money.from_decimal_string(rec["amount"])
    return Money(cents=parsed.cents, currency=rec["currency"])


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------

def datetime_to_record(value: datetime) -> str:
    """Render a :class:`datetime` as an ISO-8601 string for storage."""
    return value.isoformat()


def datetime_from_record(value: str) -> datetime:
    """Parse an ISO-8601 string produced by :func:`datetime_to_record`."""
    return datetime.fromisoformat(value)


# ---------------------------------------------------------------------------
# Address
# ---------------------------------------------------------------------------

def serialize_address(address: Address) -> Record:
    """Convert an :class:`Address` into its stored record form.

    Record schema::

        {
            "street":      str,
            "city":        str,
            "state":       str,
            "postal_code": str,
            "country":     str,
        }
    """
    return {
        "street": address.street,
        "city": address.city,
        "state": address.state,
        "postal_code": address.postal_code,
        "country": address.country,
    }


def deserialize_address(record: Record) -> Address:
    """Reconstruct an :class:`Address` from its stored record form.

    Expects the schema produced by :func:`serialize_address`.
    """
    return Address(
        street=record["street"],
        city=record["city"],
        state=record["state"],
        postal_code=record["postal_code"],
        country=record["country"],
    )


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

def serialize_product(product: Product) -> Record:
    """Convert a :class:`Product` into its stored record form.

    Record schema::

        {
            "product_id":   str,
            "sku":          str,
            "name":         str,
            "description":  str,
            "price":        dict,       # see money_to_record
            "category":     str,
            "tags":         list[str],
            "weight_grams": int,
            "active":       bool,
        }

    Tags are copied into a fresh list so mutating the record cannot
    alias the entity's tag list.
    """
    return {
        "product_id": product.product_id,
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "price": money_to_record(product.price),
        "category": product.category,
        "tags": list(product.tags),
        "weight_grams": product.weight_grams,
        "active": product.active,
    }


def deserialize_product(record: Record) -> Product:
    """Reconstruct a :class:`Product` from its stored record form.

    Expects the schema produced by :func:`serialize_product`.
    """
    return Product(
        product_id=record["product_id"],
        sku=record["sku"],
        name=record["name"],
        description=record["description"],
        price=money_from_record(record["price"]),
        category=record["category"],
        tags=list(record["tags"]),
        weight_grams=record["weight_grams"],
        active=record["active"],
    )


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

def serialize_customer(customer: Customer) -> Record:
    """Convert a :class:`Customer` into its stored record form.

    Record schema::

        {
            "customer_id":  str,
            "email":        str,
            "name":         str,
            "loyalty_tier": str,
            "addresses":    list[dict],  # see serialize_address
        }

    Each address is serialized in place with :func:`serialize_address`;
    the customer record therefore embeds its addresses rather than
    referencing a separate table.
    """
    return {
        "customer_id": customer.customer_id,
        "email": customer.email,
        "name": customer.name,
        "loyalty_tier": customer.loyalty_tier,
        "addresses": [
            serialize_address(address) for address in customer.addresses
        ],
    }


def deserialize_customer(record: Record) -> Customer:
    """Reconstruct a :class:`Customer` from its stored record form.

    Expects the schema produced by :func:`serialize_customer`.  Nested
    address records are rebuilt with :func:`deserialize_address`.
    """
    return Customer(
        customer_id=record["customer_id"],
        email=record["email"],
        name=record["name"],
        loyalty_tier=record["loyalty_tier"],
        addresses=[
            deserialize_address(address_record)
            for address_record in record["addresses"]
        ],
    )


# ---------------------------------------------------------------------------
# CartItem
# ---------------------------------------------------------------------------

def serialize_cart_item(item: CartItem) -> Record:
    """Convert a :class:`CartItem` into its stored record form.

    Record schema::

        {
            "product_id": str,
            "quantity":   int,
            "unit_price": dict,  # see money_to_record
        }

    The unit price is captured at the moment the item was added so cart
    contents remain stable when catalog prices change.
    """
    return {
        "product_id": item.product_id,
        "quantity": item.quantity,
        "unit_price": money_to_record(item.unit_price),
    }


def deserialize_cart_item(record: Record) -> CartItem:
    """Reconstruct a :class:`CartItem` from its stored record form.

    Expects the schema produced by :func:`serialize_cart_item`.
    """
    return CartItem(
        product_id=record["product_id"],
        quantity=record["quantity"],
        unit_price=money_from_record(record["unit_price"]),
    )


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

def serialize_cart(cart: Cart) -> Record:
    """Convert a :class:`Cart` into its stored record form.

    Record schema::

        {
            "cart_id":     str,
            "customer_id": str,
            "items":       list[dict],  # see serialize_cart_item
            "created_at":  str,         # ISO-8601 datetime
        }

    Items are embedded in the cart record in order, preserving the
    sequence in which the customer added them.
    """
    return {
        "cart_id": cart.cart_id,
        "customer_id": cart.customer_id,
        "items": [serialize_cart_item(item) for item in cart.items],
        "created_at": datetime_to_record(cart.created_at),
    }


def deserialize_cart(record: Record) -> Cart:
    """Reconstruct a :class:`Cart` from its stored record form.

    Expects the schema produced by :func:`serialize_cart`.  Nested item
    records are rebuilt with :func:`deserialize_cart_item` and the
    creation timestamp is parsed from its ISO-8601 form.
    """
    return Cart(
        cart_id=record["cart_id"],
        customer_id=record["customer_id"],
        items=[
            deserialize_cart_item(item_record)
            for item_record in record["items"]
        ],
        created_at=datetime_from_record(record["created_at"]),
    )


# ---------------------------------------------------------------------------
# OrderLine
# ---------------------------------------------------------------------------

def serialize_order_line(line: OrderLine) -> Record:
    """Convert an :class:`OrderLine` into its stored record form.

    Record schema::

        {
            "product_id": str,
            "sku":        str,
            "name":       str,
            "quantity":   int,
            "unit_price": dict,  # see money_to_record
            "line_total": dict,  # see money_to_record
        }

    Order lines denormalise the SKU and product name so historical
    orders stay readable even after catalog edits.
    """
    return {
        "product_id": line.product_id,
        "sku": line.sku,
        "name": line.name,
        "quantity": line.quantity,
        "unit_price": money_to_record(line.unit_price),
        "line_total": money_to_record(line.line_total),
    }


def deserialize_order_line(record: Record) -> OrderLine:
    """Reconstruct an :class:`OrderLine` from its stored record form.

    Expects the schema produced by :func:`serialize_order_line`.
    """
    return OrderLine(
        product_id=record["product_id"],
        sku=record["sku"],
        name=record["name"],
        quantity=record["quantity"],
        unit_price=money_from_record(record["unit_price"]),
        line_total=money_from_record(record["line_total"]),
    )


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

def serialize_order(order: Order) -> Record:
    """Convert an :class:`Order` into its stored record form.

    Record schema::

        {
            "order_id":         str,
            "customer_id":      str,
            "lines":            list[dict],  # see serialize_order_line
            "status":           str,
            "subtotal":         dict,        # see money_to_record
            "discount_total":   dict,
            "tax_total":        dict,
            "shipping_total":   dict,
            "grand_total":      dict,
            "shipping_address": dict,        # see serialize_address
            "placed_at":        str,         # ISO-8601 datetime
        }

    All five monetary totals are stored independently rather than being
    recomputed on load, so a stored order is an immutable financial
    record of what the customer was actually charged.
    """
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "lines": [serialize_order_line(line) for line in order.lines],
        "status": order.status,
        "subtotal": money_to_record(order.subtotal),
        "discount_total": money_to_record(order.discount_total),
        "tax_total": money_to_record(order.tax_total),
        "shipping_total": money_to_record(order.shipping_total),
        "grand_total": money_to_record(order.grand_total),
        "shipping_address": serialize_address(order.shipping_address),
        "placed_at": datetime_to_record(order.placed_at),
    }


def deserialize_order(record: Record) -> Order:
    """Reconstruct an :class:`Order` from its stored record form.

    Expects the schema produced by :func:`serialize_order`.  Nested
    line records, the shipping address, all five Money totals, and the
    placement timestamp are each rebuilt with their dedicated helpers.
    """
    return Order(
        order_id=record["order_id"],
        customer_id=record["customer_id"],
        lines=[
            deserialize_order_line(line_record)
            for line_record in record["lines"]
        ],
        status=record["status"],
        subtotal=money_from_record(record["subtotal"]),
        discount_total=money_from_record(record["discount_total"]),
        tax_total=money_from_record(record["tax_total"]),
        shipping_total=money_from_record(record["shipping_total"]),
        grand_total=money_from_record(record["grand_total"]),
        shipping_address=deserialize_address(record["shipping_address"]),
        placed_at=datetime_from_record(record["placed_at"]),
    )


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

def serialize_payment(payment: Payment) -> Record:
    """Convert a :class:`Payment` into its stored record form.

    Record schema::

        {
            "payment_id": str,
            "order_id":   str,
            "amount":     dict,  # see money_to_record
            "method":     str,   # e.g. "card", "paypal"
            "status":     str,   # e.g. "authorized", "captured"
        }
    """
    return {
        "payment_id": payment.payment_id,
        "order_id": payment.order_id,
        "amount": money_to_record(payment.amount),
        "method": payment.method,
        "status": payment.status,
    }


def deserialize_payment(record: Record) -> Payment:
    """Reconstruct a :class:`Payment` from its stored record form.

    Expects the schema produced by :func:`serialize_payment`.
    """
    return Payment(
        payment_id=record["payment_id"],
        order_id=record["order_id"],
        amount=money_from_record(record["amount"]),
        method=record["method"],
        status=record["status"],
    )


# ---------------------------------------------------------------------------
# Shipment
# ---------------------------------------------------------------------------

def serialize_shipment(shipment: Shipment) -> Record:
    """Convert a :class:`Shipment` into its stored record form.

    Record schema::

        {
            "shipment_id":   str,
            "order_id":      str,
            "carrier":       str,  # e.g. "UPS", "FedEx"
            "tracking_code": str,
            "status":        str,  # e.g. "pending", "in_transit"
        }
    """
    return {
        "shipment_id": shipment.shipment_id,
        "order_id": shipment.order_id,
        "carrier": shipment.carrier,
        "tracking_code": shipment.tracking_code,
        "status": shipment.status,
    }


def deserialize_shipment(record: Record) -> Shipment:
    """Reconstruct a :class:`Shipment` from its stored record form.

    Expects the schema produced by :func:`serialize_shipment`.
    """
    return Shipment(
        shipment_id=record["shipment_id"],
        order_id=record["order_id"],
        carrier=record["carrier"],
        tracking_code=record["tracking_code"],
        status=record["status"],
    )


# ---------------------------------------------------------------------------
# Discount
# ---------------------------------------------------------------------------

def serialize_discount(discount: Discount) -> Record:
    """Convert a :class:`Discount` into its stored record form.

    Record schema::

        {
            "code":               str,   # e.g. "WELCOME10"
            "kind":               str,   # "percent" or "fixed"
            "value":              int,   # percent points or cents
            "min_subtotal_cents": int,   # eligibility threshold
            "active":             bool,
        }

    ``value`` is interpreted according to ``kind``: whole percentage
    points for percent discounts, cents for fixed-amount discounts.
    """
    return {
        "code": discount.code,
        "kind": discount.kind,
        "value": discount.value,
        "min_subtotal_cents": discount.min_subtotal_cents,
        "active": discount.active,
    }


def deserialize_discount(record: Record) -> Discount:
    """Reconstruct a :class:`Discount` from its stored record form.

    Expects the schema produced by :func:`serialize_discount`.
    """
    return Discount(
        code=record["code"],
        kind=record["kind"],
        value=record["value"],
        min_subtotal_cents=record["min_subtotal_cents"],
        active=record["active"],
    )


# ---------------------------------------------------------------------------
# Record schemas and validation
# ---------------------------------------------------------------------------

#: Required record keys for every record type this module produces.
#: The keys mirror the ``Record schema`` blocks in each serializer's
#: docstring and are the contract that :func:`validate_record` enforces.
RECORD_SCHEMAS: Dict[str, tuple] = {
    "money": (
        "amount",
        "currency",
    ),
    "address": (
        "street",
        "city",
        "state",
        "postal_code",
        "country",
    ),
    "product": (
        "product_id",
        "sku",
        "name",
        "description",
        "price",
        "category",
        "tags",
        "weight_grams",
        "active",
    ),
    "customer": (
        "customer_id",
        "email",
        "name",
        "loyalty_tier",
        "addresses",
    ),
    "cart_item": (
        "product_id",
        "quantity",
        "unit_price",
    ),
    "cart": (
        "cart_id",
        "customer_id",
        "items",
        "created_at",
    ),
    "order_line": (
        "product_id",
        "sku",
        "name",
        "quantity",
        "unit_price",
        "line_total",
    ),
    "order": (
        "order_id",
        "customer_id",
        "lines",
        "status",
        "subtotal",
        "discount_total",
        "tax_total",
        "shipping_total",
        "grand_total",
        "shipping_address",
        "placed_at",
    ),
    "payment": (
        "payment_id",
        "order_id",
        "amount",
        "method",
        "status",
    ),
    "shipment": (
        "shipment_id",
        "order_id",
        "carrier",
        "tracking_code",
        "status",
    ),
    "discount": (
        "code",
        "kind",
        "value",
        "min_subtotal_cents",
        "active",
    ),
}


def validate_record(entity_name: str, record: Record) -> None:
    """Check that ``record`` carries every key required for ``entity_name``.

    Args:
        entity_name: A key of :data:`RECORD_SCHEMAS`, e.g. ``"order"``.
        record: The stored record to validate.

    Raises:
        ValidationError: If ``entity_name`` is not a known record type,
            or if the record is missing one or more required keys.  The
            error message lists every missing key so callers can fix a
            malformed record in one pass.
    """
    try:
        required = RECORD_SCHEMAS[entity_name]
    except KeyError:
        raise ValidationError(
            "Unknown record type {name!r}; expected one of: {names}".format(
                name=entity_name, names=", ".join(sorted(RECORD_SCHEMAS))
            )
        ) from None

    missing = [key for key in required if key not in record]
    if missing:
        raise ValidationError(
            "Record for {name!r} is missing required keys: {keys}".format(
                name=entity_name, keys=", ".join(missing)
            )
        )
