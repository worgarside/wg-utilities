"""Unit tests specifically for the exception handler decorator."""

from __future__ import annotations

from collections.abc import Callable
from os import environ
from unittest.mock import patch

from pytest import LogCaptureFixture, mark, raises
from requests_mock import Mocker

from tests.conftest import EXCEPTION_GENERATORS
from wg_utilities.exceptions import HA_LOG_ENDPOINT, on_exception


def test_decorated_function_is_called_correctly_without_exception() -> None:
    """Test the decorated function is called as expected when no exception is raised.

    The decorated function should be called with the same arguments as it was
    originally called with.
    """

    called_args = None
    called_kwargs = None

    @on_exception(exception_callback=lambda _: None)
    def worker(*args: int, **kwargs: int) -> None:
        nonlocal called_args, called_kwargs
        called_args = args
        called_kwargs = kwargs

    worker(1, 2, kwarg1=3, kwarg2=4)

    assert called_args == (1, 2)
    assert called_kwargs == {"kwarg1": 3, "kwarg2": 4}


def test_decorated_functions_value_is_returned() -> None:
    """Test that the decorated function's value is returned.

    The decorated function's return value(s) should be returned correctly when no
    exception is raised.
    """

    @on_exception(exception_callback=lambda _: None)
    def worker(*args: int) -> int:
        return sum(args)

    assert worker(1, 2, 3, 4) == 10


def test_exception_is_sent_to_ha_by_default(mock_requests_root: Mocker) -> None:
    """Test that the exception is sent to Home Assistant by default."""

    mock_requests_root.post(f"http://{HA_LOG_ENDPOINT}/log/error", status_code=200)

    @on_exception(raise_after_callback=False)
    def worker() -> None:
        raise Exception("Test Exception")  # pylint: disable=broad-exception-raised

    assert worker() is None

    assert (
        mock_requests_root.request_history[0].url
        == f"http://{HA_LOG_ENDPOINT}/log/error"
    )


@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_decorator_catches_exception_and_calls_callback_correctly(
    exception_type: (
        type[AttributeError]
        | type[FileNotFoundError]
        | type[IsADirectoryError]
        | type[IndexError]
        | type[KeyError]
        | type[LookupError]
        | type[NameError]
        | type[TypeError]
        | type[UnicodeError]
        | type[UnicodeEncodeError]
        | type[ValueError]
        | type[ZeroDivisionError]
    ),
    raise_func: Callable[..., object],
    raise_args: tuple[object, ...],
) -> None:
    """Test that the decorator catches exceptions of varying types."""

    exception = None

    def _cb(
        exc: Exception,
    ) -> None:
        nonlocal exception
        exception = exc
        assert isinstance(exc, exception_type)

    with raises(exception_type) as exc_info:

        @on_exception(exception_callback=_cb)
        def worker() -> None:
            raise_func(*raise_args)

        worker()

    # This is to ensure that the `raises` statement is catching the correct exception
    # and nothing weird is going on inside the decorator.
    assert exc_info.value is exception


@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_false_raise_after_callback_does_not_raise(
    exception_type: type[Exception],
    raise_func: Callable[..., object],
    raise_args: tuple[object, ...],
) -> None:
    """Test that the correct exception is raised when `raise_after_callback` is True."""

    called = False
    finished = False
    exception = None

    def _cb(
        exc: Exception,
    ) -> None:
        nonlocal exception
        exception = exc
        assert isinstance(exc, exception_type)

    @on_exception(raise_after_callback=False, exception_callback=_cb)
    def worker() -> None:
        nonlocal called, finished
        called = True
        raise_func(*raise_args)
        finished = True  # pragma: no cover

    worker()
    assert called is True
    assert finished is False
    assert isinstance(exception, exception_type)


@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_ignore_exception_types(
    exception_type: type[Exception],
    raise_func: Callable[..., object],
    raise_args: tuple[object, ...],
) -> None:
    """Test that the decorator ignores exceptions of the specified types."""

    called = False
    finished = False

    @on_exception(
        raise_after_callback=True,
        exception_callback=lambda _: None,
        ignore_exception_types=[exception_type],
    )
    def worker() -> None:
        nonlocal called, finished
        called = True
        raise_func(*raise_args)
        finished = True  # pragma: no cover

    worker()
    assert called is True
    assert finished is False


@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_ignoring_exceptions_is_logged_as_warning(
    exception_type: type[Exception],
    raise_func: Callable[..., object],
    raise_args: tuple[object, ...],
    caplog: LogCaptureFixture,
) -> None:
    """Test that ignoring exceptions is logged as a warning.

    The warning should be logged with the correct information.
    """

    called = False
    finished = False

    @on_exception(
        raise_after_callback=True,
        exception_callback=lambda _: None,
        ignore_exception_types=[exception_type],
    )
    def worker() -> None:
        nonlocal called, finished
        called = True
        raise_func(*raise_args)
        finished = True  # pragma: no cover

    worker()
    assert called is True
    assert finished is False

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"

    # Can't test for these because a child exception type is raised
    if exception_type not in (LookupError, UnicodeError):
        assert (
            f"Ignoring exception of type {exception_type.__name__} in"
            f" test__on_exception.worker." in caplog.records[0].message
        )


@patch.dict(environ, {"SUPPRESS_WG_UTILS_IGNORANCE": "0"})
@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_ignorant_warning_suppression_via_parameter(
    exception_type: type[Exception],
    raise_func: Callable[..., object],
    raise_args: tuple[object, ...],
    caplog: LogCaptureFixture,
) -> None:
    """Test that the warning suppression for ignoring exceptions works as expected.

    Either the parameter and the environment variable (or both) should disable any
    logging output with regards to ignoring exceptions. This test is concerned with
    the former.
    """

    @on_exception(
        raise_after_callback=True,
        exception_callback=lambda _: None,
        ignore_exception_types=[exception_type],
        _suppress_ignorant_warnings=True,
    )
    def worker() -> None:
        raise_func(*raise_args)

    worker()

    assert environ["SUPPRESS_WG_UTILS_IGNORANCE"] != "1"
    assert len(caplog.records) == 0


@patch.dict(environ, {"SUPPRESS_WG_UTILS_IGNORANCE": "1"})
@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_ignorant_warning_suppression_via_env_var(
    exception_type: type[Exception],
    raise_func: Callable[..., object],
    raise_args: tuple[object, ...],
    caplog: LogCaptureFixture,
) -> None:
    """Test that the warning suppression for ignoring exceptions works as expected.

    Either the parameter and the environment variable (or both) should disable any
    logging output with regards to ignoring exceptions. This test is concerned with
    the latter.
    """

    @on_exception(
        raise_after_callback=True,
        exception_callback=lambda _: None,
        ignore_exception_types=[exception_type],
    )
    def worker() -> None:
        raise_func(*raise_args)

    caplog.clear()
    worker()

    assert len(caplog.records) == 0


def test_default_return_value() -> None:
    """Test that the default return value is returned correctly."""

    @on_exception(str, raise_after_callback=False, default_return_value="default")
    def worker() -> None:
        raise Exception("Test Exception")  # pylint: disable=broad-exception-raised

    assert worker() == "default"


def test_default_return_value_with_raise_after_callback() -> None:
    """Test that the default return value is returned correctly."""

    @on_exception(str, raise_after_callback=True, default_return_value="default")
    def worker() -> None:
        raise Exception("Test Exception")  # pylint: disable=broad-exception-raised

    assert worker() == "default"
