from datetime import date

from ledger import Transaction, by_month, monthly_net, totals_by_category

TXS = [
    Transaction(date(2026, 3, 1), -20.0, "USD", "food"),
    Transaction(date(2026, 3, 5), -30.0, "USD", "food"),
    Transaction(date(2026, 3, 5), -100.0, "EUR", "food"),
    Transaction(date(2026, 3, 10), 500.0, "USD", "salary"),
    Transaction(date(2026, 4, 2), -40.0, "USD", "food"),
]


def test_by_month_uses_calendar_month():
    march = by_month(TXS, 2026, 3)
    assert len(march) == 4
    assert all(t.when.month == 3 for t in march)


def test_totals_by_category_respects_currency():
    t = totals_by_category(TXS, "USD")
    assert t["food"] == -90.0  # EUR transaction must be excluded
    assert t["salary"] == 500.0


def test_monthly_net():
    assert monthly_net(TXS, 2026, 3, "USD") == 450.0
    assert monthly_net(TXS, 2026, 4, "USD") == -40.0
