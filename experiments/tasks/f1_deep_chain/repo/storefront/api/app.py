"""The Api front controller: route table and request dispatch."""

from __future__ import annotations

import functools

from storefront.api import middleware
from storefront.api.handlers import carts as cart_handlers
from storefront.api.handlers import customers as customer_handlers
from storefront.api.handlers import orders as order_handlers
from storefront.api.handlers import products as product_handlers
from storefront.api.handlers import reports as report_handlers
from storefront.api.request import Request
from storefront.api.response import Response, error
from storefront.persistence.repositories import ProductRepository
from storefront.utils.logging import get_logger


def _split(path: str) -> list[str]:
    """Split a path into segments, ignoring leading/trailing slashes."""
    return [segment for segment in path.strip("/").split("/") if segment]


def _match(template: str, path: str) -> dict | None:
    """Match ``path`` against ``template``, returning captured params.

    Template segments wrapped in braces (``"{order_id}"``) capture the
    corresponding path segment; every other segment must match exactly.
    Returns ``None`` when the path does not fit the template.
    """
    template_parts = _split(template)
    path_parts = _split(path)
    if len(template_parts) != len(path_parts):
        return None
    params: dict = {}
    for expected, actual in zip(template_parts, path_parts):
        if expected.startswith("{") and expected.endswith("}"):
            params[expected[1:-1]] = actual
        elif expected != actual:
            return None
    return params


class Api:
    """Dispatches ``Request`` objects to handler functions.

    The route table binds each (method, path template) pair to a
    handler function and the service it operates on. ``dispatch``
    resolves the route, merges captured path parameters into
    ``request.params``, and runs the handler under the error-handling
    and logging middleware.
    """

    def __init__(self, catalog, carts, orders, customers, reports, store):
        self.catalog = catalog
        self.carts = carts
        self.orders = orders
        self.customers = customers
        self.reports = reports
        self.store = store
        self.product_repo = ProductRepository(store)
        self.logger = get_logger("storefront.api")
        self.routes = self._build_routes()

    def _build_routes(self) -> list[tuple[str, str, object, object]]:
        """Return the route table: (method, template, handler_fn, service)."""
        return [
            # Catalog
            ("GET", "/products", product_handlers.list_products, self.catalog),
            ("GET", "/products/{product_id}", product_handlers.get_product, self.product_repo),
            ("POST", "/products/{product_id}/deactivate", product_handlers.deactivate_product, self.catalog),
            # Carts
            ("POST", "/carts", cart_handlers.create_cart, self.carts),
            ("GET", "/carts/{cart_id}", cart_handlers.get_cart, self.carts),
            ("POST", "/carts/{cart_id}/items", cart_handlers.add_item, self.carts),
            ("DELETE", "/carts/{cart_id}/items/{product_id}", cart_handlers.remove_item, self.carts),
            # Orders
            ("POST", "/orders", order_handlers.place_order, self.orders),
            ("POST", "/orders/{order_id}/pay", order_handlers.pay_order, self.orders),
            ("POST", "/orders/{order_id}/cancel", order_handlers.cancel_order, self.orders),
            ("POST", "/orders/{order_id}/fulfill", order_handlers.fulfill_order, self.orders),
            ("GET", "/orders/{order_id}", order_handlers.get_order, self.orders),
            ("GET", "/orders/{order_id}/summary", order_handlers.order_summary, self.orders),
            # Customers
            ("POST", "/customers", customer_handlers.register_customer, self.customers),
            ("GET", "/customers/{customer_id}", customer_handlers.get_customer, self.customers),
            ("GET", "/customers/{customer_id}/orders", order_handlers.list_customer_orders, self.orders),
            # Reports
            ("GET", "/reports/revenue", report_handlers.revenue, self.reports),
            ("GET", "/reports/top-products", report_handlers.top_products, self.reports),
            ("GET", "/reports/sales-by-status", report_handlers.sales_by_status, self.reports),
        ]

    def _resolve(self, request: Request):
        """Find the route for a request.

        Returns ``(handler_fn, service, path_params)`` on a match, or
        ``None`` when no route fits. Static segments beat captures
        implicitly because more specific templates are listed first
        (e.g. ``/orders/{order_id}/summary`` vs ``/orders/{order_id}``
        differ in length, so ordering is not load-bearing today).
        """
        method = request.method.upper()
        for route_method, template, handler_fn, service in self.routes:
            if route_method != method:
                continue
            params = _match(template, request.path)
            if params is not None:
                return handler_fn, service, params
        return None

    def dispatch(self, request: Request) -> Response:
        """Route a request to its handler and return the Response.

        Unknown method/path combinations yield a 404 error response.
        Handlers run wrapped in error handling (domain errors to 4xx,
        unexpected errors to 500) and per-request logging.
        """
        resolved = self._resolve(request)
        if resolved is None:
            self.logger.warning(
                "%s %s -> 404 (no route)", request.method, request.path
            )
            return error(
                404,
                "No route for %s %s." % (request.method, request.path),
                detail="RouteNotFound",
            )

        handler_fn, service, path_params = resolved
        request.params.update(path_params)

        bound = functools.partial(handler_fn, service)
        pipeline = middleware.apply_middleware(
            bound,
            middleware.with_error_handling,
            functools.partial(middleware.with_logging, self.logger),
        )
        return pipeline(request)
