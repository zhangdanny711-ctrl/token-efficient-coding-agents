"""Aggregation over transactions."""

from collections import defaultdict

from .filters import by_month


def totals_by_category(transactions, currency):
    """Sum amounts per category, restricted to the given currency."""
    out = defaultdict(float)
    for t in transactions:
        out[t.category] += t.amount
    return dict(out)


def monthly_net(transactions, year, month, currency):
    """Net amount (income + expenses) for one month in one currency."""
    month_txs = by_month(transactions, year, month)
    return sum(t.amount for t in month_txs if t.currency == currency)
