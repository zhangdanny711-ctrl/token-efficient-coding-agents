"""Tests for storefront.services.pricing.PricingService."""

import pytest

from storefront.domain.errors import DiscountError, ValidationError
from storefront.domain.models import Address, CartItem, Product
from storefront.domain.money import Money

CA = Address(street="1200 Harbor Blvd", city="San Diego", state="CA",
             postal_code="92101")


def make_product(product_id="p1", price_cents=500, weight_grams=100):
    return Product(
        product_id=product_id, sku="SKU-" + product_id, name="Item " + product_id,
        description="", price=Money(price_cents), category="misc",
        tags=[], weight_grams=weight_grams,
    )


def make_item(product, qty=1):
    return CartItem(product_id=product.product_id, quantity=qty,
                    unit_price=product.price)


def cart_of(*specs):
    """Build (items, products_by_id) from (price_cents, weight, qty) specs."""
    items, by_id = [], {}
    for i, (price_cents, weight, qty) in enumerate(specs):
        product = make_product("p%d" % i, price_cents, weight)
        by_id[product.product_id] = product
        items.append(make_item(product, qty))
    return items, by_id


# ----------------------------------------------------------------------
# line_total / subtotal
# ----------------------------------------------------------------------

def test_line_total(pricing_service):
    item = make_item(make_product(price_cents=299), qty=3)
    assert pricing_service.line_total(item) == Money(897)


def test_line_total_rejects_non_positive_quantity(pricing_service):
    # CartItem construction allows qty 0 (validate() is separate); the
    # pricing service still refuses to price it.
    item = CartItem(product_id="p", quantity=0, unit_price=Money(100))
    with pytest.raises(ValidationError):
        pricing_service.line_total(item)


def test_subtotal_sums_lines(pricing_service):
    items, _ = cart_of((500, 100, 2), (299, 100, 1))
    assert pricing_service.subtotal(items) == Money(1299)


def test_subtotal_empty_is_zero(pricing_service):
    assert pricing_service.subtotal([]) == Money.zero()


# ----------------------------------------------------------------------
# discount_for
# ----------------------------------------------------------------------

def test_discount_for_known_code(pricing_service):
    amount, code = pricing_service.discount_for(Money(10000), "WELCOME10")
    assert amount == Money(1000)
    assert code == "WELCOME10"


def test_discount_for_unknown_code(pricing_service):
    with pytest.raises(DiscountError, match="unknown code"):
        pricing_service.discount_for(Money(10000), "BOGUS")


def test_discount_for_none(pricing_service):
    assert pricing_service.discount_for(Money(10000), None) == (Money.zero(), None)


def test_discount_for_empty_string(pricing_service):
    assert pricing_service.discount_for(Money(10000), "") == (Money.zero(), None)


def test_discount_for_inactive_code(pricing_service):
    with pytest.raises(DiscountError):
        pricing_service.discount_for(Money(10000), "EXPIRED")


def test_discount_for_min_subtotal_unmet(pricing_service):
    with pytest.raises(DiscountError):
        pricing_service.discount_for(Money(4999), "SAVE15")


# ----------------------------------------------------------------------
# shipping_for
# ----------------------------------------------------------------------

def test_shipping_free_at_threshold(pricing_service):
    items, by_id = cart_of((7500, 100, 1))
    assert pricing_service.shipping_for(items, by_id, Money(7500)).is_zero()


def test_shipping_flat_below_threshold(pricing_service):
    items, by_id = cart_of((7499, 100, 1))
    assert pricing_service.shipping_for(items, by_id, Money(7499)) == Money(599)


def test_shipping_heavy_surcharge(pricing_service):
    items, by_id = cart_of((3000, 5001, 1))
    assert pricing_service.shipping_for(items, by_id, Money(3000)) == Money(999)


def test_shipping_weight_at_threshold_no_surcharge(pricing_service):
    # Surcharge applies only strictly above heavy_order_grams.
    items, by_id = cart_of((3000, 5000, 1))
    assert pricing_service.shipping_for(items, by_id, Money(3000)) == Money(599)


def test_shipping_weight_multiplied_by_quantity(pricing_service):
    items, by_id = cart_of((1000, 2000, 3))  # 6000 g total
    assert pricing_service.shipping_for(items, by_id, Money(3000)) == Money(999)


def test_shipping_free_even_when_heavy(pricing_service):
    items, by_id = cart_of((8000, 9000, 1))
    assert pricing_service.shipping_for(items, by_id, Money(8000)).is_zero()


# ----------------------------------------------------------------------
# tier adjustment
# ----------------------------------------------------------------------

def test_tier_adjustment_gold(pricing_service):
    assert pricing_service.apply_tier_adjustment(Money(10000), "gold") == Money(9800)


def test_tier_adjustment_standard_and_silver_unchanged(pricing_service):
    assert pricing_service.apply_tier_adjustment(Money(10000), "standard") == Money(10000)
    assert pricing_service.apply_tier_adjustment(Money(10000), "silver") == Money(10000)


def test_tier_adjustment_unknown_tier_passthrough(pricing_service):
    assert pricing_service.apply_tier_adjustment(Money(10000), "mystery") == Money(10000)


# ----------------------------------------------------------------------
# tax
# ----------------------------------------------------------------------

def test_tax_for_address(pricing_service):
    assert pricing_service.tax_for_address(Money(10000), CA) == Money(725)


def test_tax_for_address_requires_address(pricing_service):
    with pytest.raises(ValidationError):
        pricing_service.tax_for_address(Money(10000), None)


# ----------------------------------------------------------------------
# full quote
# ----------------------------------------------------------------------

def grand_identity(b):
    return b.subtotal.sub(b.discount_total).add(b.tax_total).add(b.shipping_total)


def test_quote_standard_tier_identity(pricing_service):
    items, by_id = cart_of((4299, 3100, 1), (2799, 390, 2))
    b = pricing_service.quote(items, by_id, CA)
    assert b.subtotal == Money(9897)
    assert b.discount_total.is_zero()
    assert b.shipping_total.is_zero()  # over free-shipping threshold
    assert b.tax_total == Money(9897).percent(0.0725)
    assert b.grand_total == grand_identity(b)
    assert b.discount_code is None


def test_quote_standard_with_code(pricing_service):
    items, by_id = cart_of((10000, 100, 1))
    b = pricing_service.quote(items, by_id, CA, discount_code="WELCOME10")
    assert b.discount_total == Money(1000)
    assert b.discount_code == "WELCOME10"
    assert b.grand_total == grand_identity(b)


def test_quote_gold_tier_reduction_in_discount_total(pricing_service):
    items, by_id = cart_of((10000, 100, 1))
    b = pricing_service.quote(items, by_id, CA, tier="gold")
    # subtotal reports the raw line sum; the 2% tier benefit shows up
    # as discount_total instead.
    assert b.subtotal == Money(10000)
    assert b.discount_total == Money(200)
    assert b.grand_total == grand_identity(b)


def test_quote_gold_tier_plus_code_folded_together(pricing_service):
    items, by_id = cart_of((10000, 100, 1))
    b = pricing_service.quote(items, by_id, CA, discount_code="WELCOME10",
                              tier="gold")
    # tier: 200 off, then 10% of the adjusted 9800 = 980.
    assert b.discount_total == Money(1180)
    assert b.tax_total == Money(8820).percent(0.0725)
    assert b.grand_total == grand_identity(b)


def test_quote_gold_min_subtotal_judged_on_adjusted(pricing_service):
    # SAVE15 requires 5000; raw 5050 adjusted by 2% -> 4949 < 5000.
    items, by_id = cart_of((5050, 100, 1))
    with pytest.raises(DiscountError):
        pricing_service.quote(items, by_id, CA, discount_code="SAVE15",
                              tier="gold")
    # A standard customer at the same subtotal qualifies.
    b = pricing_service.quote(items, by_id, CA, discount_code="SAVE15")
    assert b.discount_code == "SAVE15"


def test_quote_discount_can_reintroduce_shipping(pricing_service):
    # Raw 7900 is above the free bar; after 15% off (1185) it is 6715.
    items, by_id = cart_of((7900, 100, 1))
    b = pricing_service.quote(items, by_id, CA, discount_code="SAVE15")
    assert b.shipping_total == Money(599)
    assert b.grand_total == grand_identity(b)


def test_quote_lines_are_json_safe(pricing_service):
    items, by_id = cart_of((500, 100, 2))
    b = pricing_service.quote(items, by_id, CA)
    assert b.lines == [{
        "product_id": "p0", "quantity": 2,
        "unit_price": "5.00", "line_total": "10.00",
    }]
    d = b.as_dict()
    assert d["subtotal"] == "10.00"
    assert isinstance(d["grand_total"], str)


def test_quote_rejects_empty_items(pricing_service):
    with pytest.raises(ValidationError):
        pricing_service.quote([], {}, CA)


def test_quote_rejects_missing_product(pricing_service):
    items, _ = cart_of((500, 100, 1))
    with pytest.raises(ValidationError, match="missing product records"):
        pricing_service.quote(items, {}, CA)
