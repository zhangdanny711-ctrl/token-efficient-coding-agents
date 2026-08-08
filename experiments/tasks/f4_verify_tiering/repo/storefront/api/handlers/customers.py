"""Handlers for the /customers routes."""

from __future__ import annotations

from storefront.api.request import Request
from storefront.api.response import Response, created, ok
from storefront.domain.errors import ValidationError
from storefront.domain.models import Address
from storefront.persistence.serializers import serialize_customer

_ADDRESS_REQUIRED = ("street", "city", "state", "postal_code")


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


def parse_address(raw) -> Address:
    """Build an ``Address`` from a request-body dict.

    Requires street, city, state and postal_code; ``country`` is
    optional and defaults to ``"US"``.
    """
    if not isinstance(raw, dict):
        raise ValidationError("Field 'address' must be an object.")
    missing = [key for key in _ADDRESS_REQUIRED if not raw.get(key)]
    if missing:
        raise ValidationError(
            "Address is missing required field(s): %s." % ", ".join(missing)
        )
    return Address(
        street=raw["street"],
        city=raw["city"],
        state=raw["state"],
        postal_code=raw["postal_code"],
        country=raw.get("country", "US"),
    )


def register_customer(customers, request: Request) -> Response:
    """POST /customers — register a new customer account.

    Body: ``{"email": str, "name": str, "address": {...}}`` where the
    address object holds the customer's first shipping address. Email
    format and uniqueness are enforced by the service. Returns 201.
    """
    body = _require_body(request)
    email = _require_field(body, "email")
    name = _require_field(body, "name")
    address = parse_address(_require_field(body, "address"))
    customer = customers.register_customer(email, name, address)
    return created(serialize_customer(customer))


def get_customer(customers, request: Request) -> Response:
    """GET /customers/{customer_id} — fetch a customer profile."""
    customer = customers.get_customer(request.params["customer_id"])
    return ok(serialize_customer(customer))
