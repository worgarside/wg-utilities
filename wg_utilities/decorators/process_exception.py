"""Custom decorator for processing a thrown exception."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from logging import Logger


def process_exception(
    exceptions: type[Exception] | tuple[type[Exception], ...] = Exception,
    /,
    logger: Logger | None = None,
    *,
    callback: Callable[[Exception], Any] | None = None,
    raise_after_processing: bool = True,
    default_return_value: Any | None = None,
) -> Callable[[Any], Any]:
    """Allow simple cover-all exception processing/logging, with optional suppression.

    Args:
        exceptions (type[Exception] | tuple[type[Exception], ...]): the exception(s) to catch
        logger (Logger): optional logger for logging the exception
        callback (Callable): callback function to process the exception
        raise_after_processing (bool): raise the exception after the processing is
            complete
        default_return_value (Any): optional default return value for the decorated
            function

    Returns:
        Callable: the actual decorator
    """

    if default_return_value is not None and raise_after_processing:
        raise ValueError(
            "The `default_return_value` parameter can only be set when"
            " `raise_after_processing` is False.",
        )

    def _decorator(func: Callable[[Any], Any]) -> Callable[[Any, Any], Any]:
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

            try:
                return func(*args, **kwargs)
            except exceptions as exc:
                if logger is not None:
                    logger.exception(
                        "%s %s in %s.%s: %s",
                        type(exc).__name__,
                        "thrown" if raise_after_processing else "caught",
                        func.__module__,
                        func.__qualname__,
                        str(exc),  # noqa: TRY401
                    )

                if callback is not None:
                    callback(exc)

                if raise_after_processing:
                    raise

                return default_return_value

        return worker

    return _decorator
