"""Tests for storefront.domain.money.Money."""

import pytest

from storefront.domain.errors import CurrencyMismatchError, ValidationError
from storefront.domain.money import Money


# ----------------------------------------------------------------------
# construction
# ----------------------------------------------------------------------

def test_construct_basic():
    m = Money(1234)
    assert m.cents == 1234
    assert m.currency == "USD"


def test_construct_rejects_non_int_cents():
    with pytest.raises(ValidationError):
        Money(12.34)


def test_construct_rejects_bool_cents():
    with pytest.raises(ValidationError):
        Money(True)


def test_construct_rejects_bad_currency():
    with pytest.raises(ValidationError):
        Money(100, "DOLLARS")


def test_zero():
    z = Money.zero("EUR")
    assert z.cents == 0
    assert z.currency == "EUR"
    assert z.is_zero()


# ----------------------------------------------------------------------
# from_decimal_string
# ----------------------------------------------------------------------

@pytest.mark.parametrize("text, cents", [
    ("12.34", 1234),
    ("12", 1200),
    ("0.5", 50),
    ("0.05", 5),
    ("-3.07", -307),
    ("0", 0),
    (" 12.34 ", 1234),
])
def test_from_decimal_string_valid(text, cents):
    assert Money.from_decimal_string(text).cents == cents


@pytest.mark.parametrize("text", [
    "12.345",
    "abc",
    "12.",
    ".5",
    "$5",
    "1,000",
    "",
    "1.2.3",
])
def test_from_decimal_string_invalid(text):
    with pytest.raises(ValidationError):
        Money.from_decimal_string(text)


def test_from_decimal_string_rejects_non_string():
    with pytest.raises(ValidationError):
        Money.from_decimal_string(1234)


def test_from_decimal_string_sets_currency():
    assert Money.from_decimal_string("1.00", "GBP").currency == "GBP"


# ----------------------------------------------------------------------
# arithmetic
# ----------------------------------------------------------------------

def test_add():
    assert Money(100).add(Money(250)) == Money(350)


def test_sub():
    assert Money(500).sub(Money(199)) == Money(301)


def test_sub_can_go_negative():
    assert Money(100).sub(Money(150)).cents == -50


def test_mul():
    assert Money(299).mul(3) == Money(897)


def test_mul_zero():
    assert Money(299).mul(0).is_zero()


def test_mul_rejects_negative_qty():
    with pytest.raises(ValidationError):
        Money(100).mul(-1)


def test_mul_rejects_non_int_qty():
    with pytest.raises(ValidationError):
        Money(100).mul(2.0)


def test_add_rejects_non_money():
    with pytest.raises(ValidationError):
        Money(100).add(100)


# ----------------------------------------------------------------------
# percent (half-up rounding)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("cents, rate, expected", [
    (10000, 0.0725, 725),
    (150, 0.05, 8),       # 7.5 rounds up
    (250, 0.05, 13),      # 12.5 rounds up
    (100, 0.005, 1),      # 0.5 rounds up
    (1, 0.005, 0),        # 0.005 rounds down
    (7999, 0.08875, 710),
    (0, 0.5, 0),
])
def test_percent_half_up(cents, rate, expected):
    assert Money(cents).percent(rate).cents == expected


def test_percent_rejects_negative_rate():
    with pytest.raises(ValidationError):
        Money(100).percent(-0.1)


def test_percent_rejects_non_numeric_rate():
    with pytest.raises(ValidationError):
        Money(100).percent("0.1")


def test_percent_preserves_currency():
    assert Money(100, "EUR").percent(0.1).currency == "EUR"


# ----------------------------------------------------------------------
# currency mismatch
# ----------------------------------------------------------------------

def test_add_currency_mismatch():
    with pytest.raises(CurrencyMismatchError):
        Money(100, "USD").add(Money(100, "EUR"))


def test_sub_currency_mismatch():
    with pytest.raises(CurrencyMismatchError):
        Money(100, "USD").sub(Money(100, "GBP"))


def test_compare_currency_mismatch():
    with pytest.raises(CurrencyMismatchError):
        Money(100, "USD") < Money(200, "EUR")


# ----------------------------------------------------------------------
# comparisons
# ----------------------------------------------------------------------

def test_comparisons():
    assert Money(100) < Money(200)
    assert Money(100) <= Money(100)
    assert Money(300) > Money(200)
    assert Money(300) >= Money(300)


# ----------------------------------------------------------------------
# formatting
# ----------------------------------------------------------------------

@pytest.mark.parametrize("cents, expected", [
    (1234, "12.34"),
    (5, "0.05"),
    (-307, "-3.07"),
    (0, "0.00"),
    (100, "1.00"),
])
def test_to_decimal_string(cents, expected):
    assert Money(cents).to_decimal_string() == expected


def test_format_known_symbols():
    assert Money(1234, "USD").format() == "$12.34"
    assert Money(1234, "EUR").format() == "€12.34"
    assert Money(1234, "GBP").format() == "£12.34"


def test_format_unknown_currency():
    assert Money(1234, "CAD").format() == "CAD 12.34"


def test_str_matches_format():
    assert str(Money(999)) == "$9.99"


def test_round_trip_decimal_string():
    m = Money(70599)
    assert Money.from_decimal_string(m.to_decimal_string()) == m
