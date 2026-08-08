"""Round-trip tests for storefront.persistence.serializers."""

from datetime import datetime

import pytest

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
from storefront.persistence.serializers import (
    deserialize_cart,
    deserialize_customer,
    deserialize_discount,
    deserialize_order,
    deserialize_payment,
    deserialize_product,
    deserialize_shipment,
    money_from_record,
    money_to_record,
    serialize_cart,
    serialize_customer,
    serialize_discount,
    serialize_order,
    serialize_payment,
    serialize_product,
    serialize_shipment,
    validate_record,
)

NOW = datetime(2026, 1, 15, 9, 0, 0)

ADDRESS = Address(street="1 Main St", city="Springfield", state="CA",
                  postal_code="90210")


# ----------------------------------------------------------------------
# Money records
# ----------------------------------------------------------------------

def test_money_record_shape():
    assert money_to_record(Money(1234)) == {"amount": "12.34", "currency": "USD"}


def test_money_round_trip():
    m = Money(70599, "EUR")
    assert money_from_record(money_to_record(m)) == m


def test_money_round_trip_negative():
    m = Money(-307)
    assert money_from_record(money_to_record(m)) == m


# ----------------------------------------------------------------------
# entity round trips
# ----------------------------------------------------------------------

def test_product_round_trip():
    product = Product(
        product_id="prd-000001", sku="ELEC-1001", name="Earbuds",
        description="Nice.", price=Money(7999), category="electronics",
        tags=["audio", "wireless"], weight_grams=58, active=False,
    )
    record = serialize_product(product)
    assert deserialize_product(record) == product


def test_product_record_tags_are_copied():
    product = Product(
        product_id="p", sku="s", name="n", description="d",
        price=Money(100), category="c", tags=["a"], weight_grams=1,
    )
    record = serialize_product(product)
    record["tags"].append("mutated")
    assert product.tags == ["a"]


def test_customer_round_trip_nested_addresses():
    customer = Customer(
        customer_id="cus-000001", email="a@example.com", name="A",
        loyalty_tier="gold",
        addresses=[
            ADDRESS,
            Address(street="2 Elm St", city="Austin", state="TX",
                    postal_code="78704"),
        ],
    )
    record = serialize_customer(customer)
    restored = deserialize_customer(record)
    assert restored == customer
    assert len(restored.addresses) == 2
    assert restored.addresses[1].state == "TX"


def test_cart_round_trip():
    cart = Cart(
        cart_id="crt-000001", customer_id="cus-000001",
        items=[
            CartItem(product_id="p1", quantity=2, unit_price=Money(500)),
            CartItem(product_id="p2", quantity=1, unit_price=Money(7999)),
        ],
        created_at=NOW,
    )
    record = serialize_cart(cart)
    restored = deserialize_cart(record)
    assert restored == cart
    assert restored.created_at == NOW
    assert record["created_at"] == "2026-01-15T09:00:00"


def test_order_round_trip():
    lines = [
        OrderLine(product_id="p1", sku="S1", name="One", quantity=2,
                  unit_price=Money(500), line_total=Money(1000)),
        OrderLine(product_id="p2", sku="S2", name="Two", quantity=1,
                  unit_price=Money(7999), line_total=Money(7999)),
    ]
    order = Order(
        order_id="ord-000001", customer_id="cus-000001", lines=lines,
        status="paid", subtotal=Money(8999), discount_total=Money(900),
        tax_total=Money(587), shipping_total=Money(0),
        grand_total=Money(8686), shipping_address=ADDRESS, placed_at=NOW,
    )
    restored = deserialize_order(serialize_order(order))
    assert restored == order
    assert restored.grand_total == Money(8686)
    assert restored.lines[1].line_total == Money(7999)


def test_payment_round_trip():
    payment = Payment(payment_id="pay-000001", order_id="ord-000001",
                      amount=Money(8686), method="card", status="captured")
    assert deserialize_payment(serialize_payment(payment)) == payment


def test_shipment_round_trip():
    shipment = Shipment(shipment_id="shp-000001", order_id="ord-000001",
                        carrier="UPS", tracking_code="UPS-shp-000001",
                        status="queued")
    assert deserialize_shipment(serialize_shipment(shipment)) == shipment


def test_discount_round_trip():
    discount = Discount(code="SAVE15", kind="percent", value=15,
                        min_subtotal_cents=5000, active=False)
    assert deserialize_discount(serialize_discount(discount)) == discount


# ----------------------------------------------------------------------
# validate_record
# ----------------------------------------------------------------------

def test_validate_record_happy():
    validate_record("money", {"amount": "1.00", "currency": "USD"})


def test_validate_record_missing_key():
    with pytest.raises(ValidationError, match="missing required keys"):
        validate_record("money", {"amount": "1.00"})


def test_validate_record_lists_all_missing_keys():
    with pytest.raises(ValidationError) as excinfo:
        validate_record("payment", {"payment_id": "pay-1"})
    message = str(excinfo.value)
    for key in ("order_id", "amount", "method", "status"):
        assert key in message


def test_validate_record_unknown_type():
    with pytest.raises(ValidationError, match="Unknown record type"):
        validate_record("gizmo", {})


def test_serialized_order_passes_validate_record():
    lines = [OrderLine(product_id="p1", sku="S1", name="One", quantity=1,
                       unit_price=Money(500), line_total=Money(500))]
    order = Order(
        order_id="ord-1", customer_id="cus-1", lines=lines, status="pending",
        subtotal=Money(500), discount_total=Money(0), tax_total=Money(36),
        shipping_total=Money(599), grand_total=Money(1135),
        shipping_address=ADDRESS, placed_at=NOW,
    )
    validate_record("order", serialize_order(order))
