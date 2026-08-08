"""Tests for storefront.persistence.repositories on the seeded store."""

import pytest

from storefront.domain.errors import NotFoundError, ValidationError
from storefront.domain.models import Product
from storefront.domain.money import Money
from storefront.persistence.repositories import (
    CustomerRepository,
    DiscountRepository,
    InventoryRecords,
    ProductRepository,
)

from tests.conftest import product_id_for_sku


@pytest.fixture
def products(seeded_store):
    return ProductRepository(seeded_store)


@pytest.fixture
def customers(seeded_store):
    return CustomerRepository(seeded_store)


@pytest.fixture
def discounts(seeded_store):
    return DiscountRepository(seeded_store)


@pytest.fixture
def inventory(seeded_store):
    return InventoryRecords(seeded_store)


# ----------------------------------------------------------------------
# generic CRUD via ProductRepository
# ----------------------------------------------------------------------

def test_list_seeded_products(products):
    assert len(products.list()) == 12


def test_get_returns_entity(products, seeded_store):
    pid = product_id_for_sku(seeded_store, "ELEC-1001")
    product = products.get(pid)
    assert isinstance(product, Product)
    assert product.name == "Aurora Wireless Earbuds"
    assert product.price == Money(7999)


def test_get_missing_raises(products):
    with pytest.raises(NotFoundError):
        products.get("prd-999999")


def test_add_and_exists(products):
    new = Product(product_id="prd-000099", sku="TEST-1", name="Test",
                  description="", price=Money(100), category="misc",
                  tags=[], weight_grams=10)
    assert not products.exists("prd-000099")
    products.add(new)
    assert products.exists("prd-000099")
    assert products.get("prd-000099") == new


def test_add_duplicate_key_raises(products, seeded_store):
    pid = product_id_for_sku(seeded_store, "ELEC-1001")
    duplicate = products.get(pid)
    with pytest.raises(ValidationError):
        products.add(duplicate)


def test_update_round_trips(products, seeded_store):
    pid = product_id_for_sku(seeded_store, "ELEC-1001")
    product = products.get(pid)
    product.active = False
    products.update(product)
    assert products.get(pid).active is False


def test_update_unknown_entity_raises(products):
    ghost = Product(product_id="prd-777777", sku="G", name="Ghost",
                    description="", price=Money(1), category="misc",
                    tags=[], weight_grams=1)
    with pytest.raises(NotFoundError):
        products.update(ghost)


def test_delete_removes(products, seeded_store):
    pid = product_id_for_sku(seeded_store, "OFFC-4003")
    products.delete(pid)
    assert not products.exists(pid)


# ----------------------------------------------------------------------
# product finders
# ----------------------------------------------------------------------

def test_find_by_sku(products):
    product = products.find_by_sku("KTCH-2002")
    assert product.name == "Brewline Pour-Over Kettle"


def test_find_by_sku_missing(products):
    with pytest.raises(NotFoundError):
        products.find_by_sku("NOPE-0000")


def test_list_by_category(products):
    kitchen = products.list_by_category("kitchen")
    assert len(kitchen) == 3
    assert all(p.category == "kitchen" for p in kitchen)


def test_list_active_excludes_deactivated(products, seeded_store):
    pid = product_id_for_sku(seeded_store, "ELEC-1001")
    product = products.get(pid)
    product.active = False
    products.update(product)
    active = products.list_active()
    assert len(active) == 11
    assert all(p.product_id != pid for p in active)


def test_search_name_case_insensitive(products):
    matches = products.search_name("KETTLE")
    assert [p.sku for p in matches] == ["KTCH-2002"]


# ----------------------------------------------------------------------
# customer finders
# ----------------------------------------------------------------------

def test_find_by_email_case_insensitive(customers):
    customer = customers.find_by_email("MAYA.CHEN@example.com")
    assert customer.name == "Maya Chen"
    assert customer.loyalty_tier == "gold"


def test_find_by_email_missing(customers):
    with pytest.raises(NotFoundError):
        customers.find_by_email("nobody@example.com")


def test_list_by_tier(customers):
    gold = customers.list_by_tier("gold")
    assert sorted(c.name for c in gold) == ["Ava Novak", "Maya Chen"]


def test_seeded_customer_addresses(customers):
    sofia = customers.find_by_email("sofia.ramirez@example.com")
    assert len(sofia.addresses) == 2
    assert sofia.primary_address().city == "Houston"


# ----------------------------------------------------------------------
# discount finders
# ----------------------------------------------------------------------

def test_find_by_code(discounts):
    d = discounts.find_by_code("SAVE15")
    assert d.kind == "percent"
    assert d.value == 15
    assert d.min_subtotal_cents == 5000


def test_find_by_code_missing(discounts):
    with pytest.raises(NotFoundError):
        discounts.find_by_code("BOGUS")


def test_list_active_discounts(discounts):
    active = discounts.list_active()
    assert sorted(d.code for d in active) == ["FIVER", "SAVE15", "WELCOME10"]


# ----------------------------------------------------------------------
# InventoryRecords
# ----------------------------------------------------------------------

def test_inventory_seeded_low_stock(inventory, seeded_store):
    pid = product_id_for_sku(seeded_store, "ELEC-1003")
    level = inventory.get_level(pid)
    assert level == {"product_id": pid, "available": 2, "reserved": 1}


def test_inventory_get_missing_raises(inventory):
    with pytest.raises(NotFoundError):
        inventory.get_level("prd-999999")


def test_inventory_set_level_insert_and_replace(inventory):
    inventory.set_level("prd-x", available=10)
    assert inventory.get_level("prd-x") == {
        "product_id": "prd-x", "available": 10, "reserved": 0}
    inventory.set_level("prd-x", available=5, reserved=2)
    assert inventory.get_level("prd-x") == {
        "product_id": "prd-x", "available": 5, "reserved": 2}


def test_inventory_update_level_partial(inventory, seeded_store):
    pid = product_id_for_sku(seeded_store, "ELEC-1002")
    updated = inventory.update_level(pid, reserved=7)
    assert updated["reserved"] == 7
    assert updated["available"] == 220  # untouched
    assert inventory.get_level(pid)["reserved"] == 7


def test_inventory_update_level_missing_raises(inventory):
    with pytest.raises(NotFoundError):
        inventory.update_level("prd-999999", available=1)
