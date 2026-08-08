"""Core data model for the ledger."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Transaction:
    when: date
    amount: float  # positive = income, negative = expense
    currency: str  # ISO code, e.g. "USD"
    category: str

    def is_expense(self) -> bool:
        return self.amount < 0
