"""Tests for storefront.services.carts.CartService."""

import pytest

from storefront.domain.errors import NotFoundError, ValidationError
from storefront.domain.money import Money

from tests.conftest import customer_id_for_email, product_id_for_sku


@pytest.fixture
def customer_id(seeded_store):
    return customer_id_for_email(seeded_store, "liam.osullivan@example.com")


@pytest.fixture
def earbuds_id(seeded_store):
    return product_id_for_sku(seeded_store, "ELEC-1001")


@pytest.fixture
def kettle_id(seeded_store):
    return product_id_for_sku(seeded_store, "KTCH-2002")


@pytest.fixture
def cart(cart_service, customer_id):
    return cart_service.create_cart(customer_id)


# ----------------------------------------------------------------------
# lifecycle
# ----------------------------------------------------------------------

def test_create_cart(cart_service, customer_id, clock):
    cart = cart_service.create_cart(customer_id)
    assert cart.customer_id == customer_id
    assert cart.items == []
    assert cart.created_at == clock.now()
    assert cart.cart_id.startswith("crt-")


def test_create_cart_persists(cart_service, cart):
    assert cart_service.get_cart(cart.cart_id).cart_id == cart.cart_id


def test_create_cart_unknown_customer_rejected(cart_service):
    with pytest.raises(NotFoundError):
        cart_service.create_cart("cus-999999")


def test_get_cart_missing(cart_service):
    with pytest.raises(NotFoundError):
        cart_service.get_cart("crt-999999")


# ----------------------------------------------------------------------
# add_item
# ----------------------------------------------------------------------

def test_add_item_snapshots_price(cart_service, cart, earbuds_id):
    updated = cart_service.add_item(cart.cart_id, earbuds_id, 2)
    assert len(updated.items) == 1
    item = updated.items[0]
    assert item.quantity == 2
    assert item.unit_price == Money(7999)


def test_add_item_merges_quantities(cart_service, cart, earbuds_id):
    cart_service.add_item(cart.cart_id, earbuds_id, 2)
    updated = cart_service.add_item(cart.cart_id, earbuds_id, 3)
    assert len(updated.items) == 1
    assert updated.items[0].quantity == 5


def test_add_item_merge_keeps_original_snapshot(cart_service, cart, earbuds_id,
                                                catalog_service, seeded_store):
    cart_service.add_item(cart.cart_id, earbuds_id, 1)
    # Simulate a catalog price change between adds.
    from storefront.persistence.repositories import ProductRepository
    repo = ProductRepository(seeded_store)
    product = repo.get(earbuds_id)
    product.price = Money(9999)
    repo.update(product)
    updated = cart_service.add_item(cart.cart_id, earbuds_id, 1)
    assert updated.items[0].unit_price == Money(7999)


def test_add_item_two_products(cart_service, cart, earbuds_id, kettle_id):
    cart_service.add_item(cart.cart_id, earbuds_id, 1)
    updated = cart_service.add_item(cart.cart_id, kettle_id, 2)
    assert len(updated.items) == 2
    assert updated.total_quantity() == 3


def test_add_item_inactive_product_rejected(cart_service, cart, earbuds_id,
                                            catalog_service):
    catalog_service.deactivate(earbuds_id)
    with pytest.raises(ValidationError, match="inactive"):
        cart_service.add_item(cart.cart_id, earbuds_id, 1)


def test_add_item_unknown_product(cart_service, cart):
    with pytest.raises(NotFoundError):
        cart_service.add_item(cart.cart_id, "prd-999999", 1)


def test_add_item_invalid_qty(cart_service, cart, earbuds_id):
    with pytest.raises(ValidationError):
        cart_service.add_item(cart.cart_id, earbuds_id, 0)
    with pytest.raises(ValidationError):
        cart_service.add_item(cart.cart_id, earbuds_id, -2)


# ----------------------------------------------------------------------
# set_quantity / remove / clear
# ----------------------------------------------------------------------

def test_set_quantity(cart_service, cart, earbuds_id):
    cart_service.add_item(cart.cart_id, earbuds_id, 1)
    updated = cart_service.set_quantity(cart.cart_id, earbuds_id, 7)
    assert updated.items[0].quantity == 7


def test_set_quantity_zero_removes_line(cart_service, cart, earbuds_id,
                                         kettle_id):
    cart_service.add_item(cart.cart_id, earbuds_id, 1)
    cart_service.add_item(cart.cart_id, kettle_id, 1)
    updated = cart_service.set_quantity(cart.cart_id, earbuds_id, 0)
    assert updated.find_item(earbuds_id) is None
    assert updated.find_item(kettle_id) is not None


def test_set_quantity_negative_rejected(cart_service, cart, earbuds_id):
    cart_service.add_item(cart.cart_id, earbuds_id, 1)
    with pytest.raises(ValidationError):
        cart_service.set_quantity(cart.cart_id, earbuds_id, -1)


def test_set_quantity_absent_product_raises(cart_service, cart, earbuds_id):
    with pytest.raises(NotFoundError):
        cart_service.set_quantity(cart.cart_id, earbuds_id, 3)


def test_remove_item(cart_service, cart, earbuds_id):
    cart_service.add_item(cart.cart_id, earbuds_id, 1)
    updated = cart_service.remove_item(cart.cart_id, earbuds_id)
    assert updated.is_empty()


def test_remove_absent_item_raises(cart_service, cart, earbuds_id):
    with pytest.raises(NotFoundError):
        cart_service.remove_item(cart.cart_id, earbuds_id)


def test_clear_cart(cart_service, cart, earbuds_id, kettle_id):
    cart_service.add_item(cart.cart_id, earbuds_id, 1)
    cart_service.add_item(cart.cart_id, kettle_id, 2)
    cleared = cart_service.clear_cart(cart.cart_id)
    assert cleared.is_empty()
    assert cart_service.get_cart(cart.cart_id).is_empty()


# ----------------------------------------------------------------------
# queries
# ----------------------------------------------------------------------

def test_carts_for_customer(cart_service, customer_id):
    first = cart_service.create_cart(customer_id)
    second = cart_service.create_cart(customer_id)
    carts = cart_service.carts_for_customer(customer_id)
    assert [c.cart_id for c in carts] == [first.cart_id, second.cart_id]


def test_carts_for_customer_empty(cart_service, seeded_store):
    other = customer_id_for_email(seeded_store, "noah.kim@example.com")
    assert cart_service.carts_for_customer(other) == []
