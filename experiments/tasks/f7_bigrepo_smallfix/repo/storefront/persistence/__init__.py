"""Persistence layer for the alpha_storefront application.

This package provides an in-memory storage backend together with the
serialization and repository machinery required to persist domain
entities.  It is intentionally structured the way a small production
service would be:

``store``
    A generic table/key/record store (:class:`InMemoryStore`) that knows
    nothing about the domain.  It only handles plain, JSON-safe dicts.

``serializers``
    Explicit, per-field converters between domain entities and their
    stored record representation.  Money values and timestamps are
    normalised to portable string forms.

``repositories``
    Entity-oriented data-access objects layered on top of the store and
    the serializers, including domain-specific finder methods.

``seed``
    Deterministic sample-data loading used by demos and tests.
"""

from storefront.persistence.store import InMemoryStore, TABLES
from storefront.persistence.repositories import (
    CartRepository,
    CustomerRepository,
    DiscountRepository,
    InventoryRecords,
    OrderRepository,
    PaymentRepository,
    ProductRepository,
    Repository,
    ShipmentRepository,
)
from storefront.persistence.seed import seed_store

__all__ = [
    "InMemoryStore",
    "TABLES",
    "Repository",
    "ProductRepository",
    "CustomerRepository",
    "CartRepository",
    "OrderRepository",
    "PaymentRepository",
    "ShipmentRepository",
    "DiscountRepository",
    "InventoryRecords",
    "seed_store",
]
