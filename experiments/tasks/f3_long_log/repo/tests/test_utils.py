from decimal import Decimal

import pytest

from etlkit.utils.numbers import (
    clamp,
    format_money,
    parse_decimal,
    parse_int,
    percent,
)
from etlkit.utils.text import (
    is_blank,
    normalize_header,
    pluralize,
    truncate,
)


class TestNormalizeHeader:
    def test_basic(self):
        assert normalize_header("Order ID ") == "order_id"

    def test_junk_collapses(self):
        assert normalize_header("Unit  Price ($)") == "unit_price"

    def test_already_clean(self):
        assert normalize_header("region") == "region"


class TestParseInt:
    def test_plain(self):
        assert parse_int("7") == 7

    def test_commas_and_space(self):
        assert parse_int(" 1,204 ") == 1204

    def test_passthrough(self):
        assert parse_int(12) == 12

    def test_bool_rejected(self):
        with pytest.raises(ValueError):
            parse_int(True)

    def test_garbage(self):
        with pytest.raises(ValueError, match="not an integer"):
            parse_int("seven")


class TestParseDecimal:
    def test_plain(self):
        assert parse_decimal("10.50") == Decimal("10.50")

    def test_currency(self):
        assert parse_decimal("$2.50") == Decimal("2.50")

    def test_garbage(self):
        with pytest.raises(ValueError, match="not a number"):
            parse_decimal("n/a")


def test_format_money():
    assert format_money(Decimal("3")) == "3.00"
    assert format_money(Decimal("3.456")) == "3.46"


def test_percent():
    assert percent(1, 4) == 25.0
    assert percent(3, 0) == 0.0


def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(99, 0, 10) == 10


def test_truncate():
    assert truncate("short") == "short"
    assert truncate("x" * 100, limit=10) == "xxxxxxx..."


def test_is_blank():
    assert is_blank(None)
    assert is_blank("   ")
    assert not is_blank("x")
    assert not is_blank(0)


def test_pluralize():
    assert pluralize(1, "record") == "1 record"
    assert pluralize(3, "record") == "3 records"
    assert pluralize(2, "entry", "entries") == "2 entries"
