"""Unit tests specifically for the exception handler decorator."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

import pytest

from tests.conftest import EXCEPTION_GENERATORS, TEST_EXCEPTION, TestError
from wg_utilities.decorators import process_exception

if TYPE_CHECKING:
    from collections.abc import Callable


def test_decorated_function_is_called_correctly_without_exception() -> None:
    """Test the decorated function is called as expected when no exception is raised.

    The decorated function should be called with the same arguments as it was
    originally called with.
    """

    called_args = None
    called_kwargs = None

    @process_exception(callback=lambda _: None)
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

    @process_exception(callback=lambda _: None)
    def worker(*args: int) -> int:
        return sum(args)

    assert worker(1, 2, 3, 4) == 10


@pytest.mark.parametrize(
    ("exception_type", "raise_func", "raise_args"),
    EXCEPTION_GENERATORS,
)
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

    with pytest.raises(exception_type) as exc_info:  # noqa: PT012

        @process_exception(callback=_cb)
        def worker() -> None:
            raise_func(*raise_args)

        worker()

    # This is to ensure that the `raises` statement is catching the correct exception
    # and nothing weird is going on inside the decorator.
    assert exc_info.value is exception


@pytest.mark.parametrize(
    ("exception_type", "raise_func", "raise_args"),
    EXCEPTION_GENERATORS,
)
def test_false_raise_after_processing_does_not_raise(
    exception_type: type[Exception],
    raise_func: Callable[..., object],
    raise_args: tuple[object, ...],
) -> None:
    """Test that the correct exception is raised when `raise_after_processing` is True."""

    called = False
    finished = False
    exception = None

    def _cb(
        exc: Exception,
    ) -> None:
        nonlocal exception
        exception = exc
        assert isinstance(exc, exception_type)

    @process_exception(raise_after_processing=False, callback=_cb)
    def worker() -> None:
        nonlocal called, finished
        called = True
        raise_func(*raise_args)
        finished = True  # pragma: no cover

    worker()
    assert called is True
    assert finished is False
    assert isinstance(exception, exception_type)


@pytest.mark.parametrize(
    ("exception_type", "raise_func", "raise_args"),
    EXCEPTION_GENERATORS,
)
def test_exception_types(
    exception_type: type[Exception],
    raise_func: Callable[..., object],
    raise_args: tuple[object, ...],
) -> None:
    """Test that the decorator only catches exceptions of the specified types."""

    called = False
    finished = False

    @process_exception(
        exception_type,
        raise_after_processing=False,
    )
    def worker() -> None:
        nonlocal called, finished
        called = True
        raise_func(*raise_args)
        finished = True  # pragma: no cover

    worker()
    assert called is True
    assert finished is False

    # Test the inverse

    @process_exception(
        exception_type,
        raise_after_processing=False,
    )
    def inverse_worker() -> None:
        raise TEST_EXCEPTION

    with pytest.raises(TestError):
        inverse_worker()


def test_default_return_value() -> None:
    """Test that the default return value is returned correctly."""

    @process_exception(raise_after_processing=False, default_return_value="default")
    def worker() -> None:
        raise TEST_EXCEPTION

    assert worker() == "default"


def test_default_return_value_with_raise_after_processing() -> None:
    """Test that the default return value is returned correctly."""

    with pytest.raises(ValueError) as exc_info:

        @process_exception(
            TestError,
            raise_after_processing=True,
            default_return_value="default",
        )
        def _() -> None:  # pragma: no cover
            raise TEST_EXCEPTION

    assert (
        str(exc_info.value) == "The `default_return_value` parameter can only be set when"
        " `raise_after_processing` is False."
    )


def test_logging(caplog: pytest.LogCaptureFixture) -> None:
    """Test that the exception is logged correctly."""

    @process_exception(
        TestError,
        logger=getLogger("test_logging"),
        raise_after_processing=False,
    )
    def worker() -> None:
        raise TEST_EXCEPTION

    worker()

    assert caplog.record_tuples == [
        (
            "test_logging",
            40,
            "TestError caught in test__process_exception.test_logging.<locals>.worker: Test Exception",
        ),
    ]
