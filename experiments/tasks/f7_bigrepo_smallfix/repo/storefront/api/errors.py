"""Translation of domain exceptions into API responses.

Keeps HTTP-status knowledge out of the domain layer: services raise
domain errors and the API boundary maps them to status codes here.
"""

from __future__ import annotations

from storefront.api.response import Response, error
from storefront.domain.errors import (
    CurrencyMismatchError,
    DiscountError,
    DomainError,
    IllegalStateError,
    NotFoundError,
    OutOfStockError,
    ValidationError,
)

_STATUS_BY_TYPE: tuple[tuple[type, int], ...] = (
    (ValidationError, 400),
    (CurrencyMismatchError, 400),
    (DiscountError, 400),
    (NotFoundError, 404),
    (OutOfStockError, 409),
    (IllegalStateError, 409),
)


def status_for(exc: Exception) -> int:
    """Return the HTTP status code for an exception.

    Specific domain errors take precedence; any other ``DomainError``
    is treated as a client error (400) and everything else as a 500.
    """
    for exc_type, status in _STATUS_BY_TYPE:
        if isinstance(exc, exc_type):
            return status
    if isinstance(exc, DomainError):
        return 400
    return 500


def to_response(exc: Exception) -> Response:
    """Convert an exception raised by a handler into a ``Response``.

    Domain errors expose their message to the caller; unexpected errors
    are masked with a generic message so internals do not leak, while
    the exception class name is still reported for debugging.
    """
    status = status_for(exc)
    name = type(exc).__name__
    if status == 500:
        return error(500, "Internal server error.", detail=name)
    message = str(exc) or name
    return error(status, message, detail=name)
