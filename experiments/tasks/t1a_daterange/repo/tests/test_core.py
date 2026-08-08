from datetime import date

from daterange import business_days, date_range, days_between


def test_days_between():
    assert days_between(date(2026, 1, 1), date(2026, 1, 4)) == 3


def test_date_range_inclusive():
    r = date_range(date(2026, 1, 1), date(2026, 1, 3))
    assert r == [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]


def test_date_range_single_day():
    assert date_range(date(2026, 5, 5), date(2026, 5, 5)) == [date(2026, 5, 5)]


def test_date_range_reversed():
    assert date_range(date(2026, 1, 3), date(2026, 1, 1)) == []


def test_business_days():
    # 2026-01-02 is a Friday, 2026-01-05 is a Monday.
    r = business_days(date(2026, 1, 2), date(2026, 1, 5))
    assert r == [date(2026, 1, 2), date(2026, 1, 5)]
