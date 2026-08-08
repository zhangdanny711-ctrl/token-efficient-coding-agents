"""Logging helpers.

The library never configures handlers on its own beyond a
``NullHandler`` (per stdlib guidance), leaving output policy to the
application embedding it.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def get_logger(name: str) -> logging.Logger:
    """Return a logger for ``name`` with a NullHandler attached once.

    Safe to call repeatedly; the NullHandler is only added if the
    logger does not already have one.
    """
    logger = logging.getLogger(name)
    if not any(isinstance(h, logging.NullHandler) for h in logger.handlers):
        logger.addHandler(logging.NullHandler())
    return logger


def log_call(logger: logging.Logger) -> Callable[[F], F]:
    """Decorator factory that debug-logs each call to the wrapped function.

    Logs the function name plus its positional and keyword arguments at
    DEBUG level before delegating to the original function.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if logger.isEnabledFor(logging.DEBUG):
                arg_parts = [repr(a) for a in args]
                arg_parts.extend(f"{k}={v!r}" for k, v in kwargs.items())
                logger.debug("call %s(%s)", func.__name__, ", ".join(arg_parts))
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
