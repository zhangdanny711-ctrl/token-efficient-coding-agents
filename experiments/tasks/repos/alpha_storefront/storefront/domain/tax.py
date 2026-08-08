"""US state sales-tax rates and calculation.

Rates are simplified base state rates (no local surtaxes) sufficient
for the storefront's needs. Unknown states are rejected rather than
defaulting, so misconfigured checkouts fail loudly.
"""

from __future__ import annotations

from storefront.domain.errors import ValidationError
from storefront.domain.money import Money
from storefront.domain.validation import require_state

#: Base sales-tax rate by two-letter state code.
STATE_TAX_RATES: dict[str, float] = {
    "AZ": 0.056,
    "CA": 0.0725,
    "CO": 0.029,
    "CT": 0.0635,
    "DE": 0.0,
    "FL": 0.06,
    "GA": 0.04,
    "IL": 0.0625,
    "MA": 0.0625,
    "MI": 0.06,
    "MN": 0.06875,
    "MT": 0.0,
    "NC": 0.0475,
    "NH": 0.0,
    "NJ": 0.06625,
    "NY": 0.08875,
    "OH": 0.0575,
    "OR": 0.0,
    "PA": 0.06,
    "TX": 0.0625,
    "WA": 0.065,
}


def tax_for(subtotal: Money, state: str) -> Money:
    """Compute the sales tax owed on ``subtotal`` for ``state``.

    Uses :meth:`Money.percent` (half-up rounding to the cent). Raises
    :class:`ValidationError` for malformed or unknown state codes.
    """
    require_state(state)
    rate = STATE_TAX_RATES.get(state)
    if rate is None:
        raise ValidationError(f"no tax rate configured for state {state!r}")
    return subtotal.percent(rate)


def states_with_no_tax() -> list[str]:
    """Return the sorted list of states with a zero sales-tax rate."""
    return sorted(code for code, rate in STATE_TAX_RATES.items() if rate == 0.0)
