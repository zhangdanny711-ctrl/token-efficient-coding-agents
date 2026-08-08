"""Service layer for the alpha_storefront application.

This package hosts the application services that orchestrate the domain
model, persistence repositories, and utility helpers into cohesive
use-case oriented operations.  Each module owns one bounded set of
responsibilities:

- :mod:`storefront.services.inventory` -- stock levels and reservations.
- :mod:`storefront.services.pricing` -- quotes, discounts, tax, shipping.
- :mod:`storefront.services.carts` -- shopping cart lifecycle.
- :mod:`storefront.services.orders` -- order placement and state machine.
- :mod:`storefront.services.customers` -- customer registration/profile.
- :mod:`storefront.services.catalog` -- product catalog management.
- :mod:`storefront.services.reports` -- read-only reporting queries.
"""

from storefront.services.inventory import InventoryService
from storefront.services.pricing import PriceBreakdown, PricingService
from storefront.services.carts import CartService
from storefront.services.orders import OrderService
from storefront.services.customers import CustomerService
from storefront.services.catalog import CatalogService
from storefront.services.reports import ReportsService

__all__ = [
    "InventoryService",
    "PriceBreakdown",
    "PricingService",
    "CartService",
    "OrderService",
    "CustomerService",
    "CatalogService",
    "ReportsService",
]
