"""Tests for storefront.services.orders.OrderService (full lifecycle)."""

import pytest

from storefront.domain.errors import (
    DiscountError,
    IllegalStateError,
    NotFoundError,
    OutOfStockError,
    ValidationError,
)
from storefront.domain.money import Money
from storefront.services import InventoryService

from tests.conftest import customer_id_for_email, product_id_for_sku


@pytest.fixture
def inventory(seeded_store):
    return InventoryService(seeded_store)


@pytest.fixture
def noah_id(seeded_store):
    # standard tier, WA address.
    return customer_id_for_email(seeded_store, "noah.kim@example.com")


@pytest.fixture
def maya_id(seeded_store):
    # gold tier, CA address.
    return customer_id_for_email(seeded_store, "maya.chen@example.com")


@pytest.fixture
def kettle_id(seeded_store):
    return product_id_for_sku(seeded_store, "KTCH-2002")  # 54.99, 820 g


@pytest.fixture
def bottle_id(seeded_store):
    return product_id_for_sku(seeded_store, "OUTD-3002")  # 27.99, 390 g


@pytest.fixture
def monitor_id(seeded_store):
    return product_id_for_sku(seeded_store, "ELEC-1003")  # low stock: 2 avail


def make_cart(cart_service, customer_id, *lines):
    cart = cart_service.create_cart(customer_id)
    for product_id, qty in lines:
        cart_service.add_item(cart.cart_id, product_id, qty)
    return cart


@pytest.fixture
def placed_order(cart_service, order_service, noah_id, kettle_id, bottle_id):
    cart = make_cart(cart_service, noah_id, (kettle_id, 1), (bottle_id, 2))
    return order_service.place_order(noah_id, cart.cart_id)


# ----------------------------------------------------------------------
# place_order happy path
# ----------------------------------------------------------------------

def test_place_order_happy_path_totals(cart_service, order_service, noah_id,
                                       kettle_id, bottle_id):
    cart = make_cart(cart_service, noah_id, (kettle_id, 1), (bottle_id, 2))
    order = order_service.place_order(noah_id, cart.cart_id)
    assert order.status == "pending"
    assert order.subtotal == Money(5499 + 2 * 2799)  # 110.97
    assert order.discount_total.is_zero()
    assert order.shipping_total.is_zero()  # above free-shipping threshold
    assert order.tax_total == order.subtotal.percent(0.065)  # WA
    assert order.grand_total == (
        order.subtotal.sub(order.discount_total)
        .add(order.tax_total).add(order.shipping_total)
    )
    assert order.shipping_address.state == "WA"
    order.validate()


def test_place_order_creates_pending_payment(order_service, placed_order):
    payments = order_service.payments_for_order(placed_order.order_id)
    assert len(payments) == 1
    payment = payments[0]
    assert payment.status == "pending"
    assert payment.amount == placed_order.grand_total
    assert payment.order_id == placed_order.order_id


def test_place_order_clears_cart(cart_service, order_service, noah_id,
                                 kettle_id):
    cart = make_cart(cart_service, noah_id, (kettle_id, 1))
    order_service.place_order(noah_id, cart.cart_id)
    assert cart_service.get_cart(cart.cart_id).is_empty()


def test_place_order_reserves_inventory(cart_service, order_service, noah_id,
                                        kettle_id, inventory):
    before_avail = inventory.available(kettle_id)
    before_res = inventory.reserved(kettle_id)
    cart = make_cart(cart_service, noah_id, (kettle_id, 3))
    order_service.place_order(noah_id, cart.cart_id)
    assert inventory.available(kettle_id) == before_avail - 3
    assert inventory.reserved(kettle_id) == before_res + 3


def test_place_order_lines_denormalise_product(order_service, placed_order,
                                               kettle_id):
    line = placed_order.find_line(kettle_id)
    assert line.sku == "KTCH-2002"
    assert line.name == "Brewline Pour-Over Kettle"
    assert line.line_total == Money(5499)


def test_place_order_empty_cart_rejected(cart_service, order_service, noah_id):
    cart = cart_service.create_cart(noah_id)
    with pytest.raises(ValidationError, match="empty"):
        order_service.place_order(noah_id, cart.cart_id)


def test_place_order_cart_ownership_enforced(cart_service, order_service,
                                             noah_id, maya_id, kettle_id):
    cart = make_cart(cart_service, noah_id, (kettle_id, 1))
    with pytest.raises(ValidationError, match="belongs to"):
        order_service.place_order(maya_id, cart.cart_id)


def test_place_order_unknown_customer(cart_service, order_service, noah_id,
                                      kettle_id):
    cart = make_cart(cart_service, noah_id, (kettle_id, 1))
    with pytest.raises(NotFoundError):
        order_service.place_order("cus-999999", cart.cart_id)


def test_place_order_bad_address_index(cart_service, order_service, noah_id,
                                       kettle_id):
    cart = make_cart(cart_service, noah_id, (kettle_id, 1))
    with pytest.raises(ValidationError, match="no address at index"):
        order_service.place_order(noah_id, cart.cart_id, address_index=5)


def test_place_order_secondary_address(cart_service, order_service,
                                       seeded_store, kettle_id):
    sofia = customer_id_for_email(seeded_store, "sofia.ramirez@example.com")
    cart = make_cart(cart_service, sofia, (kettle_id, 1))
    order = order_service.place_order(sofia, cart.cart_id, address_index=1)
    assert order.shipping_address.city == "Austin"


# ----------------------------------------------------------------------
# discount codes
# ----------------------------------------------------------------------

def test_place_order_with_discount_code(cart_service, order_service, noah_id,
                                        kettle_id, bottle_id):
    cart = make_cart(cart_service, noah_id, (kettle_id, 1), (bottle_id, 2))
    order = order_service.place_order(noah_id, cart.cart_id,
                                      discount_code="SAVE15")
    assert order.discount_total == order.subtotal.percent(0.15)
    assert order.grand_total == (
        order.subtotal.sub(order.discount_total)
        .add(order.tax_total).add(order.shipping_total)
    )


def test_place_order_gold_tier_discount(cart_service, order_service, maya_id,
                                        kettle_id, bottle_id):
    cart = make_cart(cart_service, maya_id, (kettle_id, 1), (bottle_id, 2))
    order = order_service.place_order(maya_id, cart.cart_id)
    assert order.discount_total == order.subtotal.percent(0.02)
    order.validate()


def test_place_order_unknown_code_rolls_back_reservations(
        cart_service, order_service, noah_id, kettle_id, inventory):
    before_avail = inventory.available(kettle_id)
    before_res = inventory.reserved(kettle_id)
    cart = make_cart(cart_service, noah_id, (kettle_id, 1))
    with pytest.raises(DiscountError):
        order_service.place_order(noah_id, cart.cart_id, discount_code="BOGUS")
    assert inventory.available(kettle_id) == before_avail
    assert inventory.reserved(kettle_id) == before_res
    # The cart survives a failed placement.
    assert not cart_service.get_cart(cart.cart_id).is_empty()


# ----------------------------------------------------------------------
# out-of-stock rollback
# ----------------------------------------------------------------------

def test_place_order_out_of_stock(cart_service, order_service, noah_id,
                                  monitor_id, inventory):
    # Seeded low-stock monitor: available=2, reserved=1; ordering 3 fails.
    cart = make_cart(cart_service, noah_id, (monitor_id, 3))
    with pytest.raises(OutOfStockError):
        order_service.place_order(noah_id, cart.cart_id)
    assert inventory.available(monitor_id) == 2
    assert inventory.reserved(monitor_id) == 1


def test_out_of_stock_releases_earlier_lines(cart_service, order_service,
                                             noah_id, kettle_id, monitor_id,
                                             inventory):
    kettle_avail = inventory.available(kettle_id)
    kettle_res = inventory.reserved(kettle_id)
    cart = make_cart(cart_service, noah_id, (kettle_id, 2), (monitor_id, 3))
    with pytest.raises(OutOfStockError):
        order_service.place_order(noah_id, cart.cart_id)
    # The kettle line that was reserved first must have been released.
    assert inventory.available(kettle_id) == kettle_avail
    assert inventory.reserved(kettle_id) == kettle_res
    assert inventory.available(monitor_id) == 2
    assert inventory.reserved(monitor_id) == 1


def test_out_of_stock_creates_no_order_or_payment(cart_service, order_service,
                                                  noah_id, monitor_id,
                                                  seeded_store):
    cart = make_cart(cart_service, noah_id, (monitor_id, 3))
    with pytest.raises(OutOfStockError):
        order_service.place_order(noah_id, cart.cart_id)
    assert seeded_store.count("orders") == 0
    assert seeded_store.count("payments") == 0


# ----------------------------------------------------------------------
# pay_order
# ----------------------------------------------------------------------

def test_pay_order_captures_and_commits(order_service, placed_order,
                                        inventory, kettle_id, bottle_id):
    kettle_res = inventory.reserved(kettle_id)
    paid = order_service.pay_order(placed_order.order_id, method="paypal")
    assert paid.status == "paid"
    payment = order_service.payments_for_order(placed_order.order_id)[0]
    assert payment.status == "captured"
    assert payment.method == "paypal"
    # Reservations committed: reserved drops, available unchanged.
    assert inventory.reserved(kettle_id) == kettle_res - 1


def test_pay_order_twice_rejected(order_service, placed_order):
    order_service.pay_order(placed_order.order_id)
    with pytest.raises(IllegalStateError):
        order_service.pay_order(placed_order.order_id)


def test_pay_unknown_order(order_service):
    with pytest.raises(NotFoundError):
        order_service.pay_order("ord-999999")


# ----------------------------------------------------------------------
# fulfill_order
# ----------------------------------------------------------------------

def test_fulfill_order(order_service, placed_order):
    order_service.pay_order(placed_order.order_id)
    shipment = order_service.fulfill_order(placed_order.order_id,
                                           carrier="FedEx")
    assert shipment.status == "queued"
    assert shipment.carrier == "FedEx"
    assert shipment.tracking_code == "FEDEX-" + shipment.shipment_id
    assert order_service.get_order(placed_order.order_id).status == "fulfilled"
    shipments = order_service.shipments_for_order(placed_order.order_id)
    assert [s.shipment_id for s in shipments] == [shipment.shipment_id]


def test_fulfill_pending_order_rejected(order_service, placed_order):
    with pytest.raises(IllegalStateError):
        order_service.fulfill_order(placed_order.order_id)


def test_fulfill_cancelled_order_rejected(order_service, placed_order):
    order_service.cancel_order(placed_order.order_id)
    with pytest.raises(IllegalStateError):
        order_service.fulfill_order(placed_order.order_id)


# ----------------------------------------------------------------------
# cancel_order
# ----------------------------------------------------------------------

def test_cancel_pending_releases_stock(order_service, placed_order,
                                       inventory, kettle_id, bottle_id):
    kettle_avail = inventory.available(kettle_id)
    kettle_res = inventory.reserved(kettle_id)
    cancelled = order_service.cancel_order(placed_order.order_id)
    assert cancelled.status == "cancelled"
    assert inventory.available(kettle_id) == kettle_avail + 1
    assert inventory.reserved(kettle_id) == kettle_res - 1
    # Pending payment stays pending: money never moved.
    payment = order_service.payments_for_order(placed_order.order_id)[0]
    assert payment.status == "pending"


def test_cancel_paid_restocks_and_refunds(order_service, placed_order,
                                          inventory, bottle_id):
    order_service.pay_order(placed_order.order_id)
    avail_after_pay = inventory.available(bottle_id)
    res_after_pay = inventory.reserved(bottle_id)
    cancelled = order_service.cancel_order(placed_order.order_id)
    assert cancelled.status == "cancelled"
    # Paid cancellation restocks (committed units come back as available).
    assert inventory.available(bottle_id) == avail_after_pay + 2
    assert inventory.reserved(bottle_id) == res_after_pay
    payment = order_service.payments_for_order(placed_order.order_id)[0]
    assert payment.status == "refunded"


def test_cancel_fulfilled_rejected(order_service, placed_order):
    order_service.pay_order(placed_order.order_id)
    order_service.fulfill_order(placed_order.order_id)
    with pytest.raises(IllegalStateError):
        order_service.cancel_order(placed_order.order_id)


def test_cancel_twice_rejected(order_service, placed_order):
    order_service.cancel_order(placed_order.order_id)
    with pytest.raises(IllegalStateError):
        order_service.cancel_order(placed_order.order_id)


# ----------------------------------------------------------------------
# refund_order
# ----------------------------------------------------------------------

def test_refund_fulfilled_order(order_service, placed_order):
    order_service.pay_order(placed_order.order_id)
    order_service.fulfill_order(placed_order.order_id)
    refunded = order_service.refund_order(placed_order.order_id)
    assert refunded.status == "refunded"
    payment = order_service.payments_for_order(placed_order.order_id)[0]
    assert payment.status == "refunded"


def test_refund_does_not_restock(order_service, placed_order, inventory,
                                 kettle_id):
    order_service.pay_order(placed_order.order_id)
    order_service.fulfill_order(placed_order.order_id)
    avail = inventory.available(kettle_id)
    order_service.refund_order(placed_order.order_id)
    assert inventory.available(kettle_id) == avail


def test_refund_pending_rejected(order_service, placed_order):
    with pytest.raises(IllegalStateError):
        order_service.refund_order(placed_order.order_id)


def test_refund_paid_rejected(order_service, placed_order):
    order_service.pay_order(placed_order.order_id)
    with pytest.raises(IllegalStateError):
        order_service.refund_order(placed_order.order_id)


def test_refund_twice_rejected(order_service, placed_order):
    order_service.pay_order(placed_order.order_id)
    order_service.fulfill_order(placed_order.order_id)
    order_service.refund_order(placed_order.order_id)
    with pytest.raises(IllegalStateError):
        order_service.refund_order(placed_order.order_id)


# ----------------------------------------------------------------------
# queries
# ----------------------------------------------------------------------

def test_list_orders_for_customer(order_service, placed_order, noah_id):
    orders = order_service.list_orders_for_customer(noah_id)
    assert [o.order_id for o in orders] == [placed_order.order_id]


def test_list_orders_by_status(order_service, placed_order):
    assert [o.order_id for o in order_service.list_orders_by_status("pending")] \
        == [placed_order.order_id]
    assert order_service.list_orders_by_status("paid") == []


def test_shipments_for_unknown_order_raises(order_service):
    with pytest.raises(NotFoundError):
        order_service.shipments_for_order("ord-999999")


def test_order_totals_summary(order_service, placed_order):
    summary = order_service.order_totals_summary(placed_order.order_id)
    assert summary["order_id"] == placed_order.order_id
    assert summary["status"] == "pending"
    assert summary["payment_status"] == "pending"
    assert summary["subtotal"] == placed_order.subtotal.to_decimal_string()
    assert summary["grand_total"] == placed_order.grand_total.to_decimal_string()
    assert len(summary["lines"]) == 2
    assert all(isinstance(line["unit_price"], str) for line in summary["lines"])
