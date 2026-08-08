"""Numeric parsing and formatting helpers.

CSV sources deliver everything as strings, so the cast/derive ops lean
on these to turn "1,204.50" or " 7 " into usable numbers with clear
error messages when they cannot.
"""

from decimal import Decimal, InvalidOperation


def parse_int(value):
    """Parse an int, tolerating surrounding space and thousands commas.

    Raises ValueError with the offending text in the message.
    """
    if isinstance(value, bool):
        raise ValueError("cannot cast a boolean to int: %r" % value)
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(",", "")
    try:
        return int(text)
    except ValueError:
        raise ValueError("not an integer: %r" % value)


def parse_decimal(value):
    """Parse a Decimal, tolerating surrounding space and a leading currency $."""
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if text.startswith("$"):
        text = text[1:]
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError("not a number: %r" % value)


def format_money(amount):
    """Render a Decimal as a plain 2-dp string for output files."""
    return str(Decimal(amount).quantize(Decimal("0.01")))


def percent(part, whole):
    """part/whole as a float percentage, 0.0 when whole is zero."""
    if not whole:
        return 0.0
    return 100.0 * part / whole


def clamp(value, low, high):
    """Pin `value` into [low, high]."""
    return max(low, min(high, value))
