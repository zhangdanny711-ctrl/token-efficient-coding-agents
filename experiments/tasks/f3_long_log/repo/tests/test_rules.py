import pytest

from etlkit.errors import CheckFailure
from etlkit.rules import RULES


def apply(rule, record, check, state=None):
    RULES[rule](record, check, state if state is not None else {})


class TestRequired:
    def test_present(self):
        apply("required", {"a": "x"}, {"rule": "required", "field": "a"})

    def test_missing(self):
        with pytest.raises(CheckFailure, match="missing or blank"):
            apply("required", {}, {"rule": "required", "field": "a"})

    def test_blank(self):
        with pytest.raises(CheckFailure):
            apply("required", {"a": "  "}, {"rule": "required", "field": "a"})


class TestType:
    def test_good_int(self):
        apply("type", {"q": "3"}, {"rule": "type", "field": "q", "type": "int"})

    def test_bad_int(self):
        with pytest.raises(CheckFailure, match="not an integer"):
            apply("type", {"q": "three"}, {"rule": "type", "field": "q", "type": "int"})

    def test_good_date(self):
        apply("type", {"d": "2026-07-01"}, {"rule": "type", "field": "d", "type": "date"})

    def test_bad_date(self):
        with pytest.raises(CheckFailure):
            apply("type", {"d": "07/01/26"}, {"rule": "type", "field": "d", "type": "date"})

    def test_bad_bool(self):
        with pytest.raises(CheckFailure, match="not a boolean"):
            apply("type", {"b": "yes"}, {"rule": "type", "field": "b", "type": "bool"})

    def test_absent_field_passes(self):
        apply("type", {}, {"rule": "type", "field": "q", "type": "int"})


class TestRange:
    def test_within(self):
        apply("range", {"q": "5"}, {"rule": "range", "field": "q", "min": 1, "max": 10})

    def test_below(self):
        with pytest.raises(CheckFailure, match="below the minimum"):
            apply("range", {"q": "0"}, {"rule": "range", "field": "q", "min": 1})

    def test_above(self):
        with pytest.raises(CheckFailure, match="above the maximum"):
            apply("range", {"q": "11"}, {"rule": "range", "field": "q", "max": 10})

    def test_unparseable(self):
        with pytest.raises(CheckFailure, match="not a number"):
            apply("range", {"q": "n/a"}, {"rule": "range", "field": "q", "min": 0})


class TestOneOf:
    def test_allowed(self):
        apply("one_of", {"r": "north"},
              {"rule": "one_of", "field": "r", "values": ["north", "south"]})

    def test_rejected(self):
        with pytest.raises(CheckFailure, match="is not one of"):
            apply("one_of", {"r": "central"},
                  {"rule": "one_of", "field": "r", "values": ["north", "south"]})


class TestUnique:
    def test_flags_duplicates(self):
        state = {}
        check = {"rule": "unique", "field": "id"}
        apply("unique", {"id": "1"}, check, state)
        apply("unique", {"id": "2"}, check, state)
        with pytest.raises(CheckFailure, match="duplicate value"):
            apply("unique", {"id": "1"}, check, state)

    def test_composite_key(self):
        state = {}
        check = {"rule": "unique", "fields": ["a", "b"]}
        apply("unique", {"a": "1", "b": "x"}, check, state)
        apply("unique", {"a": "1", "b": "y"}, check, state)
        with pytest.raises(CheckFailure):
            apply("unique", {"a": "1", "b": "x"}, check, state)


class TestMatches:
    def test_prefix_ok(self):
        apply("matches", {"sku": "WID-1"}, {"rule": "matches", "field": "sku", "prefix": "WID-"})

    def test_prefix_fail(self):
        with pytest.raises(CheckFailure, match="does not start with"):
            apply("matches", {"sku": "GAD-1"},
                  {"rule": "matches", "field": "sku", "prefix": "WID-"})

    def test_contains_fail(self):
        with pytest.raises(CheckFailure, match="does not contain"):
            apply("matches", {"email": "x"},
                  {"rule": "matches", "field": "email", "contains": "@"})
