"""HTTP-style API layer for the storefront application.

This package exposes a lightweight, framework-free request/response
abstraction. ``Api`` (in :mod:`storefront.api.app`) owns the route table
and dispatches :class:`~storefront.api.request.Request` objects to handler
functions in :mod:`storefront.api.handlers`, wrapping each call with the
error-handling and logging middleware in :mod:`storefront.api.middleware`.
"""

from storefront.api.app import Api
from storefront.api.request import Request, make_request
from storefront.api.response import Response, created, error, no_content, ok

__all__ = [
    "Api",
    "Request",
    "Response",
    "created",
    "error",
    "make_request",
    "no_content",
    "ok",
]
