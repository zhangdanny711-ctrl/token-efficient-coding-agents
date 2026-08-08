"""Tests for storefront.services.inventory.InventoryService."""

import pytest

from storefront.domain.errors import OutOfStockError, ValidationError
from storefront.services import InventoryService

from tests.conftest import product_id_for_sku


@pytest.fixture
def inventory(seeded_store):
    return InventoryService(seeded_store)


@pytest.fixture
def pid(seeded_store):
    # KTCH-2001 seeds at available=75, reserved=2.
    return product_id_for_sku(seeded_store, "KTCH-2001")


@pytest.fixture
def low_pid(seeded_store):
    # ELEC-1003 seeds at available=2, reserved=1.
    return product_id_for_sku(seeded_store, "ELEC-1003")


def test_available_and_reserved_queries(inventory, pid):
    assert inventory.available(pid) == 75
    assert inventory.reserved(pid) == 2


def test_reserve_moves_units(inventory, pid):
    inventory.reserve(pid, 5)
    assert inventory.available(pid) == 70
    assert inventory.reserved(pid) == 7


def test_reserve_over_available_raises(inventory, low_pid):
    with pytest.raises(OutOfStockError):
        inventory.reserve(low_pid, 3)
    # Nothing changed.
    assert inventory.available(low_pid) == 2
    assert inventory.reserved(low_pid) == 1


def test_reserve_exactly_available_ok(inventory, low_pid):
    inventory.reserve(low_pid, 2)
    assert inventory.available(low_pid) == 0
    assert inventory.reserved(low_pid) == 3


def test_reserve_invalid_qty(inventory, pid):
    with pytest.raises(ValidationError):
        inventory.reserve(pid, 0)
    with pytest.raises(ValidationError):
        inventory.reserve(pid, -1)
    with pytest.raises(ValidationError):
        inventory.reserve(pid, 1.5)


def test_release_returns_units(inventory, pid):
    inventory.release(pid, 2)
    assert inventory.available(pid) == 77
    assert inventory.reserved(pid) == 0


def test_release_more_than_reserved_raises(inventory, pid):
    with pytest.raises(ValidationError):
        inventory.release(pid, 3)


def test_commit_consumes_reserved(inventory, pid):
    inventory.commit_reservation(pid, 2)
    assert inventory.reserved(pid) == 0
    assert inventory.available(pid) == 75  # never returns to available


def test_commit_more_than_reserved_raises(inventory, pid):
    with pytest.raises(ValidationError):
        inventory.commit_reservation(pid, 3)


def test_adjust_positive_and_negative(inventory, pid):
    inventory.adjust(pid, 10)
    assert inventory.available(pid) == 85
    inventory.adjust(pid, -5)
    assert inventory.available(pid) == 80


def test_adjust_below_zero_raises(inventory, low_pid):
    with pytest.raises(ValidationError):
        inventory.adjust(low_pid, -3)


def test_adjust_zero_delta_raises(inventory, pid):
    with pytest.raises(ValidationError):
        inventory.adjust(pid, 0)


def test_restock_adds_units(inventory, pid):
    inventory.restock(pid, 25)
    assert inventory.available(pid) == 100


def test_restock_invalid_qty(inventory, pid):
    with pytest.raises(ValidationError):
        inventory.restock(pid, 0)


def test_set_level_overwrites(inventory, pid):
    inventory.set_level(pid, available=9, reserved=1)
    assert inventory.available(pid) == 9
    assert inventory.reserved(pid) == 1


def test_set_level_rejects_negative(inventory, pid):
    with pytest.raises(ValidationError):
        inventory.set_level(pid, available=-1)
    with pytest.raises(ValidationError):
        inventory.set_level(pid, available=1, reserved=-2)
