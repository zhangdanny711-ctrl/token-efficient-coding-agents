"""Tests for storefront.domain.models entities."""

from datetime import datetime

import pytest

from storefront.domain.errors import IllegalStateError, ValidationError
from storefront.domain.models import (
    ALLOWED_TRANSITIONS,
    ORDER_STATUSES,
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

NOW = datetime(2026, 1, 15, 9, 0, 0)


def make_address(**overrides):
    kwargs = dict(street="1 Main St", city="Springfield", state="CA",
                  postal_code="90210")
    kwargs.update(overrides)
    return Address(**kwargs)


def make_product(**overrides):
    kwargs = dict(product_id="prd-000001", sku="SKU-1", name="Widget",
                  description="A widget.", price=Money(500),
                  category="misc", tags=["a"], weight_grams=100)
    kwargs.update(overrides)
    return Product(**kwargs)


def make_order_line(qty=2, unit_cents=500):
    return OrderLine(
        product_id="prd-000001", sku="SKU-1", name="Widget",
        quantity=qty, unit_price=Money(unit_cents),
        line_total=Money(unit_cents * qty),
    )


def make_order(**overrides):
    line = make_order_line()
    kwargs = dict(
        order_id="ord-000001", customer_id="cus-000001", lines=[line],
        status="pending", subtotal=Money(1000), discount_total=Money(0),
        tax_total=Money(73), shipping_total=Money(599),
        grand_total=Money(1672), shipping_address=make_address(),
        placed_at=NOW,
    )
    kwargs.update(overrides)
    return Order(**kwargs)


# ----------------------------------------------------------------------
# Address
# ----------------------------------------------------------------------

def test_address_validate_happy():
    make_address().validate()


def test_address_validate_zip_plus_four():
    make_address(postal_code="90210-1234").validate()


def test_address_rejects_bad_state():
    with pytest.raises(ValidationError):
        make_address(state="California").validate()


def test_address_rejects_bad_zip():
    with pytest.raises(ValidationError):
        make_address(postal_code="9021").validate()


def test_address_one_line():
    assert make_address().one_line() == "1 Main St, Springfield, CA 90210, US"


def test_address_is_domestic():
    assert make_address().is_domestic()
    assert not make_address(country="CA", postal_code="K1A0B1").is_domestic()


# ----------------------------------------------------------------------
# Product
# ----------------------------------------------------------------------

def test_product_validate_happy():
    make_product().validate()


def test_product_rejects_non_positive_price():
    with pytest.raises(ValidationError):
        make_product(price=Money(0)).validate()


def test_product_rejects_blank_sku():
    with pytest.raises(ValidationError):
        make_product(sku="  ").validate()


def test_product_rejects_non_positive_weight():
    with pytest.raises(ValidationError):
        make_product(weight_grams=0).validate()


def test_product_has_tag_case_insensitive():
    p = make_product(tags=["Audio", "wireless"])
    assert p.has_tag("audio")
    assert p.has_tag("WIRELESS")
    assert not p.has_tag("video")


def test_product_is_heavy():
    p = make_product(weight_grams=5000)
    assert p.is_heavy(5000)
    assert not p.is_heavy(5001)


# ----------------------------------------------------------------------
# Customer
# ----------------------------------------------------------------------

def test_customer_validate_happy():
    Customer(customer_id="cus-1", email="a@example.com", name="A",
             loyalty_tier="gold", addresses=[make_address()]).validate()


def test_customer_rejects_bad_email():
    with pytest.raises(ValidationError):
        Customer(customer_id="cus-1", email="not-an-email", name="A").validate()


def test_customer_rejects_bad_tier():
    with pytest.raises(ValidationError):
        Customer(customer_id="cus-1", email="a@example.com", name="A",
                 loyalty_tier="platinum").validate()


def test_customer_primary_address_requires_one():
    c = Customer(customer_id="cus-1", email="a@example.com", name="A")
    with pytest.raises(ValidationError):
        c.primary_address()


def test_customer_add_address_and_premium():
    c = Customer(customer_id="cus-1", email="a@example.com", name="A",
                 loyalty_tier="silver")
    c.add_address(make_address())
    assert c.primary_address() is c.addresses[0]
    assert c.is_premium()


# ----------------------------------------------------------------------
# Cart / CartItem
# ----------------------------------------------------------------------

def test_cart_item_line_total():
    item = CartItem(product_id="p", quantity=3, unit_price=Money(250))
    assert item.line_total() == Money(750)


def test_cart_item_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        CartItem(product_id="p", quantity=0, unit_price=Money(100)).validate()


def test_cart_validate_rejects_duplicate_lines():
    items = [
        CartItem(product_id="p1", quantity=1, unit_price=Money(100)),
        CartItem(product_id="p1", quantity=2, unit_price=Money(100)),
    ]
    cart = Cart(cart_id="crt-1", customer_id="cus-1", items=items, created_at=NOW)
    with pytest.raises(ValidationError):
        cart.validate()


def test_cart_subtotal_and_queries():
    items = [
        CartItem(product_id="p1", quantity=2, unit_price=Money(100)),
        CartItem(product_id="p2", quantity=1, unit_price=Money(350)),
    ]
    cart = Cart(cart_id="crt-1", customer_id="cus-1", items=items, created_at=NOW)
    cart.validate()
    assert cart.subtotal() == Money(550)
    assert cart.total_quantity() == 3
    assert cart.find_item("p2").quantity == 1
    assert cart.find_item("missing") is None
    assert not cart.is_empty()


def test_empty_cart_subtotal_zero():
    cart = Cart(cart_id="crt-1", customer_id="cus-1", items=[], created_at=NOW)
    assert cart.is_empty()
    assert cart.subtotal() == Money.zero()


# ----------------------------------------------------------------------
# OrderLine
# ----------------------------------------------------------------------

def test_order_line_validate_happy():
    make_order_line().validate()


def test_order_line_rejects_bad_line_total():
    line = OrderLine(product_id="p", sku="s", name="n", quantity=2,
                     unit_price=Money(500), line_total=Money(999))
    with pytest.raises(ValidationError):
        line.validate()


# ----------------------------------------------------------------------
# Order status transitions
# ----------------------------------------------------------------------

TRANSITION_TABLE = [
    (frm, to, to in ALLOWED_TRANSITIONS[frm])
    for frm in ORDER_STATUSES
    for to in ORDER_STATUSES
]


@pytest.mark.parametrize("frm, to, allowed", TRANSITION_TABLE)
def test_order_transition_table(frm, to, allowed):
    order = make_order(status=frm)
    assert order.can_transition_to(to) is allowed
    if allowed:
        order.transition_to(to)
        assert order.status == to
    else:
        with pytest.raises(IllegalStateError):
            order.transition_to(to)


def test_order_can_transition_rejects_unknown_status():
    with pytest.raises(ValidationError):
        make_order().can_transition_to("shipped")


def test_order_is_terminal():
    assert make_order(status="cancelled").is_terminal()
    assert make_order(status="refunded").is_terminal()
    assert not make_order(status="pending").is_terminal()


# ----------------------------------------------------------------------
# Order totals
# ----------------------------------------------------------------------

def test_order_validate_happy():
    make_order().validate()


def test_order_totals_identity_violation():
    with pytest.raises(ValidationError):
        make_order(grand_total=Money(9999)).validate()


def test_order_subtotal_must_match_lines():
    with pytest.raises(ValidationError):
        make_order(subtotal=Money(1100), grand_total=Money(1772)).validate()


def test_order_rejects_negative_totals():
    with pytest.raises(ValidationError):
        make_order(discount_total=Money(-100), grand_total=Money(1772)).validate()


def test_order_rejects_no_lines():
    with pytest.raises(ValidationError):
        make_order(lines=[]).validate()


def test_order_rejects_currency_mismatch_in_totals():
    with pytest.raises(ValidationError):
        make_order(tax_total=Money(73, "EUR")).validate()


def test_order_convenience_helpers():
    order = make_order()
    assert order.line_count() == 1
    assert order.total_quantity() == 2
    assert order.find_line("prd-000001") is order.lines[0]
    assert order.find_line("nope") is None
    assert "ord-000001" in order.summary()


# ----------------------------------------------------------------------
# Payment / Shipment / Discount
# ----------------------------------------------------------------------

def test_payment_validate_happy():
    Payment(payment_id="pay-1", order_id="ord-1", amount=Money(100),
            method="card", status="captured").validate()


def test_payment_rejects_bad_method():
    with pytest.raises(ValidationError):
        Payment(payment_id="pay-1", order_id="ord-1", amount=Money(100),
                method="cash", status="pending").validate()


def test_payment_rejects_zero_amount():
    with pytest.raises(ValidationError):
        Payment(payment_id="pay-1", order_id="ord-1", amount=Money(0),
                method="card", status="pending").validate()


def test_shipment_validate_happy():
    Shipment(shipment_id="shp-1", order_id="ord-1", carrier="UPS",
             tracking_code="UPS-1", status="queued").validate()


def test_shipment_rejects_bad_status():
    with pytest.raises(ValidationError):
        Shipment(shipment_id="shp-1", order_id="ord-1", carrier="UPS",
                 tracking_code="UPS-1", status="lost").validate()


def test_discount_validate_percent_bounds():
    Discount(code="X", kind="percent", value=90, min_subtotal_cents=0).validate()
    with pytest.raises(ValidationError):
        Discount(code="X", kind="percent", value=91, min_subtotal_cents=0).validate()
    with pytest.raises(ValidationError):
        Discount(code="X", kind="percent", value=0, min_subtotal_cents=0).validate()


def test_discount_fixed_requires_positive_value():
    Discount(code="X", kind="fixed", value=500, min_subtotal_cents=0).validate()
    with pytest.raises(ValidationError):
        Discount(code="X", kind="fixed", value=0, min_subtotal_cents=0).validate()
