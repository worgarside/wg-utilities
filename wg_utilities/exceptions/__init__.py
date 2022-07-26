"""Custom exception types"""
from __future__ import annotations

from functools import wraps
from inspect import stack
from os import getenv
from socket import gethostname
from traceback import format_exc
from typing import Any, Callable

from dotenv import load_dotenv
from requests import post
from requests.exceptions import SSLError

load_dotenv()

HA_LOG_ENDPOINT = getenv("HA_LOG_ENDPOINT")


class ResourceNotFound(Exception):
    """Custom exception for when some kind of resource isn't found"""


def send_exception_to_home_assistant(exc: Exception) -> None:
    """Format an exception and send useful info to Home Assistant

    Args:
        exc (Exception): the exception being handled

    Raises:
        Exception: if posting the exception to HA fails, then an exception is raised
    """
    payload = {
        "client": gethostname(),
        "message": f"{type(exc).__name__} in `{stack()[2].filename}`: {repr(exc)}",
        "traceback": format_exc(),
    }

    try:
        try:
            post(f"https://{HA_LOG_ENDPOINT}/log/error", json=payload)
        except SSLError:
            # If the host is on the same network as HA, then an HTTP local URL can be
            # used
            post(f"http://{HA_LOG_ENDPOINT}/log/error", json=payload)
    except Exception as send_exc:
        raise send_exc from exc


def on_exception(
    exception_callback: Callable[[Exception], Any] = send_exception_to_home_assistant,
    raise_after_callback: bool = True,
) -> Callable[[Callable[[Any], Any]], Callable[[Any, Any], None]]:
    """Decorator factory to allow parameterizing the inner decorator

    Args:
        exception_callback (Callable): callback function to process the exception
        raise_after_callback (bool): raise the exception after the callback has run

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

            try:
                return func(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                exception_callback(exc)
                if raise_after_callback:
                    raise

                return None

        return worker

    return _decorator


__all__ = ["on_exception", "send_exception_to_home_assistant", "ResourceNotFound"]
