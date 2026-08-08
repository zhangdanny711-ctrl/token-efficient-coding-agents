"""Request object used by the API dispatch layer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Request:
    """An in-process representation of an HTTP request.

    Attributes:
        method: Uppercase HTTP verb, e.g. ``"GET"`` or ``"POST"``.
        path: Request path such as ``"/orders/ord-1/pay"``.
        params: Query-string style parameters plus any path parameters
            captured during routing (e.g. ``{"order_id": "ord-1"}``).
        body: Parsed JSON body for write requests, or ``None``.
    """

    method: str
    path: str
    params: dict = field(default_factory=dict)
    body: dict | None = None


def make_request(method: str, path: str, body: dict | None = None, **params) -> Request:
    """Convenience constructor for building requests in code and tests.

    Keyword arguments become query parameters::

        make_request("GET", "/products", q="mug")
    """
    return Request(method=method.upper(), path=path, params=dict(params), body=body)
