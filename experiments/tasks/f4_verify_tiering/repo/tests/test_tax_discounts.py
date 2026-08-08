"""Tests for storefront.domain.tax and storefront.domain.discounts."""

import pytest

from storefront.domain.discounts import best_discount, discount_amount
from storefront.domain.errors import DiscountError, ValidationError
from storefront.domain.models import Discount
from storefront.domain.money import Money
from storefront.domain.tax import STATE_TAX_RATES, states_with_no_tax, tax_for


# ----------------------------------------------------------------------
# tax_for
# ----------------------------------------------------------------------

def test_tax_for_ca():
    assert tax_for(Money(10000), "CA") == Money(725)


def test_tax_for_ny():
    assert tax_for(Money(10000), "NY") == Money(888)  # 887.5 rounds up


def test_tax_for_zero_rate_state():
    assert tax_for(Money(10000), "OR").is_zero()


def test_tax_for_unknown_state():
    with pytest.raises(ValidationError):
        tax_for(Money(10000), "ZZ")


def test_tax_for_malformed_state():
    with pytest.raises(ValidationError):
        tax_for(Money(10000), "ca")


def test_tax_for_half_up_rounding():
    # 7999 * 0.0725 = 579.9275 -> 580
    assert tax_for(Money(7999), "CA") == Money(580)


def test_states_with_no_tax():
    zero = states_with_no_tax()
    assert zero == sorted(zero)
    assert set(zero) == {c for c, r in STATE_TAX_RATES.items() if r == 0.0}
    assert "OR" in zero and "CA" not in zero


# ----------------------------------------------------------------------
# discount_amount
# ----------------------------------------------------------------------

def test_discount_inactive_raises():
    d = Discount(code="X", kind="percent", value=10, min_subtotal_cents=0,
                 active=False)
    with pytest.raises(DiscountError):
        discount_amount(d, Money(10000))


def test_discount_min_subtotal_not_met():
    d = Discount(code="X", kind="percent", value=10, min_subtotal_cents=5000)
    with pytest.raises(DiscountError):
        discount_amount(d, Money(4999))


def test_discount_min_subtotal_exactly_met():
    d = Discount(code="X", kind="percent", value=10, min_subtotal_cents=5000)
    assert discount_amount(d, Money(5000)) == Money(500)


def test_discount_percent():
    d = Discount(code="X", kind="percent", value=15, min_subtotal_cents=0)
    assert discount_amount(d, Money(10000)) == Money(1500)


def test_discount_percent_half_up():
    d = Discount(code="X", kind="percent", value=15, min_subtotal_cents=0)
    # 15% of 3.30 = 49.5 cents -> 50
    assert discount_amount(d, Money(330)) == Money(50)


def test_discount_fixed():
    d = Discount(code="X", kind="fixed", value=500, min_subtotal_cents=0)
    assert discount_amount(d, Money(10000)) == Money(500)


def test_discount_fixed_capped_at_subtotal():
    d = Discount(code="X", kind="fixed", value=5000, min_subtotal_cents=0)
    assert discount_amount(d, Money(3000)) == Money(3000)


def test_discount_preserves_currency():
    d = Discount(code="X", kind="fixed", value=100, min_subtotal_cents=0)
    assert discount_amount(d, Money(1000, "EUR")).currency == "EUR"


# ----------------------------------------------------------------------
# best_discount
# ----------------------------------------------------------------------

def test_best_discount_picks_largest():
    ten = Discount(code="TEN", kind="percent", value=10, min_subtotal_cents=0)
    fiver = Discount(code="FIVER", kind="fixed", value=500, min_subtotal_cents=0)
    winner, amount = best_discount([ten, fiver], Money(10000))
    assert winner is ten
    assert amount == Money(1000)


def test_best_discount_skips_inapplicable():
    inactive = Discount(code="DEAD", kind="percent", value=50,
                        min_subtotal_cents=0, active=False)
    too_high = Discount(code="BIGMIN", kind="percent", value=50,
                        min_subtotal_cents=99999)
    small = Discount(code="SMALL", kind="fixed", value=100, min_subtotal_cents=0)
    winner, amount = best_discount([inactive, too_high, small], Money(5000))
    assert winner is small
    assert amount == Money(100)


def test_best_discount_none_when_nothing_applies():
    inactive = Discount(code="DEAD", kind="percent", value=50,
                        min_subtotal_cents=0, active=False)
    assert best_discount([inactive], Money(5000)) is None


def test_best_discount_empty_iterable():
    assert best_discount([], Money(5000)) is None
