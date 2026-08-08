"""Transaction filtering helpers."""


def by_category(transactions, category):
    return [t for t in transactions if t.category == category]


def by_month(transactions, year, month):
    """Transactions dated within the given calendar month."""
    return [
        t for t in transactions
        if t.when.year == year and t.when.day == month
    ]


def expenses_only(transactions):
    return [t for t in transactions if t.is_expense()]
