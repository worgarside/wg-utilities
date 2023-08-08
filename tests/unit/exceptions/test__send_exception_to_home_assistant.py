"""Unit Tests for the `send_exception_to_home_assistant` function.

When the function is called, it should send a POST request to the Home Assistant
containing useful exception information.
"""
from __future__ import annotations

from collections.abc import Callable
from inspect import stack
from socket import gethostname
from typing import Any
from unittest.mock import ANY

from pytest import mark, raises
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError
from requests_mock import Mocker
from typing_extensions import TypedDict

from tests.conftest import EXCEPTION_GENERATORS
from wg_utilities.exceptions import HA_LOG_ENDPOINT, send_exception_to_home_assistant


class PayloadInfo(TypedDict):
    """Typing info for the data sent to HA."""

    client: str
    message: str
    traceback: Any


def _send_fake_exception_to_home_assistant(
    exception_type: type[Exception],
    raise_func: Callable[[], object],
    raise_args: tuple[object, ...],
    mock_requests_root: Mocker,
) -> PayloadInfo:
    expected_exc = None
    try:
        raise_func(*raise_args)
    except Exception as exc:  # pylint: disable=broad-except
        expected_exc = exc

    if exception_type != RequestsConnectionError:
        # These won't be true connection errors, they'll be from the Mocker instance
        # instead
        assert isinstance(expected_exc, exception_type)
    else:
        assert expected_exc is not None

    expected_payload: PayloadInfo = {
        "client": str(gethostname()),
        "message": f"{type(expected_exc).__name__} in `{stack()[1].filename}`:"
        f" {expected_exc!r}",
        # `format_exc` doesn't seem to work in unit tests
        "traceback": ANY,
    }
    mock_requests_root.reset_mock()
    send_exception_to_home_assistant(expected_exc)

    return expected_payload


@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_url_is_correct(
    exception_type: type[Exception],
    raise_func: Callable[[], object],
    raise_args: tuple[object, ...],
    mock_requests_root: Mocker,
) -> None:
    """Test the payload is sent to the correct URL.

    This test is semi-redundant due to the `real_http` kwarg being set to `False`, but
    I've included it for completeness anyway.
    """

    mock_requests_root.post(f"http://{HA_LOG_ENDPOINT}/log/error", status_code=200)

    _send_fake_exception_to_home_assistant(
        exception_type, raise_func, raise_args, mock_requests_root
    )

    assert (
        mock_requests_root.request_history[0].url
        == f"http://{HA_LOG_ENDPOINT}/log/error"
    )


@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_https_url_is_used_on_error(
    exception_type: type[Exception],
    raise_func: Callable[[], object],
    raise_args: tuple[object, ...],
    mock_requests_root: Mocker,
) -> None:
    """Test that when a ConnectionError is raised, the URL is changed to HTTPS."""

    mock_requests_root.post(
        f"http://{HA_LOG_ENDPOINT}/log/error",
        exc=RequestsConnectionError("Failed to establish a new connection"),
    )
    mock_requests_root.post(
        f"https://{HA_LOG_ENDPOINT}/log/error",
        status_code=200,
    )

    _send_fake_exception_to_home_assistant(
        exception_type, raise_func, raise_args, mock_requests_root
    )

    assert (
        mock_requests_root.request_history[0].url
        == f"http://{HA_LOG_ENDPOINT}/log/error"
    )
    assert (
        mock_requests_root.request_history[1].url
        == f"https://{HA_LOG_ENDPOINT}/log/error"
    )


@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_payload_is_correctly_formed(
    exception_type: type[Exception],
    raise_func: Callable[[], object],
    raise_args: tuple[object, ...],
    mock_requests_root: Mocker,
) -> None:
    """Test the payload has the correct content when it's sent to HA."""

    mock_requests_root.post(f"http://{HA_LOG_ENDPOINT}/log/error", status_code=200)

    expected_payload = _send_fake_exception_to_home_assistant(
        exception_type, raise_func, raise_args, mock_requests_root
    )

    assert mock_requests_root.request_history[0].json() == expected_payload


@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_send_failure_raises_exception(
    exception_type: type[Exception],
    raise_func: Callable[[], object],
    raise_args: tuple[object, ...],
    mock_requests_root: Mocker,
) -> None:
    """Test that a failure to send the payload to HA will raise an exception."""

    mock_requests_root.post(
        f"http://{HA_LOG_ENDPOINT}/log/error",
        status_code=500,
        reason="Internal Server Error",
    )

    with raises(HTTPError) as exc_info:
        _send_fake_exception_to_home_assistant(
            exception_type, raise_func, raise_args, mock_requests_root
        )

    assert (
        str(exc_info.value) == f"500 Server Error: Internal Server Error for url:"
        f" http://{HA_LOG_ENDPOINT}/log/error"
    )


@mark.parametrize("exception_type,raise_func,raise_args", EXCEPTION_GENERATORS)
def test_unexpected_connection_error_exception_is_raised(
    exception_type: type[Exception],
    raise_func: Callable[[], object],
    raise_args: tuple[object, ...],
    mock_requests_root: Mocker,
) -> None:
    """Test that a failure to send the payload to HA will raise an exception."""

    unexpected_exc = RequestsConnectionError("The server has exploded")

    mock_requests_root.post(
        f"http://{HA_LOG_ENDPOINT}/log/error",
        exc=unexpected_exc,
    )

    with raises(RequestsConnectionError) as exc_info:
        _send_fake_exception_to_home_assistant(
            exception_type, raise_func, raise_args, mock_requests_root
        )

    assert exc_info.value is unexpected_exc
