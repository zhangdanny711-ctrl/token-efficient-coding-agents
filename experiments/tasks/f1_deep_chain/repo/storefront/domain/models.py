"""Core domain entities for the storefront.

These dataclasses are deliberately behavior-light: they carry state,
enforce their own invariants via ``validate()`` (and cheap
``__post_init__`` type checks), and expose small convenience helpers.
Orchestration lives in the services layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from storefront.domain.errors import IllegalStateError, ValidationError
from storefront.domain.money import Money
from storefront.domain.validation import (
    require_email,
    require_in,
    require_non_empty,
    require_non_negative,
    require_positive,
    require_state,
    require_type,
)

# ----------------------------------------------------------------------
# Status vocabularies
# ----------------------------------------------------------------------

LOYALTY_TIERS = ("standard", "silver", "gold")

ORDER_STATUSES = ("pending", "paid", "fulfilled", "cancelled", "refunded")

#: Legal order status transitions. Terminal states map to empty tuples.
ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pending": ("paid", "cancelled"),
    "paid": ("fulfilled", "cancelled", "refunded"),
    "fulfilled": ("refunded",),
    "cancelled": (),
    "refunded": (),
}

PAYMENT_METHODS = ("card", "paypal", "giftcard")
PAYMENT_STATUSES = ("pending", "captured", "refunded")

SHIPMENT_STATUSES = ("queued", "shipped", "delivered")

DISCOUNT_KINDS = ("percent", "fixed")


# ----------------------------------------------------------------------
# Address
# ----------------------------------------------------------------------


@dataclass
class Address:
    """A physical mailing address, US-centric for tax purposes."""

    street: str
    city: str
    state: str
    postal_code: str
    country: str = "US"

    def validate(self) -> None:
        """Check every field; raise :class:`ValidationError` on failure."""
        require_non_empty(self.street, "street")
        require_non_empty(self.city, "city")
        require_state(self.state)
        require_non_empty(self.postal_code, "postal_code")
        require_non_empty(self.country, "country")
        if self.country == "US":
            digits = self.postal_code.replace("-", "")
            if not digits.isdigit() or len(self.postal_code) not in (5, 10):
                raise ValidationError(
                    f"postal_code must be ZIP or ZIP+4, got {self.postal_code!r}"
                )

    def one_line(self) -> str:
        """Render as a single display line."""
        return (
            f"{self.street}, {self.city}, {self.state} "
            f"{self.postal_code}, {self.country}"
        )

    def is_domestic(self) -> bool:
        """True when the address is in the US."""
        return self.country == "US"


# ----------------------------------------------------------------------
# Product
# ----------------------------------------------------------------------


@dataclass
class Product:
    """A sellable catalog item."""

    product_id: str
    sku: str
    name: str
    description: str
    price: Money
    category: str
    tags: list[str]
    weight_grams: int
    active: bool = True

    def __post_init__(self) -> None:
        require_type(self.price, Money, "price")
        require_type(self.tags, list, "tags")

    def validate(self) -> None:
        """Check invariants; raise :class:`ValidationError` on failure."""
        require_non_empty(self.product_id, "product_id")
        require_non_empty(self.sku, "sku")
        require_non_empty(self.name, "name")
        require_type(self.description, str, "description")
        require_type(self.price, Money, "price")
        if self.price.cents <= 0:
            raise ValidationError(
                f"price must be positive, got {self.price.to_decimal_string()}"
            )
        require_non_empty(self.category, "category")
        for i, tag in enumerate(self.tags):
            require_non_empty(tag, f"tags[{i}]")
        require_positive(self.weight_grams, "weight_grams")
        require_type(self.active, bool, "active")

    def has_tag(self, tag: str) -> bool:
        """True when the product carries ``tag`` (case-insensitive)."""
        wanted = tag.lower()
        return any(t.lower() == wanted for t in self.tags)

    def is_heavy(self, threshold_grams: int) -> bool:
        """True when the product weighs at least ``threshold_grams``."""
        return self.weight_grams >= threshold_grams

    def display_name(self) -> str:
        """Human-friendly one-liner including SKU and price."""
        return f"{self.name} [{self.sku}] — {self.price.format()}"


# ----------------------------------------------------------------------
# Customer
# ----------------------------------------------------------------------


@dataclass
class Customer:
    """A registered shopper with a loyalty tier and saved addresses."""

    customer_id: str
    email: str
    name: str
    loyalty_tier: str = "standard"
    addresses: list[Address] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_type(self.addresses, list, "addresses")

    def validate(self) -> None:
        """Check invariants; raise :class:`ValidationError` on failure."""
        require_non_empty(self.customer_id, "customer_id")
        require_email(self.email)
        require_non_empty(self.name, "name")
        require_in(self.loyalty_tier, LOYALTY_TIERS, "loyalty_tier")
        for address in self.addresses:
            require_type(address, Address, "addresses[]")
            address.validate()

    def primary_address(self) -> Address:
        """Return the first saved address.

        Raises :class:`ValidationError` when the customer has no
        addresses on file.
        """
        if not self.addresses:
            raise ValidationError(
                f"customer {self.customer_id} has no addresses on file"
            )
        return self.addresses[0]

    def add_address(self, address: Address) -> None:
        """Validate and append a new saved address."""
        require_type(address, Address, "address")
        address.validate()
        self.addresses.append(address)

    def is_premium(self) -> bool:
        """True for silver or gold loyalty members."""
        return self.loyalty_tier in ("silver", "gold")


# ----------------------------------------------------------------------
# Cart
# ----------------------------------------------------------------------


@dataclass
class CartItem:
    """A quantity of one product held in a cart at a captured price."""

    product_id: str
    quantity: int
    unit_price: Money

    def __post_init__(self) -> None:
        require_type(self.unit_price, Money, "unit_price")

    def validate(self) -> None:
        """Check invariants; raise :class:`ValidationError` on failure."""
        require_non_empty(self.product_id, "product_id")
        require_positive(self.quantity, "quantity")
        require_type(self.unit_price, Money, "unit_price")
        require_non_negative(self.unit_price.cents, "unit_price.cents")

    def line_total(self) -> Money:
        """Extended price: unit price times quantity."""
        return self.unit_price.mul(self.quantity)


@dataclass
class Cart:
    """A customer's in-progress selection of items."""

    cart_id: str
    customer_id: str
    items: list[CartItem]
    created_at: datetime

    def __post_init__(self) -> None:
        require_type(self.items, list, "items")
        require_type(self.created_at, datetime, "created_at")

    def validate(self) -> None:
        """Check the cart and every item within it."""
        require_non_empty(self.cart_id, "cart_id")
        require_non_empty(self.customer_id, "customer_id")
        seen: set[str] = set()
        for item in self.items:
            require_type(item, CartItem, "items[]")
            item.validate()
            if item.product_id in seen:
                raise ValidationError(
                    f"cart {self.cart_id} has duplicate line for "
                    f"product {item.product_id}"
                )
            seen.add(item.product_id)

    def total_quantity(self) -> int:
        """Sum of quantities across all lines."""
        return sum(item.quantity for item in self.items)

    def find_item(self, product_id: str) -> CartItem | None:
        """Return the line for ``product_id``, or None if absent."""
        for item in self.items:
            if item.product_id == product_id:
                return item
        return None

    def is_empty(self) -> bool:
        """True when the cart holds no items."""
        return not self.items

    def subtotal(self) -> Money:
        """Sum of all line totals; zero (USD) for an empty cart."""
        if not self.items:
            return Money.zero()
        total = self.items[0].line_total()
        for item in self.items[1:]:
            total = total.add(item.line_total())
        return total


# ----------------------------------------------------------------------
# Order
# ----------------------------------------------------------------------


@dataclass
class OrderLine:
    """An immutable snapshot of one purchased product on an order."""

    product_id: str
    sku: str
    name: str
    quantity: int
    unit_price: Money
    line_total: Money

    def __post_init__(self) -> None:
        require_type(self.unit_price, Money, "unit_price")
        require_type(self.line_total, Money, "line_total")

    def validate(self) -> None:
        """Check invariants, including the line-total arithmetic."""
        require_non_empty(self.product_id, "product_id")
        require_non_empty(self.sku, "sku")
        require_non_empty(self.name, "name")
        require_positive(self.quantity, "quantity")
        require_non_negative(self.unit_price.cents, "unit_price.cents")
        expected = self.unit_price.mul(self.quantity)
        if self.line_total != expected:
            raise ValidationError(
                f"line_total {self.line_total.to_decimal_string()} does not "
                f"equal unit_price x quantity "
                f"({expected.to_decimal_string()}) for product "
                f"{self.product_id}"
            )

    def describe(self) -> str:
        """Render as ``"2 x Widget @ $5.00 = $10.00"``."""
        return (
            f"{self.quantity} x {self.name} @ {self.unit_price.format()} "
            f"= {self.line_total.format()}"
        )


@dataclass
class Order:
    """A placed order with fully computed totals and a status lifecycle."""

    order_id: str
    customer_id: str
    lines: list[OrderLine]
    status: str
    subtotal: Money
    discount_total: Money
    tax_total: Money
    shipping_total: Money
    grand_total: Money
    shipping_address: Address
    placed_at: datetime

    def __post_init__(self) -> None:
        require_type(self.lines, list, "lines")
        for money_field in (
            "subtotal",
            "discount_total",
            "tax_total",
            "shipping_total",
            "grand_total",
        ):
            require_type(getattr(self, money_field), Money, money_field)
        require_type(self.shipping_address, Address, "shipping_address")
        require_type(self.placed_at, datetime, "placed_at")

    def validate(self) -> None:
        """Check identity, lines, status, address, and totals arithmetic."""
        require_non_empty(self.order_id, "order_id")
        require_non_empty(self.customer_id, "customer_id")
        require_in(self.status, ORDER_STATUSES, "status")
        if not self.lines:
            raise ValidationError(f"order {self.order_id} has no lines")
        for line in self.lines:
            require_type(line, OrderLine, "lines[]")
            line.validate()
        self.shipping_address.validate()
        self._validate_totals()

    def _validate_totals(self) -> None:
        """Verify each total individually, then the grand-total equation."""
        for name, amount in (
            ("subtotal", self.subtotal),
            ("discount_total", self.discount_total),
            ("tax_total", self.tax_total),
            ("shipping_total", self.shipping_total),
            ("grand_total", self.grand_total),
        ):
            require_non_negative(amount.cents, f"{name}.cents")
            if amount.currency != self.subtotal.currency:
                raise ValidationError(
                    f"{name} currency {amount.currency} does not match "
                    f"subtotal currency {self.subtotal.currency}"
                )
        lines_total = self.lines[0].line_total
        for line in self.lines[1:]:
            lines_total = lines_total.add(line.line_total)
        if lines_total != self.subtotal:
            raise ValidationError(
                f"subtotal {self.subtotal.to_decimal_string()} does not "
                f"match sum of lines {lines_total.to_decimal_string()}"
            )
        expected = (
            self.subtotal.sub(self.discount_total)
            .add(self.tax_total)
            .add(self.shipping_total)
        )
        if self.grand_total != expected:
            raise ValidationError(
                f"grand_total {self.grand_total.to_decimal_string()} != "
                f"subtotal - discount + tax + shipping "
                f"({expected.to_decimal_string()})"
            )

    # -- status lifecycle ------------------------------------------------

    def can_transition_to(self, status: str) -> bool:
        """True when moving from the current status to ``status`` is legal."""
        require_in(status, ORDER_STATUSES, "status")
        return status in ALLOWED_TRANSITIONS.get(self.status, ())

    def transition_to(self, status: str) -> None:
        """Move to ``status``; raise :class:`IllegalStateError` if illegal."""
        if not self.can_transition_to(status):
            raise IllegalStateError(
                f"order {self.order_id} cannot move from "
                f"{self.status!r} to {status!r}"
            )
        self.status = status

    def is_terminal(self) -> bool:
        """True when no further status transitions are possible."""
        return not ALLOWED_TRANSITIONS.get(self.status, ())

    # -- convenience -------------------------------------------------------

    def line_count(self) -> int:
        """Number of distinct order lines."""
        return len(self.lines)

    def total_quantity(self) -> int:
        """Sum of quantities across all lines."""
        return sum(line.quantity for line in self.lines)

    def find_line(self, product_id: str) -> OrderLine | None:
        """Return the line for ``product_id``, or None if absent."""
        for line in self.lines:
            if line.product_id == product_id:
                return line
        return None

    def summary(self) -> str:
        """Compact one-line summary for logs and reports."""
        return (
            f"order {self.order_id} [{self.status}] "
            f"{self.line_count()} lines, "
            f"{self.total_quantity()} items, "
            f"total {self.grand_total.format()}"
        )


# ----------------------------------------------------------------------
# Payment
# ----------------------------------------------------------------------


@dataclass
class Payment:
    """A payment attempt or capture against an order."""

    payment_id: str
    order_id: str
    amount: Money
    method: str
    status: str

    def __post_init__(self) -> None:
        require_type(self.amount, Money, "amount")

    def validate(self) -> None:
        """Check invariants; raise :class:`ValidationError` on failure."""
        require_non_empty(self.payment_id, "payment_id")
        require_non_empty(self.order_id, "order_id")
        require_positive(self.amount.cents, "amount.cents")
        require_in(self.method, PAYMENT_METHODS, "method")
        require_in(self.status, PAYMENT_STATUSES, "status")

    def is_captured(self) -> bool:
        """True when funds have been captured."""
        return self.status == "captured"

    def describe(self) -> str:
        """Render as e.g. ``"pay-000001: $42.00 via card (captured)"``."""
        return (
            f"{self.payment_id}: {self.amount.format()} via "
            f"{self.method} ({self.status})"
        )


# ----------------------------------------------------------------------
# Shipment
# ----------------------------------------------------------------------


@dataclass
class Shipment:
    """A physical shipment fulfilling (part of) an order."""

    shipment_id: str
    order_id: str
    carrier: str
    tracking_code: str
    status: str

    def validate(self) -> None:
        """Check invariants; raise :class:`ValidationError` on failure."""
        require_non_empty(self.shipment_id, "shipment_id")
        require_non_empty(self.order_id, "order_id")
        require_non_empty(self.carrier, "carrier")
        require_non_empty(self.tracking_code, "tracking_code")
        require_in(self.status, SHIPMENT_STATUSES, "status")

    def is_delivered(self) -> bool:
        """True when the carrier reported delivery."""
        return self.status == "delivered"

    def describe(self) -> str:
        """Render as e.g. ``"shp-000001 via UPS [shipped] #1Z999"``."""
        return (
            f"{self.shipment_id} via {self.carrier} "
            f"[{self.status}] #{self.tracking_code}"
        )


# ----------------------------------------------------------------------
# Discount
# ----------------------------------------------------------------------


@dataclass
class Discount:
    """A promotional code, either percentage-based or a fixed amount.

    ``value`` is a whole-number percentage (1-90) for ``kind ==
    "percent"``, or an amount in cents for ``kind == "fixed"``.
    """

    code: str
    kind: str
    value: int
    min_subtotal_cents: int
    active: bool = True

    def validate(self) -> None:
        """Check invariants; raise :class:`ValidationError` on failure."""
        require_non_empty(self.code, "code")
        require_in(self.kind, DISCOUNT_KINDS, "kind")
        require_type(self.value, int, "value")
        if self.kind == "percent":
            if not 1 <= self.value <= 90:
                raise ValidationError(
                    f"percent discount value must be between 1 and 90, "
                    f"got {self.value}"
                )
        else:
            require_positive(self.value, "value")
        require_non_negative(self.min_subtotal_cents, "min_subtotal_cents")
        require_type(self.active, bool, "active")

    def describe(self) -> str:
        """Render as e.g. ``"SAVE10: 10% off (min $50.00)"``."""
        minimum = Money(self.min_subtotal_cents).format()
        if self.kind == "percent":
            benefit = f"{self.value}% off"
        else:
            benefit = f"{Money(self.value).format()} off"
        state = "" if self.active else " [inactive]"
        return f"{self.code}: {benefit} (min {minimum}){state}"
