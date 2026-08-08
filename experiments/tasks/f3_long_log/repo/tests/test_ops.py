import datetime
from decimal import Decimal

import pytest

from etlkit.errors import RecordError
from etlkit.ops import OPS


def apply(op_name, record, op):
    return OPS[op_name](record, op)


class TestCast:
    def test_int(self):
        rec = apply("cast", {"q": " 1,204 "}, {"op": "cast", "field": "q", "to": "int"})
        assert rec["q"] == 1204

    def test_decimal(self):
        rec = apply("cast", {"p": "$2.50"}, {"op": "cast", "field": "p", "to": "decimal"})
        assert rec["p"] == Decimal("2.50")

    def test_date(self):
        rec = apply("cast", {"d": "2026-07-01"}, {"op": "cast", "field": "d", "to": "date"})
        assert rec["d"] == datetime.date(2026, 7, 1)

    def test_bool(self):
        assert apply("cast", {"b": "TRUE"}, {"op": "cast", "field": "b", "to": "bool"})["b"] is True
        assert apply("cast", {"b": "0"}, {"op": "cast", "field": "b", "to": "bool"})["b"] is False

    def test_blank_untouched(self):
        rec = apply("cast", {"q": ""}, {"op": "cast", "field": "q", "to": "int"})
        assert rec["q"] == ""

    def test_failure_is_record_error(self):
        with pytest.raises(RecordError, match="cast q to int failed"):
            apply("cast", {"q": "many"}, {"op": "cast", "field": "q", "to": "int"})


class TestRename:
    def test_renames(self):
        rec = apply("rename", {"old": 1}, {"op": "rename", "field": "old", "to": "new"})
        assert rec == {"new": 1}

    def test_absent_is_noop(self):
        rec = apply("rename", {"a": 1}, {"op": "rename", "field": "x", "to": "y"})
        assert rec == {"a": 1}


class TestDefault:
    def test_fills_blank(self):
        rec = apply("default", {"r": " "}, {"op": "default", "field": "r", "value": "n/a"})
        assert rec["r"] == "n/a"

    def test_keeps_present(self):
        rec = apply("default", {"r": "x"}, {"op": "default", "field": "r", "value": "n/a"})
        assert rec["r"] == "x"


def test_drop():
    rec = apply("drop", {"a": 1, "b": 2}, {"op": "drop", "field": "a"})
    assert rec == {"b": 2}


class TestDerive:
    def test_multiply(self):
        rec = apply(
            "derive",
            {"q": 3, "p": Decimal("2.50")},
            {"op": "derive", "field": "t", "formula": "multiply", "args": ["q", "p"]},
        )
        assert rec["t"] == Decimal("7.50")

    def test_subtract(self):
        rec = apply(
            "derive",
            {"a": Decimal("10"), "b": Decimal("4")},
            {"op": "derive", "field": "d", "formula": "subtract", "args": ["a", "b"]},
        )
        assert rec["d"] == Decimal("6")

    def test_money(self):
        rec = apply(
            "derive",
            {"t": Decimal("7.5")},
            {"op": "derive", "field": "t", "formula": "money", "args": ["t"]},
        )
        assert rec["t"] == "7.50"

    def test_concat(self):
        rec = apply(
            "derive",
            {"f": "Ada", "l": "Byron"},
            {"op": "derive", "field": "n", "formula": "concat", "args": ["f", "l"]},
        )
        assert rec["n"] == "Ada Byron"

    def test_missing_arg(self):
        with pytest.raises(RecordError, match="which is missing"):
            apply(
                "derive",
                {"q": 1},
                {"op": "derive", "field": "t", "formula": "multiply", "args": ["q", "p"]},
            )

    def test_unknown_formula(self):
        with pytest.raises(RecordError, match="unknown derive formula"):
            apply(
                "derive",
                {"a": 1},
                {"op": "derive", "field": "x", "formula": "power", "args": ["a"]},
            )
