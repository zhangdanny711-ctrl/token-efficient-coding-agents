"""Handlers for the /carts routes."""

from __future__ import annotations

from storefront.api.request import Request
from storefront.api.response import Response, created, no_content, ok
from storefront.domain.errors import ValidationError
from storefront.persistence.serializers import serialize_cart


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


def _parse_quantity(body: dict) -> int:
    """Extract and validate the ``quantity`` field of a cart item body."""
    raw = _require_field(body, "quantity")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValidationError("Field 'quantity' must be an integer.")
    return raw


def create_cart(carts, request: Request) -> Response:
    """POST /carts — open a new cart for a customer.

    Body: ``{"customer_id": str}``. Returns 201 with the empty cart.
    """
    body = _require_body(request)
    customer_id = _require_field(body, "customer_id")
    cart = carts.create_cart(customer_id)
    return created(serialize_cart(cart))


def get_cart(carts, request: Request) -> Response:
    """GET /carts/{cart_id} — fetch a cart with its line items."""
    cart = carts.get_cart(request.params["cart_id"])
    return ok(serialize_cart(cart))


def add_item(carts, request: Request) -> Response:
    """POST /carts/{cart_id}/items — add (or top up) a product in the cart.

    Body: ``{"product_id": str, "quantity": int}``. Stock and product
    activity checks happen in the service; failures surface as 404/409.
    Returns the updated cart.
    """
    body = _require_body(request)
    product_id = _require_field(body, "product_id")
    quantity = _parse_quantity(body)
    cart = carts.add_item(request.params["cart_id"], product_id, quantity)
    return ok(serialize_cart(cart))


def remove_item(carts, request: Request) -> Response:
    """DELETE /carts/{cart_id}/items/{product_id} — drop a line item.

    Returns 204; the caller can re-fetch the cart for its new state.
    """
    carts.remove_item(request.params["cart_id"], request.params["product_id"])
    return no_content()
