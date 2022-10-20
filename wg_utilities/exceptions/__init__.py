"""Custom exception types"""
from __future__ import annotations

from functools import wraps
from inspect import stack
from logging import Logger, getLogger
from os import getenv
from socket import gethostname
from sys import exc_info
from traceback import format_exc
from typing import Any, Callable, Iterable

from dotenv import load_dotenv
from requests import post

from wg_utilities.loggers import add_stream_handler

load_dotenv()

HA_LOG_ENDPOINT = getenv("HA_LOG_ENDPOINT", "homeassistant.local:8001")

LOGGER: Logger | None = None


class ResourceNotFound(Exception):
    """Custom exception for when some kind of resource isn't found"""


def send_exception_to_home_assistant(exc: Exception) -> None:
    """Format an exception and send useful info to Home Assistant

    Args:
        exc (Exception): the exception being handled

    Raises:
        ValueError: if the HA_LOG_ENDPOINT isn't set
        Exception: if posting the exception to HA fails, then an exception is raised
    """
    payload = {
        "client": gethostname(),
        "message": f"{type(exc).__name__} in `{stack()[2].filename}`: {repr(exc)}",
        "traceback": format_exc(),
    }

    try:
        try:
            # If the host is on the same network as HA, then an HTTP local URL can be
            # used
            post(f"http://{HA_LOG_ENDPOINT}/log/error", json=payload, timeout=10)
        except Exception:  # pylint: disable=broad-except
            post(f"https://{HA_LOG_ENDPOINT}/log/error", json=payload, timeout=10)
    except Exception as send_exc:
        raise send_exc from exc


def on_exception(
    exception_callback: Callable[[Exception], Any] = send_exception_to_home_assistant,
    *,
    raise_after_callback: bool = True,
    logger: Logger | None = None,
    ignore_exception_types: Iterable[type[Exception]] | None = None,
    _suppress_ignorant_warnings: bool | None = None,
) -> Callable[[Any], Any]:
    # pylint: disable=useless-type-doc,useless-param-doc
    """Decorator factory to allow parameterizing the inner decorator

    Args:
        exception_callback (Callable): callback function to process the exception
        raise_after_callback (bool): raise the exception after the callback has run
        logger (Logger): optional logger for logging the exception
        ignore_exception_types (Iterable[type[Exception]]): optional iterable of
            exception types to ignore
        _suppress_ignorant_warnings (bool): optional flag to suppress warnings about
            ignoring exception types

    Returns:
        Callable: the actual decorator
    """

    def _decorator(func: Callable[[Any], Any]) -> Callable[[Any, Any], Any]:
        """Decorator to allow simple cover-all exception handler callback behaviour

        Args:
            func (Callable): the function being wrapped

        Returns:
            Callable: the inner function
        """

        @wraps(func)
        def worker(*args: Any, **kwargs: Any) -> Any:
            """Tries to run the decorated function and calls the callback function

            Args:
                *args (Any): any args passed to the inner func
                **kwargs (Any): any kwargs passed to the inner func

            Returns:
                Any: the result of the wrapped function

            Raises:
                Exception: any exception from the decorated function
            """
            global LOGGER  # pylint: disable=global-statement

            try:
                return func(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
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
                            "Ignoring exception type %s in %s.%s. This function has"
                            " ceased executing at line %i. To suppress these warnings"
                            " set the `_suppress_ignorant_warnings` parameter to True"
                            ' or env var `SUPPRESS_WG_UTILS_IGNORANCE` to "1".',
                            type(exc).__name__,
                            func.__module__,
                            func.__name__,
                            exc_info()[2].tb_lineno,  # type: ignore[union-attr]
                        )

                    return None

                exception_callback(exc)

                if raise_after_callback:
                    raise

                return None

        return worker

    return _decorator


__all__ = ["on_exception", "send_exception_to_home_assistant", "ResourceNotFound"]
