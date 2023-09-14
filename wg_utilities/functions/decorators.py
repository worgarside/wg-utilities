"""Custom decorators."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from logging import Logger
from random import random
from time import sleep
from typing import Any


def backoff(
    exceptions: type[Exception] | tuple[type[Exception], ...] = Exception,
    /,
    logger: Logger | None = None,
    *,
    max_tries: int = 10,
    max_delay: int = 60,
) -> Callable[[Any], Any]:
    """Apply an exponential backoff to the decorated function.

        The function will be called until it succeeds or the maximum number of tries,
        with an exponential delay between tries (up to the maximum delay).

    Args:
        exceptions (type[Exception] | tuple[type[Exception], ...]): the exception(s) to catch
        logger (Logger): optional logger for logging the exception
        max_tries (int): the maximum number of tries
        max_delay (int): the maximum delay in seconds between tries

    Returns:
        Callable: the actual decorator
    """

    def _decorator(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
        """Apply an exponential backoff to the decorated function.

        The function will be called until it succeeds or the maximum number of tries,
        with an exponential delay between tries (up to the maximum delay).

        Args:
            func (Callable): the function being wrapped

        Returns:
            Callable: the inner function
        """

        @wraps(func)
        def worker(*args: Any, **kwargs: Any) -> Any:
            """Try to run the decorated function and calls the callback function.

            Args:
                *args (Any): any args passed to the inner func
                **kwargs (Any): any kwargs passed to the inner func

            Returns:
                Any: the result of the wrapped function

            Raises:
                Exception: any exception from the decorated function
            """

            tries = 0
            delay = 0.1
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # pylint: disable=broad-except
                    if logger is not None:
                        logger.warning(
                            "Exception caught in backoff decorator (attempt %i/%i): %s %s",
                            tries,
                            max_tries,
                            type(exc).__name__,
                            exc,
                        )
                    tries += 1

                    if tries >= max_tries:
                        raise

                    sleep(delay)
                    delay = min(delay * (2 + random()), max_delay)  # noqa: S311

        return worker

    return _decorator
