"""Response object and helpers used by API handlers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Response:
    """An in-process representation of an HTTP response.

    Attributes:
        status: HTTP status code (200, 201, 204, 400, 404, 409, 500, ...).
        body: JSON-safe dict payload. Empty for 204 responses.
    """

    status: int
    body: dict


def ok(body: dict) -> Response:
    """200 OK with the given payload."""
    return Response(status=200, body=body)


def created(body: dict) -> Response:
    """201 Created with the given payload."""
    return Response(status=201, body=body)


def no_content() -> Response:
    """204 No Content with an empty payload."""
    return Response(status=204, body={})


def error(status: int, message: str, detail: str | None = None) -> Response:
    """An error response with a standard ``{"error": ..., "message": ...}`` shape.

    Args:
        status: HTTP error status code.
        message: Human-readable summary of the failure.
        detail: Optional machine-oriented detail, typically the exception
            class name; stored under ``body["error"]``.
    """
    body: dict = {"error": detail or "Error", "message": message}
    return Response(status=status, body=body)
