"""Tests for storefront.persistence.store.InMemoryStore."""

import pytest

from storefront.domain.errors import NotFoundError, ValidationError
from storefront.persistence.store import TABLES, InMemoryStore


def test_tables_constant():
    assert "products" in TABLES
    assert "inventory" in TABLES


def test_insert_and_get(store):
    store.insert("products", "p1", {"name": "Kettle"})
    assert store.get("products", "p1") == {"name": "Kettle"}


def test_insert_duplicate_key_raises(store):
    store.insert("products", "p1", {"name": "Kettle"})
    with pytest.raises(ValidationError):
        store.insert("products", "p1", {"name": "Other"})


def test_get_missing_key_raises_not_found(store):
    with pytest.raises(NotFoundError):
        store.get("products", "missing")


def test_unknown_table_raises_validation(store):
    with pytest.raises(ValidationError):
        store.get("widgets", "p1")
    with pytest.raises(ValidationError):
        store.insert("widgets", "p1", {})
    with pytest.raises(ValidationError):
        store.all("widgets")


def test_update_replaces_record(store):
    store.insert("products", "p1", {"name": "Kettle"})
    store.update("products", "p1", {"name": "Pot"})
    assert store.get("products", "p1") == {"name": "Pot"}


def test_update_missing_key_raises(store):
    with pytest.raises(NotFoundError):
        store.update("products", "missing", {"name": "x"})


def test_delete(store):
    store.insert("products", "p1", {"name": "Kettle"})
    store.delete("products", "p1")
    with pytest.raises(NotFoundError):
        store.get("products", "p1")


def test_delete_missing_key_raises(store):
    with pytest.raises(NotFoundError):
        store.delete("products", "missing")


def test_all_returns_insertion_order(store):
    store.insert("products", "p1", {"name": "A"})
    store.insert("products", "p2", {"name": "B"})
    assert store.all("products") == [{"name": "A"}, {"name": "B"}]


def test_count(store):
    assert store.count("products") == 0
    store.insert("products", "p1", {})
    assert store.count("products") == 1


def test_clear_empties_all_tables(store):
    store.insert("products", "p1", {})
    store.insert("customers", "c1", {})
    store.clear()
    assert store.count("products") == 0
    assert store.count("customers") == 0


# ----------------------------------------------------------------------
# copy semantics
# ----------------------------------------------------------------------

def test_insert_copies_record(store):
    record = {"name": "Kettle"}
    store.insert("products", "p1", record)
    record["name"] = "Mutated"
    assert store.get("products", "p1")["name"] == "Kettle"


def test_get_returns_copy(store):
    store.insert("products", "p1", {"name": "Kettle"})
    fetched = store.get("products", "p1")
    fetched["name"] = "Mutated"
    assert store.get("products", "p1")["name"] == "Kettle"


def test_all_returns_copies(store):
    store.insert("products", "p1", {"name": "Kettle"})
    store.all("products")[0]["name"] = "Mutated"
    assert store.get("products", "p1")["name"] == "Kettle"
