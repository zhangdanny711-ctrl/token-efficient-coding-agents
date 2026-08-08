"""Handlers for the /reports routes (read-only analytics)."""

from __future__ import annotations

from storefront.api.request import Request
from storefront.api.response import Response, ok
from storefront.domain.errors import ValidationError


def revenue(reports, request: Request) -> Response:
    """GET /reports/revenue — aggregate revenue figures.

    The service returns a JSON-safe dict (gross, refunds, net and
    similar figures as decimal strings) which is passed through.
    """
    return ok(reports.revenue_summary())


def sales_by_status(reports, request: Request) -> Response:
    """GET /reports/sales-by-status — order counts grouped by status."""
    return ok({"sales_by_status": reports.sales_by_status()})


def top_products(reports, request: Request) -> Response:
    """GET /reports/top-products — best sellers by units sold.

    Optional query parameter ``n`` limits the number of rows; when it
    is omitted the service applies its own default. ``n`` arrives as a
    string when it comes from a query string, so both forms are accepted.
    """
    raw_n = request.params.get("n")
    if raw_n is None:
        rows = reports.top_products()
    else:
        try:
            n = int(raw_n)
        except (TypeError, ValueError):
            raise ValidationError("Query parameter 'n' must be an integer.")
        if n < 1:
            raise ValidationError("Query parameter 'n' must be positive.")
        rows = reports.top_products(n)
    return ok({"top_products": rows})
