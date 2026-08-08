"""Small text-manipulation helpers used for slugs, display names, etc."""

from __future__ import annotations

import re

_SLUG_INVALID = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")

# Short words kept lowercase in title_case unless first or last.
_MINOR_WORDS = frozenset(
    {"a", "an", "and", "as", "at", "but", "by", "for", "in",
     "nor", "of", "on", "or", "the", "to", "up"}
)


def slugify(s: str) -> str:
    """Convert ``s`` to a URL-safe slug.

    Lowercases, replaces runs of non-alphanumeric characters with a
    single hyphen, and strips leading/trailing hyphens.

    >>> slugify("  Deluxe Espresso Machine! ")
    'deluxe-espresso-machine'
    """
    lowered = s.lower()
    slug = _SLUG_INVALID.sub("-", lowered)
    return slug.lstrip("-")


def normalize_ws(s: str) -> str:
    """Collapse all runs of whitespace to single spaces and trim ends.

    >>> normalize_ws("  hello \\t world\\n")
    'hello world'
    """
    return _WS.sub(" ", s).strip()


def truncate(s: str, n: int, suffix: str = "...") -> str:
    """Shorten ``s`` to at most ``n`` characters, appending ``suffix``.

    If the string already fits within ``n`` characters it is returned
    unchanged. The suffix counts against the limit; if ``n`` is smaller
    than the suffix itself, a plain hard cut is used.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if len(s) <= n:
        return s
    if n <= len(suffix):
        return s[:n]
    return s[: n - len(suffix)].rstrip() + suffix


def title_case(s: str) -> str:
    """Convert ``s`` to headline-style title case.

    Minor words ("of", "the", "and", ...) stay lowercase unless they
    are the first or last word.

    >>> title_case("the art of the deal")
    'The Art of the Deal'
    """
    words = normalize_ws(s).split(" ")
    if not words or words == [""]:
        return ""
    result: list[str] = []
    last = len(words) - 1
    for i, word in enumerate(words):
        lower = word.lower()
        if 0 < i < last and lower in _MINOR_WORDS:
            result.append(lower)
        else:
            result.append(lower[:1].upper() + lower[1:])
    return " ".join(result)
