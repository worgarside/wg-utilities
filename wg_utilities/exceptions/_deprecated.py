"""Deprecated exception handling utilities."""
from __future__ import annotations

from functools import wraps
from inspect import stack
from logging import Logger, getLogger
from os import getenv
from socket import gethostname
from sys import exc_info
from traceback import format_exc
from typing import TYPE_CHECKING, Any

from requests import post
from requests.exceptions import ConnectionError as RequestsConnectionError

from wg_utilities.loggers import add_stream_handler

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


HA_LOG_ENDPOINT = getenv("HA_LOG_ENDPOINT", "homeassistant.local:8001")

LOGGER: Logger | None = None


def send_exception_to_home_assistant(exc: Exception) -> None:
    """Format an exception and send useful info to Home Assistant.

    Args:
        exc (Exception): the exception being handled

    Raises:
        ValueError: if the HA_LOG_ENDPOINT isn't set
        Exception: if posting the exception to HA fails, then an exception is raised
    """
    payload = {
        "client": gethostname(),
        "message": f"{type(exc).__name__} in `{stack()[2].filename}`: {exc!r}",
        "traceback": format_exc(),
    }

    try:
        try:
            # If the host is on the same network as HA, then an HTTP local URL can be
            # used
            res = post(f"http://{HA_LOG_ENDPOINT}/log/error", json=payload, timeout=10)
        except RequestsConnectionError as ha_exc:
            if "Failed to establish a new connection" not in str(ha_exc):
                raise

            res = post(f"https://{HA_LOG_ENDPOINT}/log/error", json=payload, timeout=10)

        res.raise_for_status()
    except Exception as send_exc:
        raise send_exc from exc


def on_exception(
    exception_callback: Callable[[Exception], Any] = send_exception_to_home_assistant,
    *,
    raise_after_callback: bool = True,
    logger: Logger | None = None,
    ignore_exception_types: Iterable[type[Exception]] | None = None,
    default_return_value: Any | None = None,
    _suppress_ignorant_warnings: bool | None = None,
) -> Callable[[Any], Any]:
    """Allow simple cover-all exception handler callback behaviour.

    Args:
        exception_callback (Callable): callback function to process the exception
        raise_after_callback (bool): raise the exception after the callback has run
        logger (Logger): optional logger for logging the exception
        ignore_exception_types (Iterable[type[Exception]]): optional iterable of
            exception types to ignore
        default_return_value (Any): optional default return value for the decorated
            function
        _suppress_ignorant_warnings (bool): optional flag to suppress warnings about
            ignoring exception types

    Returns:
        Callable: the actual decorator
    """

    if default_return_value is not None and raise_after_callback:
        raise ValueError(
            "The `default_return_value` parameter can only be set when"
            " `raise_after_callback` is False.",
        )

    def _decorator(func: Callable[[Any], Any]) -> Callable[[Any, Any], Any]:
        """Allow simple cover-all exception handler callback behaviour.

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
            global LOGGER

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if ignore_exception_types and any(
                    isinstance(exc, exc_type) for exc_type in ignore_exception_types
                ):
                    if (
                        getenv("SUPPRESS_WG_UTILS_IGNORANCE") != "1"
                        and _suppress_ignorant_warnings is None
                    ) or _suppress_ignorant_warnings is False:
                        (
                            logger
                            or LOGGER
                            or (LOGGER := add_stream_handler(getLogger(__name__)))
                        ).warning(
                            "Ignoring exception of type %s in %s.%s. This function has"
                            " ceased executing at line %i. To suppress these warnings"
                            " set the `_suppress_ignorant_warnings` parameter to True"
                            ' or env var `SUPPRESS_WG_UTILS_IGNORANCE` to "1".',
                            type(exc).__name__,
                            func.__module__,
                            func.__name__,
                            exc_info()[2].tb_lineno,  # type: ignore[union-attr]
                        )
                else:
                    exception_callback(exc)

                    if raise_after_callback:
                        raise

                return default_return_value

        return worker

    return _decorator
