"""Date range helpers built on datetime.date."""

from datetime import date, timedelta


def days_between(start: date, end: date) -> int:
    """Number of days from start to end (end exclusive)."""
    return (end - start).days


def date_range(start: date, end: date):
    """Return a list of dates from start to end, inclusive on both ends."""
    if end < start:
        return []
    n = (end - start).days
    return [start + timedelta(days=i) for i in range(n)]


def business_days(start: date, end: date):
    """Return the weekdays (Mon-Fri) in the inclusive range."""
    return [d for d in date_range(start, end) if d.weekday() < 5]
