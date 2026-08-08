"""Tests for storefront.utils (text, config, ids, clock)."""

from datetime import datetime

import pytest

from storefront.utils.clock import FixedClock, SystemClock
from storefront.utils.config import DEFAULTS, load_config
from storefront.utils.ids import IdSequence, make_sequences
from storefront.utils.text import normalize_ws, slugify, title_case, truncate


# ----------------------------------------------------------------------
# text helpers
# ----------------------------------------------------------------------

def test_slugify_basic():
    assert slugify("  Deluxe Espresso Machine! ") == "deluxe-espresso-machine"


def test_slugify_collapses_runs():
    assert slugify("a  --  b") == "a-b"


def test_slugify_strips_edge_hyphens():
    assert slugify("!!hello!!") == "hello"


def test_normalize_ws():
    assert normalize_ws("  hello \t world\n") == "hello world"


def test_normalize_ws_empty():
    assert normalize_ws("   ") == ""


def test_truncate_fits_unchanged():
    assert truncate("short", 10) == "short"


def test_truncate_adds_suffix():
    assert truncate("hello world", 8) == "hello..."


def test_truncate_hard_cut_when_n_small():
    assert truncate("hello", 2) == "he"


def test_truncate_rejects_negative_n():
    with pytest.raises(ValueError):
        truncate("x", -1)


def test_title_case_minor_words():
    assert title_case("the art of the deal") == "The Art of the Deal"


def test_title_case_first_and_last_capitalised():
    assert title_case("of mice and of") == "Of Mice and Of"


def test_title_case_empty():
    assert title_case("") == ""
    assert title_case("   ") == ""


# ----------------------------------------------------------------------
# config
# ----------------------------------------------------------------------

def test_load_config_defaults():
    config = load_config()
    assert config == DEFAULTS
    assert config is not DEFAULTS  # a copy, never the shared dict


def test_load_config_applies_overrides():
    config = load_config({"flat_shipping_cents": 999})
    assert config["flat_shipping_cents"] == 999
    assert config["currency"] == "USD"


def test_load_config_rejects_unknown_key():
    with pytest.raises(ValueError, match="unknown config keys"):
        load_config({"flat_shipping": 999})


def test_load_config_does_not_mutate_defaults():
    load_config({"flat_shipping_cents": 1})
    assert DEFAULTS["flat_shipping_cents"] == 599


# ----------------------------------------------------------------------
# IdSequence
# ----------------------------------------------------------------------

def test_id_sequence_formatting():
    seq = IdSequence("ord")
    assert seq.next() == "ord-000001"
    assert seq.next() == "ord-000002"


def test_id_sequence_peek_does_not_advance():
    seq = IdSequence("crt")
    assert seq.peek() == "crt-000001"
    assert seq.peek() == "crt-000001"
    assert seq.next() == "crt-000001"


def test_id_sequence_custom_start_and_reset():
    seq = IdSequence("x", start=42)
    assert seq.next() == "x-000042"
    seq.reset()
    assert seq.next() == "x-000042"


def test_id_sequence_rejects_empty_prefix():
    with pytest.raises(ValueError):
        IdSequence("")


def test_id_sequence_rejects_negative_start():
    with pytest.raises(ValueError):
        IdSequence("x", start=-1)


def test_make_sequences_keys():
    seqs = make_sequences()
    assert set(seqs) == {"product", "customer", "cart", "order",
                         "payment", "shipment"}
    assert seqs["order"].next() == "ord-000001"
    assert seqs["product"].next() == "prd-000001"


# ----------------------------------------------------------------------
# clocks
# ----------------------------------------------------------------------

def test_fixed_clock_is_frozen():
    clock = FixedClock("2026-01-15T09:00:00")
    assert clock.now() == datetime(2026, 1, 15, 9, 0, 0)
    assert clock.now() == clock.now()


def test_fixed_clock_advance():
    clock = FixedClock("2026-01-15T09:00:00")
    clock.advance(3600)
    assert clock.now() == datetime(2026, 1, 15, 10, 0, 0)


def test_system_clock_returns_utc():
    now = SystemClock().now()
    assert now.tzinfo is not None
