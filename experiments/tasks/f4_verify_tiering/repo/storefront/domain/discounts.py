"""Discount application rules.

Pure functions that turn a :class:`Discount` plus an order subtotal
into a concrete discount amount, enforcing eligibility rules.
"""

from __future__ import annotations

from typing import Iterable

from storefront.domain.errors import DiscountError
from storefront.domain.models import Discount
from storefront.domain.money import Money


def discount_amount(discount: Discount, subtotal: Money) -> Money:
    """Compute the amount a discount takes off ``subtotal``.

    Rules:

    * inactive codes raise :class:`DiscountError`;
    * subtotals below the code's minimum raise :class:`DiscountError`
      (the message states the required minimum);
    * ``percent`` codes take ``value`` percent of the subtotal
      (half-up rounding);
    * ``fixed`` codes take ``value`` cents, capped at the subtotal so
      the discount never exceeds the amount owed.
    """
    if not discount.active:
        raise DiscountError(f"discount {discount.code} is not active")
    if subtotal.cents < discount.min_subtotal_cents:
        minimum = Money(discount.min_subtotal_cents, subtotal.currency)
        raise DiscountError(
            f"discount {discount.code} requires a minimum subtotal of "
            f"{minimum.format()}; got {subtotal.format()}"
        )
    if discount.kind == "percent":
        return subtotal.percent(discount.value / 100.0)
    return Money(min(discount.value, subtotal.cents), subtotal.currency)


def best_discount(
    discounts: Iterable[Discount], subtotal: Money
) -> tuple[Discount, Money] | None:
    """Pick the applicable discount that saves the customer the most.

    Codes that raise :class:`DiscountError` (inactive, or minimum not
    met) are skipped. Returns the winning ``(discount, amount)`` pair,
    or ``None`` when no code applies.
    """
    best: tuple[Discount, Money] | None = None
    for discount in discounts:
        try:
            amount = discount_amount(discount, subtotal)
        except DiscountError:
            continue
        if best is None or amount.cents > best[1].cents:
            best = (discount, amount)
    return best
