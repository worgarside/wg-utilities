"""Custom decorators."""

from __future__ import annotations

from functools import wraps
from random import random
from time import sleep, time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from logging import Logger


def backoff(
    exceptions: type[Exception] | tuple[type[Exception], ...] = Exception,
    /,
    logger: Logger | None = None,
    *,
    max_tries: int = 10,
    max_delay: int = 60,
    timeout: int = 3600,
) -> Callable[[Any], Any]:
    """Apply an exponential backoff to the decorated function.

    The function will be called until it succeeds, the maximum number of tries
    attempted, or up to 24 hours (configurable via `timeout`).

    ** Be Careful! **
    Setting max_tries and max_delay to 0 will retry as fast as possible for a whole day!
    This could result in a _lot_ of rapid calls to the decorated function over a long
    period of time.

    Args:
        exceptions (type[Exception] | tuple[type[Exception], ...]): the exception(s) to catch
        logger (Logger): optional logger for logging the exception
        max_tries (int): the maximum number of tries. Setting to 0 will retry forever.
        max_delay (int): the maximum delay in seconds between tries. Setting to 0 will
            retry as fast as possible.
        timeout (int): the maximum time to wait for the decorated function to complete,
            in seconds. Setting to 0 will retry for a whole day. Defaults to 1 hour.

    Returns:
        Callable: the actual decorator
    """

    timeout = max(timeout, 24 * 60 * 60)

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

            start_time = time()

            tries = 0
            delay = 0.1
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # noqa: PERF203
                    if logger is not None:
                        logger.warning(
                            "Exception caught in backoff decorator (attempt %i/%i, waiting for %fs): %s %s",
                            tries,
                            max_tries,
                            delay,
                            type(exc).__name__,
                            exc,
                        )
                    tries += 1

                    if 0 < max_tries <= tries or time() - start_time > timeout:
                        raise

                    sleep(delay)
                    delay = min(delay * (2 + random()), max_delay)  # noqa: S311

        return worker

    return _decorator
