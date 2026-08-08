"""Handlers for the /orders routes (checkout and fulfilment lifecycle)."""

from __future__ import annotations

from storefront.api.request import Request
from storefront.api.response import Response, created, ok
from storefront.domain.errors import ValidationError
from storefront.persistence.serializers import serialize_order, serialize_shipment


def _require_body(request: Request) -> dict:
    """Return the request body, raising if it is missing."""
    if request.body is None:
        raise ValidationError("Request body is required.")
    return request.body


def _require_field(body: dict, name: str):
    """Return ``body[name]``, raising a clear error when absent or null."""
    value = body.get(name)
    if value is None:
        raise ValidationError("Missing required field '%s'." % name)
    return value


def place_order(orders, request: Request) -> Response:
    """POST /orders — convert a cart into a placed order.

    Body: ``{"customer_id", "cart_id"}`` plus optional
    ``"discount_code"`` and ``"address_index"`` (which shipping address
    of the customer to use, default 0). Returns 201 with the order.
    """
    body = _require_body(request)
    customer_id = _require_field(body, "customer_id")
    cart_id = _require_field(body, "cart_id")
    discount_code = body.get("discount_code")
    address_index = body.get("address_index", 0)
    if isinstance(address_index, bool) or not isinstance(address_index, int):
        raise ValidationError("Field 'address_index' must be an integer.")

    order = orders.place_order(
        customer_id,
        cart_id,
        discount_code=discount_code,
        address_index=address_index,
    )
    return created(serialize_order(order))


def pay_order(orders, request: Request) -> Response:
    """POST /orders/{order_id}/pay — capture payment for a placed order.

    Optional body ``{"method": str}`` selects the payment method
    (default ``"card"``). Paying an order that is not payable raises
    ``IllegalStateError`` (409) in the service.
    """
    body = request.body or {}
    method = body.get("method", "card")
    order = orders.pay_order(request.params["order_id"], method=method)
    return ok(serialize_order(order))


def cancel_order(orders, request: Request) -> Response:
    """POST /orders/{order_id}/cancel — cancel an order before shipment."""
    order = orders.cancel_order(request.params["order_id"])
    return ok(serialize_order(order))


def fulfill_order(orders, request: Request) -> Response:
    """POST /orders/{order_id}/fulfill — ship a paid order.

    Optional body ``{"carrier": str}`` (default ``"UPS"``). Returns the
    created shipment rather than the order.
    """
    body = request.body or {}
    carrier = body.get("carrier", "UPS")
    shipment = orders.fulfill_order(request.params["order_id"], carrier=carrier)
    return ok(serialize_shipment(shipment))


def get_order(orders, request: Request) -> Response:
    """GET /orders/{order_id} — fetch a single order."""
    order = orders.get_order(request.params["order_id"])
    return ok(serialize_order(order))


def order_summary(orders, request: Request) -> Response:
    """GET /orders/{order_id}/summary — totals breakdown for an order.

    The service returns a JSON-safe dict (subtotal, discount, tax,
    shipping, total) which is passed through unchanged.
    """
    summary = orders.order_totals_summary(request.params["order_id"])
    return ok(summary)


def list_customer_orders(orders, request: Request) -> Response:
    """GET /customers/{customer_id}/orders — a customer's order history."""
    customer_id = request.params["customer_id"]
    history = orders.list_orders_for_customer(customer_id)
    return ok(
        {
            "customer_id": customer_id,
            "orders": [serialize_order(order) for order in history],
        }
    )
