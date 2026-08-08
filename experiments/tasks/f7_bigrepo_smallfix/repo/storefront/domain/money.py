"""Exact integer-cent money value object.

All monetary amounts in the storefront are represented as an integer
number of cents plus an ISO currency code. Decimal parsing and
formatting never round-trips through ``float``; percentages use
``decimal`` with half-up rounding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from storefront.domain.errors import CurrencyMismatchError, ValidationError

_DECIMAL_RE = re.compile(r"^(-?)(\d+)(?:\.(\d{1,2}))?$")

_CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}


@dataclass(frozen=True)
class Money:
    """An immutable amount of money in a single currency.

    ``cents`` is the total amount in the currency's minor unit;
    ``Money(1234)`` is $12.34.
    """

    cents: int
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not isinstance(self.cents, int) or isinstance(self.cents, bool):
            raise ValidationError(f"cents must be an int, got {type(self.cents).__name__}")
        if not isinstance(self.currency, str) or len(self.currency) != 3:
            raise ValidationError(f"currency must be a 3-letter code, got {self.currency!r}")

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def zero(cls, currency: str = "USD") -> "Money":
        """Return a zero amount in ``currency``."""
        return cls(0, currency)

    @classmethod
    def from_decimal_string(cls, s: str, currency: str = "USD") -> "Money":
        """Parse an exact decimal string like ``"12.34"`` into Money.

        Accepts an optional sign and at most two fractional digits.
        Never goes through ``float``, so no representation error is
        possible. Raises :class:`ValidationError` on malformed input.
        """
        if not isinstance(s, str):
            raise ValidationError(f"expected a decimal string, got {type(s).__name__}")
        match = _DECIMAL_RE.match(s.strip())
        if match is None:
            raise ValidationError(f"not a valid decimal amount: {s!r}")
        sign, whole, frac = match.groups()
        frac = (frac or "").ljust(2, "0")
        cents = int(whole) * 100 + int(frac)
        if sign == "-":
            cents = -cents
        return cls(cents, currency)

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def _require_same_currency(self, other: "Money", op: str) -> None:
        if not isinstance(other, Money):
            raise ValidationError(f"cannot {op} Money and {type(other).__name__}")
        if other.currency != self.currency:
            raise CurrencyMismatchError(
                f"cannot {op} {self.currency} and {other.currency}"
            )

    def add(self, other: "Money") -> "Money":
        """Return the sum of this amount and ``other`` (same currency)."""
        self._require_same_currency(other, "add")
        return Money(self.cents + other.cents, self.currency)

    def sub(self, other: "Money") -> "Money":
        """Return this amount minus ``other`` (same currency)."""
        self._require_same_currency(other, "subtract")
        return Money(self.cents - other.cents, self.currency)

    def mul(self, qty: int) -> "Money":
        """Return this amount multiplied by an integer quantity."""
        if not isinstance(qty, int) or isinstance(qty, bool):
            raise ValidationError(f"quantity must be an int, got {type(qty).__name__}")
        if qty < 0:
            raise ValidationError(f"quantity must be non-negative, got {qty}")
        return Money(self.cents * qty, self.currency)

    def percent(self, rate: float) -> "Money":
        """Return ``rate`` (a fraction, e.g. 0.0725 for 7.25%) of this amount.

        Rounds half up to the nearest cent using ``decimal`` so results
        are exact and reproducible.
        """
        if not isinstance(rate, (int, float)) or isinstance(rate, bool):
            raise ValidationError(f"rate must be a number, got {type(rate).__name__}")
        if rate < 0:
            raise ValidationError(f"rate must be non-negative, got {rate}")
        raw = Decimal(self.cents) * Decimal(str(rate))
        rounded = raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return Money(int(rounded), self.currency)

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------

    def to_decimal_string(self) -> str:
        """Render as a plain decimal string, e.g. ``"12.34"``."""
        sign = "-" if self.cents < 0 else ""
        magnitude = abs(self.cents)
        return f"{sign}{magnitude // 100}.{magnitude % 100:02d}"

    def format(self) -> str:
        """Render for display, e.g. ``"$12.34"`` or ``"CAD 12.34"``."""
        symbol = _CURRENCY_SYMBOLS.get(self.currency)
        if symbol is not None:
            return f"{symbol}{self.to_decimal_string()}"
        return f"{self.currency} {self.to_decimal_string()}"

    # ------------------------------------------------------------------
    # Predicates and comparisons
    # ------------------------------------------------------------------

    def is_zero(self) -> bool:
        """True when the amount is exactly zero."""
        return self.cents == 0

    def __lt__(self, other: "Money") -> bool:
        self._require_same_currency(other, "compare")
        return self.cents < other.cents

    def __le__(self, other: "Money") -> bool:
        self._require_same_currency(other, "compare")
        return self.cents <= other.cents

    def __gt__(self, other: "Money") -> bool:
        self._require_same_currency(other, "compare")
        return self.cents > other.cents

    def __ge__(self, other: "Money") -> bool:
        self._require_same_currency(other, "compare")
        return self.cents >= other.cents

    def __str__(self) -> str:
        return self.format()
