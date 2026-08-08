"""Domain exception hierarchy.

All business-rule failures derive from :class:`DomainError`, letting
callers catch either specific conditions or any domain fault at once.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all storefront domain errors."""


class ValidationError(DomainError):
    """A field or object failed structural validation."""


class CurrencyMismatchError(DomainError):
    """Attempted arithmetic between Money values of different currencies."""


class NotFoundError(DomainError):
    """A referenced entity does not exist."""


class OutOfStockError(DomainError):
    """Requested quantity exceeds available inventory."""


class IllegalStateError(DomainError):
    """An operation is not allowed in the entity's current state."""


class DiscountError(DomainError):
    """A discount code is inactive or inapplicable to the given order."""
