"""Tests for the API layer: routing, handlers, and error mapping."""

import pytest

from storefront.api import make_request

from tests.conftest import customer_id_for_email, product_id_for_sku


@pytest.fixture
def noah_id(seeded_store):
    return customer_id_for_email(seeded_store, "noah.kim@example.com")


@pytest.fixture
def kettle_id(seeded_store):
    return product_id_for_sku(seeded_store, "KTCH-2002")


@pytest.fixture
def monitor_id(seeded_store):
    return product_id_for_sku(seeded_store, "ELEC-1003")  # low stock


def create_cart(api, customer_id):
    response = api.dispatch(make_request(
        "POST", "/carts", body={"customer_id": customer_id}))
    assert response.status == 201
    return response.body["cart_id"]


def add_item(api, cart_id, product_id, qty):
    return api.dispatch(make_request(
        "POST", "/carts/%s/items" % cart_id,
        body={"product_id": product_id, "quantity": qty}))


def place_order(api, customer_id, cart_id, **extra):
    body = {"customer_id": customer_id, "cart_id": cart_id}
    body.update(extra)
    return api.dispatch(make_request("POST", "/orders", body=body))


# ----------------------------------------------------------------------
# routing
# ----------------------------------------------------------------------

def test_unmatched_route_404(api):
    response = api.dispatch(make_request("GET", "/nope"))
    assert response.status == 404
    assert response.body["error"] == "RouteNotFound"


def test_unmatched_method_404(api):
    response = api.dispatch(make_request("PATCH", "/products"))
    assert response.status == 404


def test_path_params_captured(api, kettle_id):
    response = api.dispatch(make_request("GET", "/products/%s" % kettle_id))
    assert response.status == 200
    assert response.body["product_id"] == kettle_id


def test_trailing_slash_tolerated(api):
    response = api.dispatch(make_request("GET", "/products/"))
    assert response.status == 200


# ----------------------------------------------------------------------
# products
# ----------------------------------------------------------------------

def test_list_products(api):
    response = api.dispatch(make_request("GET", "/products"))
    assert response.status == 200
    assert len(response.body["products"]) == 12


def test_list_products_by_category(api):
    response = api.dispatch(make_request("GET", "/products",
                                         category="kitchen"))
    assert response.status == 200
    assert len(response.body["products"]) == 3


def test_search_products(api):
    response = api.dispatch(make_request("GET", "/products", q="kettle"))
    assert response.status == 200
    skus = [p["sku"] for p in response.body["products"]]
    assert skus == ["KTCH-2002"]


def test_search_products_by_tag(api):
    response = api.dispatch(make_request("GET", "/products", q="camping"))
    assert [p["sku"] for p in response.body["products"]] == ["OUTD-3001"]


def test_products_both_filters_rejected(api):
    response = api.dispatch(make_request("GET", "/products",
                                         q="kettle", category="kitchen"))
    assert response.status == 400
    assert response.body["error"] == "ValidationError"


def test_get_product_404(api):
    response = api.dispatch(make_request("GET", "/products/prd-999999"))
    assert response.status == 404
    assert response.body["error"] == "NotFoundError"


def test_deactivate_product(api, kettle_id):
    response = api.dispatch(make_request(
        "POST", "/products/%s/deactivate" % kettle_id))
    assert response.status == 200
    assert response.body == {"product_id": kettle_id, "active": False}
    listed = api.dispatch(make_request("GET", "/products"))
    assert all(p["product_id"] != kettle_id for p in listed.body["products"])


# ----------------------------------------------------------------------
# carts
# ----------------------------------------------------------------------

def test_create_cart_201(api, noah_id):
    response = api.dispatch(make_request(
        "POST", "/carts", body={"customer_id": noah_id}))
    assert response.status == 201
    assert response.body["customer_id"] == noah_id
    assert response.body["items"] == []


def test_create_cart_missing_body_400(api):
    response = api.dispatch(make_request("POST", "/carts"))
    assert response.status == 400


def test_create_cart_missing_field_400(api):
    response = api.dispatch(make_request("POST", "/carts", body={}))
    assert response.status == 400
    assert "customer_id" in response.body["message"]


def test_create_cart_unknown_customer_404(api):
    response = api.dispatch(make_request(
        "POST", "/carts", body={"customer_id": "cus-999999"}))
    assert response.status == 404


def test_add_item_and_get_cart(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    response = add_item(api, cart_id, kettle_id, 2)
    assert response.status == 200
    assert response.body["items"][0]["quantity"] == 2
    assert response.body["items"][0]["unit_price"]["amount"] == "54.99"

    fetched = api.dispatch(make_request("GET", "/carts/%s" % cart_id))
    assert fetched.status == 200
    assert fetched.body == response.body


def test_add_item_non_integer_quantity_400(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    response = api.dispatch(make_request(
        "POST", "/carts/%s/items" % cart_id,
        body={"product_id": kettle_id, "quantity": "2"}))
    assert response.status == 400


def test_remove_item_204(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 1)
    response = api.dispatch(make_request(
        "DELETE", "/carts/%s/items/%s" % (cart_id, kettle_id)))
    assert response.status == 204
    assert response.body == {}


def test_remove_absent_item_404(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    response = api.dispatch(make_request(
        "DELETE", "/carts/%s/items/%s" % (cart_id, kettle_id)))
    assert response.status == 404


# ----------------------------------------------------------------------
# orders
# ----------------------------------------------------------------------

def test_place_order_201(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 1)
    response = place_order(api, noah_id, cart_id)
    assert response.status == 201
    assert response.body["status"] == "pending"
    assert response.body["subtotal"]["amount"] == "54.99"
    assert response.body["lines"][0]["sku"] == "KTCH-2002"


def test_place_order_with_discount(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 2)
    response = place_order(api, noah_id, cart_id, discount_code="SAVE15")
    assert response.status == 201
    assert response.body["discount_total"]["amount"] != "0.00"


def test_place_order_unknown_discount_400(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 1)
    response = place_order(api, noah_id, cart_id, discount_code="BOGUS")
    assert response.status == 400
    assert response.body["error"] == "DiscountError"


def test_place_order_empty_cart_400(api, noah_id):
    cart_id = create_cart(api, noah_id)
    response = place_order(api, noah_id, cart_id)
    assert response.status == 400


def test_place_order_out_of_stock_409(api, noah_id, monitor_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, monitor_id, 3)
    response = place_order(api, noah_id, cart_id)
    assert response.status == 409
    assert response.body["error"] == "OutOfStockError"


def test_pay_order(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 1)
    order_id = place_order(api, noah_id, cart_id).body["order_id"]
    response = api.dispatch(make_request(
        "POST", "/orders/%s/pay" % order_id, body={"method": "paypal"}))
    assert response.status == 200
    assert response.body["status"] == "paid"


def test_pay_order_twice_409(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 1)
    order_id = place_order(api, noah_id, cart_id).body["order_id"]
    api.dispatch(make_request("POST", "/orders/%s/pay" % order_id))
    response = api.dispatch(make_request("POST", "/orders/%s/pay" % order_id))
    assert response.status == 409
    assert response.body["error"] == "IllegalStateError"


def test_fulfill_order_returns_shipment(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 1)
    order_id = place_order(api, noah_id, cart_id).body["order_id"]
    api.dispatch(make_request("POST", "/orders/%s/pay" % order_id))
    response = api.dispatch(make_request(
        "POST", "/orders/%s/fulfill" % order_id, body={"carrier": "DHL"}))
    assert response.status == 200
    assert response.body["carrier"] == "DHL"
    assert response.body["status"] == "queued"


def test_cancel_order(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 1)
    order_id = place_order(api, noah_id, cart_id).body["order_id"]
    response = api.dispatch(make_request(
        "POST", "/orders/%s/cancel" % order_id))
    assert response.status == 200
    assert response.body["status"] == "cancelled"


def test_get_order_and_summary(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 1)
    placed = place_order(api, noah_id, cart_id).body
    order_id = placed["order_id"]

    got = api.dispatch(make_request("GET", "/orders/%s" % order_id))
    assert got.status == 200
    assert got.body == placed

    summary = api.dispatch(make_request("GET", "/orders/%s/summary" % order_id))
    assert summary.status == 200
    assert summary.body["order_id"] == order_id
    assert summary.body["payment_status"] == "pending"
    assert summary.body["grand_total"] == placed["grand_total"]["amount"]


def test_get_order_404(api):
    response = api.dispatch(make_request("GET", "/orders/ord-999999"))
    assert response.status == 404


def test_list_customer_orders(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 1)
    order_id = place_order(api, noah_id, cart_id).body["order_id"]
    response = api.dispatch(make_request(
        "GET", "/customers/%s/orders" % noah_id))
    assert response.status == 200
    assert response.body["customer_id"] == noah_id
    assert [o["order_id"] for o in response.body["orders"]] == [order_id]


# ----------------------------------------------------------------------
# customers
# ----------------------------------------------------------------------

def test_register_customer_201(api):
    response = api.dispatch(make_request("POST", "/customers", body={
        "email": "new.person@example.com",
        "name": "New Person",
        "address": {"street": "1 Way", "city": "Denver", "state": "CO",
                    "postal_code": "80202"},
    }))
    assert response.status == 201
    assert response.body["email"] == "new.person@example.com"
    assert response.body["loyalty_tier"] == "standard"


def test_register_duplicate_email_400(api):
    response = api.dispatch(make_request("POST", "/customers", body={
        "email": "maya.chen@example.com",
        "name": "Imposter",
        "address": {"street": "1 Way", "city": "Denver", "state": "CO",
                    "postal_code": "80202"},
    }))
    assert response.status == 400


def test_register_incomplete_address_400(api):
    response = api.dispatch(make_request("POST", "/customers", body={
        "email": "x@example.com", "name": "X",
        "address": {"street": "1 Way"},
    }))
    assert response.status == 400
    assert "city" in response.body["message"]


def test_get_customer(api, noah_id):
    response = api.dispatch(make_request("GET", "/customers/%s" % noah_id))
    assert response.status == 200
    assert response.body["name"] == "Noah Kim"


# ----------------------------------------------------------------------
# reports
# ----------------------------------------------------------------------

def test_reports_revenue(api, noah_id, kettle_id):
    cart_id = create_cart(api, noah_id)
    add_item(api, cart_id, kettle_id, 1)
    order_id = place_order(api, noah_id, cart_id).body["order_id"]
    api.dispatch(make_request("POST", "/orders/%s/pay" % order_id))
    response = api.dispatch(make_request("GET", "/reports/revenue"))
    assert response.status == 200
    assert response.body["order_count"] == 1


def test_reports_sales_by_status(api):
    response = api.dispatch(make_request("GET", "/reports/sales-by-status"))
    assert response.status == 200
    assert response.body["sales_by_status"]["pending"] == 0


def test_reports_top_products_with_n(api):
    response = api.dispatch(make_request("GET", "/reports/top-products", n="3"))
    assert response.status == 200
    assert response.body["top_products"] == []


def test_reports_top_products_bad_n_400(api):
    response = api.dispatch(make_request("GET", "/reports/top-products",
                                         n="lots"))
    assert response.status == 400
    response = api.dispatch(make_request("GET", "/reports/top-products", n="0"))
    assert response.status == 400
