"""Middleware wrappers applied to every route handler.

A "handler" at this level is a callable of one argument::

    handler(request: Request) -> Response

The ``Api`` dispatcher binds the target service to the underlying
handler function first, then decorates the resulting single-argument
callable with the wrappers defined here. Wrappers compose like ordinary
decorators, so ordering matters: the *last* wrapper passed to
``apply_middleware`` sees the request first.
"""

from __future__ import annotations

import functools
from typing import Callable

from storefront.api.errors import to_response
from storefront.api.request import Request
from storefront.api.response import Response

Handler = Callable[[Request], Response]


def with_error_handling(handler: Handler) -> Handler:
    """Wrap ``handler`` so any raised exception becomes an error Response.

    Domain errors are mapped to their spec'd status codes; unexpected
    exceptions become a 500 with a generic message. Handlers therefore
    never need try/except blocks of their own for domain failures.
    """

    @functools.wraps(handler)
    def wrapped(request: Request) -> Response:
        try:
            return handler(request)
        except Exception as exc:  # noqa: BLE001 - boundary catch-all by design
            return to_response(exc)

    return wrapped


def with_logging(logger, handler: Handler) -> Handler:
    """Wrap ``handler`` to log one line per request: method, path, status.

    Successful (2xx) responses log at INFO; client errors (4xx) at
    WARNING; server errors (5xx) at ERROR. Exceptions are not caught
    here — pair with :func:`with_error_handling` (applied inside this
    wrapper) so every request produces a status to log.
    """

    @functools.wraps(handler)
    def wrapped(request: Request) -> Response:
        response = handler(request)
        line = "%s %s -> %d" % (request.method, request.path, response.status)
        if response.status >= 500:
            logger.error(line)
        elif response.status >= 400:
            logger.warning(line)
        else:
            logger.info(line)
        return response

    return wrapped


def apply_middleware(handler: Handler, *wrappers) -> Handler:
    """Apply ``wrappers`` to ``handler`` in order.

    Each wrapper is a callable ``wrapper(handler) -> handler``. Wrappers
    are applied left to right, so the first wrapper ends up innermost
    (closest to the handler) and the last wrapper outermost::

        apply_middleware(h, with_error_handling, logging_wrapper)

    gives ``logging_wrapper(with_error_handling(h))`` — logging sees the
    final status even when the error handler converts an exception.
    """
    wrapped = handler
    for wrapper in wrappers:
        wrapped = wrapper(wrapped)
    return wrapped
