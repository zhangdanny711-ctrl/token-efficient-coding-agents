"""Handlers for the /products routes."""

from __future__ import annotations

from storefront.api.request import Request
from storefront.api.response import Response, ok
from storefront.domain.errors import ValidationError
from storefront.persistence.serializers import serialize_product


def list_products(catalog, request: Request) -> Response:
    """GET /products — list catalog products.

    Supports mutually exclusive filters via query parameters:

    * ``category`` — exact category match via ``list_by_category``.
    * ``q`` — free-text search via ``search``.

    With neither parameter, every active product is listed via
    ``list_active``.
    """
    category = request.params.get("category")
    query = request.params.get("q")
    if category is not None and query is not None:
        raise ValidationError("Provide either 'category' or 'q', not both.")

    if category is not None:
        products = catalog.list_by_category(category)
    elif query is not None:
        products = catalog.search(query)
    else:
        products = catalog.list_active()

    return ok({"products": [serialize_product(p) for p in products]})


def get_product(product_repo, request: Request) -> Response:
    """GET /products/{product_id} — fetch a single product.

    Bound to a ``ProductRepository`` rather than the catalog service;
    ``repo.get`` raises ``NotFoundError`` for unknown ids, which the
    middleware maps to a 404.
    """
    product_id = request.params["product_id"]
    product = product_repo.get(product_id)
    return ok(serialize_product(product))


def deactivate_product(catalog, request: Request) -> Response:
    """POST /products/{product_id}/deactivate — remove a product from sale.

    Deactivated products stay in the catalog for reporting but no longer
    appear in listings and cannot be added to carts.
    """
    product_id = request.params["product_id"]
    catalog.deactivate(product_id)
    return ok({"product_id": product_id, "active": False})
