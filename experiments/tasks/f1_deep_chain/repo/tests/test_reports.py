"""Tests for storefront.services.reports.ReportsService."""

import pytest

from storefront.domain.money import Money

from tests.conftest import customer_id_for_email, product_id_for_sku


def make_order(cart_service, order_service, customer_id, *lines):
    cart = cart_service.create_cart(customer_id)
    for product_id, qty in lines:
        cart_service.add_item(cart.cart_id, product_id, qty)
    return order_service.place_order(customer_id, cart.cart_id)


@pytest.fixture
def noah_id(seeded_store):
    return customer_id_for_email(seeded_store, "noah.kim@example.com")


@pytest.fixture
def liam_id(seeded_store):
    return customer_id_for_email(seeded_store, "liam.osullivan@example.com")


@pytest.fixture
def kettle_id(seeded_store):
    return product_id_for_sku(seeded_store, "KTCH-2002")


@pytest.fixture
def bottle_id(seeded_store):
    return product_id_for_sku(seeded_store, "OUTD-3002")


@pytest.fixture
def orderbook(cart_service, order_service, noah_id, liam_id, kettle_id,
              bottle_id):
    """One order in each interesting status; returns the orders by key."""
    paid = make_order(cart_service, order_service, noah_id, (kettle_id, 1))
    order_service.pay_order(paid.order_id)

    fulfilled = make_order(cart_service, order_service, noah_id,
                           (bottle_id, 2))
    order_service.pay_order(fulfilled.order_id)
    order_service.fulfill_order(fulfilled.order_id)

    pending = make_order(cart_service, order_service, liam_id, (bottle_id, 1))

    cancelled = make_order(cart_service, order_service, liam_id,
                           (kettle_id, 1))
    order_service.cancel_order(cancelled.order_id)

    refunded = make_order(cart_service, order_service, noah_id,
                          (kettle_id, 2))
    order_service.pay_order(refunded.order_id)
    order_service.fulfill_order(refunded.order_id)
    order_service.refund_order(refunded.order_id)

    return {
        "paid": paid, "fulfilled": fulfilled, "pending": pending,
        "cancelled": cancelled, "refunded": refunded,
    }


# ----------------------------------------------------------------------
# revenue_summary
# ----------------------------------------------------------------------

def test_revenue_summary_empty(reports_service):
    summary = reports_service.revenue_summary()
    assert summary == {
        "order_count": 0,
        "gross_revenue": "0.00",
        "tax_collected": "0.00",
        "shipping_collected": "0.00",
        "discounts_given": "0.00",
    }


def test_revenue_summary_counts_paid_and_fulfilled_only(reports_service,
                                                        orderbook):
    summary = reports_service.revenue_summary()
    assert summary["order_count"] == 2
    expected_gross = orderbook["paid"].grand_total.add(
        orderbook["fulfilled"].grand_total)
    assert summary["gross_revenue"] == expected_gross.to_decimal_string()
    expected_tax = orderbook["paid"].tax_total.add(
        orderbook["fulfilled"].tax_total)
    assert summary["tax_collected"] == expected_tax.to_decimal_string()
    expected_shipping = orderbook["paid"].shipping_total.add(
        orderbook["fulfilled"].shipping_total)
    assert summary["shipping_collected"] == expected_shipping.to_decimal_string()


# ----------------------------------------------------------------------
# sales_by_status
# ----------------------------------------------------------------------

def test_sales_by_status_stable_shape_when_empty(reports_service):
    assert reports_service.sales_by_status() == {
        "pending": 0, "paid": 0, "fulfilled": 0, "cancelled": 0, "refunded": 0,
    }


def test_sales_by_status_counts(reports_service, orderbook):
    assert reports_service.sales_by_status() == {
        "pending": 1, "paid": 1, "fulfilled": 1, "cancelled": 1, "refunded": 1,
    }


# ----------------------------------------------------------------------
# top_products
# ----------------------------------------------------------------------

def test_top_products_empty(reports_service):
    assert reports_service.top_products() == []


def test_top_products_ordering_by_revenue(reports_service, orderbook,
                                          kettle_id, bottle_id):
    rows = reports_service.top_products()
    # Revenue orders only: kettle 1 x 54.99 (paid), bottle 2 x 27.99
    # (fulfilled). Kettle revenue 54.99 > bottle 55.98? No: 55.98 > 54.99.
    assert [r["product_id"] for r in rows] == [bottle_id, kettle_id]
    assert rows[0]["units"] == 2
    assert rows[0]["revenue"] == "55.98"
    assert rows[1]["units"] == 1
    assert rows[1]["revenue"] == "54.99"


def test_top_products_excludes_non_revenue_orders(reports_service, orderbook,
                                                  kettle_id):
    rows = reports_service.top_products()
    kettle_row = next(r for r in rows if r["product_id"] == kettle_id)
    # Cancelled (1) and refunded (2) kettle units must not count.
    assert kettle_row["units"] == 1


def test_top_products_respects_n(reports_service, orderbook):
    rows = reports_service.top_products(1)
    assert len(rows) == 1


def test_top_products_zero_n(reports_service, orderbook):
    assert reports_service.top_products(0) == []


def test_top_products_denormalised_name(reports_service, orderbook,
                                        bottle_id):
    rows = reports_service.top_products()
    assert rows[0]["name"] == "Summit Insulated Bottle 1L"


# ----------------------------------------------------------------------
# customer_lifetime_value
# ----------------------------------------------------------------------

def test_customer_lifetime_value_excludes_refunded(reports_service, orderbook,
                                                   noah_id):
    expected = orderbook["paid"].grand_total.add(
        orderbook["fulfilled"].grand_total)
    assert reports_service.customer_lifetime_value(noah_id) \
        == expected.to_decimal_string()


def test_customer_lifetime_value_excludes_pending_and_cancelled(
        reports_service, orderbook, liam_id):
    # Liam only has a pending and a cancelled order.
    assert reports_service.customer_lifetime_value(liam_id) == "0.00"


def test_customer_lifetime_value_no_orders(reports_service, seeded_store):
    ava = customer_id_for_email(seeded_store, "ava.novak@example.com")
    assert reports_service.customer_lifetime_value(ava) == "0.00"
