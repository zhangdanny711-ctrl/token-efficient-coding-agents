"""Shared fixtures and helpers for the alpha_storefront test suite."""

import pytest

from storefront.api import Api
from storefront.persistence import InMemoryStore, seed_store
from storefront.persistence.repositories import DiscountRepository
from storefront.services import (
    CartService,
    CatalogService,
    CustomerService,
    OrderService,
    PricingService,
    ReportsService,
)
from storefront.utils.clock import FixedClock
from storefront.utils.ids import make_sequences


# ----------------------------------------------------------------------
# Helpers to resolve seeded ids from the store (importable by tests)
# ----------------------------------------------------------------------

def product_id_for_sku(store, sku):
    """Return the seeded product id for ``sku`` via a raw store scan."""
    for record in store.all("products"):
        if record["sku"] == sku:
            return record["product_id"]
    raise AssertionError("no seeded product with sku %r" % (sku,))


def customer_id_for_email(store, email):
    """Return the seeded customer id for ``email`` via a raw store scan."""
    for record in store.all("customers"):
        if record["email"] == email:
            return record["customer_id"]
    raise AssertionError("no seeded customer with email %r" % (email,))


# ----------------------------------------------------------------------
# Core fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def clock():
    return FixedClock("2026-01-15T09:00:00")


@pytest.fixture
def sequences():
    return make_sequences()


@pytest.fixture
def seeded_store(store, clock, sequences):
    seed_store(store, clock, sequences)
    return store


# ----------------------------------------------------------------------
# Service fixtures (all built over the seeded store)
# ----------------------------------------------------------------------

@pytest.fixture
def cart_service(seeded_store, clock, sequences):
    return CartService(seeded_store, clock, sequences)


@pytest.fixture
def order_service(seeded_store, clock, sequences):
    return OrderService(seeded_store, clock, sequences)


@pytest.fixture
def catalog_service(seeded_store):
    return CatalogService(seeded_store)


@pytest.fixture
def customer_service(seeded_store, sequences):
    return CustomerService(seeded_store, sequences)


@pytest.fixture
def reports_service(seeded_store):
    return ReportsService(seeded_store)


@pytest.fixture
def pricing_service(seeded_store):
    return PricingService(DiscountRepository(seeded_store))


@pytest.fixture
def api(catalog_service, cart_service, order_service, customer_service,
        reports_service, seeded_store):
    return Api(
        catalog=catalog_service,
        carts=cart_service,
        orders=order_service,
        customers=customer_service,
        reports=reports_service,
        store=seeded_store,
    )
