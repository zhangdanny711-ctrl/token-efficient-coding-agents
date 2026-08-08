"""Reusable field validators.

Each validator raises :class:`ValidationError` with a message that
names the offending field, and returns the (possibly unchanged) value
so validators can be chained inline in constructors.
"""

from __future__ import annotations

import re
from typing import Any, Collection, Type

from storefront.domain.errors import ValidationError

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_STATE_RE = re.compile(r"^[A-Z]{2}$")


def require_non_empty(value: str, field: str) -> str:
    """Ensure ``value`` is a string with non-whitespace content."""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValidationError(f"{field} must not be empty")
    return value


def require_positive(value: int, field: str) -> int:
    """Ensure ``value`` is an integer strictly greater than zero."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{field} must be an int, got {type(value).__name__}")
    if value <= 0:
        raise ValidationError(f"{field} must be positive, got {value}")
    return value


def require_non_negative(value: int, field: str) -> int:
    """Ensure ``value`` is an integer greater than or equal to zero."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{field} must be an int, got {type(value).__name__}")
    if value < 0:
        raise ValidationError(f"{field} must be non-negative, got {value}")
    return value


def require_email(value: str) -> str:
    """Ensure ``value`` looks like an email address (simple pattern)."""
    if not isinstance(value, str) or _EMAIL_RE.match(value) is None:
        raise ValidationError(f"invalid email address: {value!r}")
    return value


def require_state(code: str) -> str:
    """Ensure ``code`` is a two-letter uppercase US state/territory code."""
    if not isinstance(code, str) or _STATE_RE.match(code) is None:
        raise ValidationError(f"invalid state code: {code!r} (expected two uppercase letters)")
    return code


def require_in(value: Any, allowed: Collection[Any], field: str) -> Any:
    """Ensure ``value`` is one of the values in ``allowed``."""
    if value not in allowed:
        choices = ", ".join(repr(a) for a in sorted(allowed, key=repr))
        raise ValidationError(f"{field} must be one of {choices}; got {value!r}")
    return value


def require_type(value: Any, typ: Type, field: str) -> Any:
    """Ensure ``value`` is an instance of ``typ``."""
    if not isinstance(value, typ):
        raise ValidationError(
            f"{field} must be {typ.__name__}, got {type(value).__name__}"
        )
    return value
