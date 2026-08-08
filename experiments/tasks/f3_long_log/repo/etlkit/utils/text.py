"""Small text helpers used across stages."""


def strip_bom(text):
    """Remove a UTF-8 byte-order mark, which Excel loves to prepend."""
    if text.startswith("﻿"):
        return text[1:]
    return text


def normalize_header(name):
    """Normalize a column header to snake_case.

    "Order ID " -> "order_id"; embedded runs of junk collapse to a
    single underscore so headers stay readable.
    """
    out = []
    prev_us = False
    for ch in strip_bom(name).strip().lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
        elif not prev_us:
            out.append("_")
            prev_us = True
    return "".join(out).strip("_")


def truncate(text, limit=60):
    """Shorten `text` for log lines; never mid-word surgery, just a cut."""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def is_blank(value):
    """True for None or a string of only whitespace."""
    return value is None or (isinstance(value, str) and not value.strip())


def pluralize(count, singular, plural=None):
    """'1 record', '3 records' — keeps log messages grammatical."""
    if count == 1:
        return "%d %s" % (count, singular)
    return "%d %s" % (count, plural or singular + "s")
