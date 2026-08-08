"""Route handler modules, one per resource.

Every handler is a module-level function with the signature::

    handler(service, request: Request) -> Response

where ``service`` is the collaborator the ``Api`` route table bound to
the route (a service instance, or a repository for direct lookups).
Handlers validate input, delegate to the service, and serialize domain
entities with the persistence serializers.
"""

from storefront.api.handlers import carts, customers, orders, products, reports

__all__ = ["carts", "customers", "orders", "products", "reports"]
