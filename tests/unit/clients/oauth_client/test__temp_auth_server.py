# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.api.temp_auth_server.TempAuthServer`."""

from __future__ import annotations

from http import HTTPStatus
from threading import Thread
from time import sleep
from unittest.mock import patch

from flask import Flask
from pytest import raises
from requests import get
from werkzeug.serving import BaseWSGIServer, make_server

from wg_utilities.api import TempAuthServer


def test_server_thread_instantiation(flask_app: Flask) -> None:
    """Test `ServerThread` instantiation."""
    st = TempAuthServer.ServerThread(flask_app)

    assert isinstance(st, TempAuthServer.ServerThread)

    assert st.server.host == "0.0.0.0"
    assert isinstance(st.server.port, int)
    assert st.server.port > 0
    assert st.ctx.app == flask_app


def test_server_thread_run_serves_forever(
    server_thread: TempAuthServer.ServerThread,
) -> None:
    """Test that the `ServerThread.run` method serves forever."""

    with patch.object(server_thread.server, "serve_forever") as mock_serve_forever:
        server_thread.run()

    mock_serve_forever.assert_called_once_with()


def test_server_thread_shutdown(server_thread: TempAuthServer.ServerThread) -> None:
    """Test the `ServerThread.shutdown` method."""

    with patch.object(server_thread.server, "shutdown") as mock_shutdown:
        server_thread.shutdown()

    mock_shutdown.assert_called_once_with()


def test_temp_auth_server_instantiation() -> None:
    """Test `TempAuthServer` instantiation."""
    tas = TempAuthServer(__name__, auto_run=False, port=1234)

    assert isinstance(tas, TempAuthServer)

    assert tas.host == "0.0.0.0"
    assert tas._user_port == 1234
    assert tas.debug is False

    assert tas.app.name == __name__
    assert tas.app.debug is False


def test_temp_auth_server_auto_run() -> None:
    """Test that the `auto_run` argument starts the server."""

    tas = TempAuthServer(__name__, auto_run=True, port=0)

    assert tas.is_running
    assert tas.server_thread.is_alive()

    tas.stop_server()


def test_create_endpoints(temp_auth_server: TempAuthServer) -> None:
    """Test that the `create_endpoints` method adds two endpoints."""

    rules = list(temp_auth_server.app.url_map.iter_rules())

    assert [rule.rule for rule in rules] == [
        "/static/<path:filename>",
        "/get_auth_code",
    ]


def test_start_server_starts_thread(temp_auth_server: TempAuthServer) -> None:
    """Test that the `start_server` method starts a thread."""
    with patch(
        "wg_utilities.api.temp_auth_server.TempAuthServer.server_thread"
    ) as mock_server:
        temp_auth_server.start_server()

    mock_server.start.assert_called_once_with()


def test_start_server_starts_server(temp_auth_server: TempAuthServer) -> None:
    """Test that the `start_server` method starts a server."""

    assert not temp_auth_server.is_running

    temp_auth_server.start_server()

    assert temp_auth_server.is_running
    assert hasattr(temp_auth_server, "_server_thread")
    assert temp_auth_server.server_thread.is_alive()
    assert (
        get(temp_auth_server.get_auth_code_url, timeout=2.5).status_code
        == HTTPStatus.OK
    )
    assert (
        "Authentication Complete"
        in get(temp_auth_server.get_auth_code_url, timeout=2.5).text
    )


def test_server_can_be_started_multiple_times(temp_auth_server: TempAuthServer) -> None:
    """Test that the `start_server` method can be called multiple times."""

    temp_auth_server.start_server()
    assert (
        get(temp_auth_server.get_auth_code_url, timeout=2.5).status_code
        == HTTPStatus.OK
    )
    assert (
        "Authentication Complete"
        in get(temp_auth_server.get_auth_code_url, timeout=2.5).text
    )
    assert temp_auth_server.is_running
    assert temp_auth_server.server_thread.is_alive()

    temp_auth_server.stop_server()
    assert not temp_auth_server.is_running

    temp_auth_server.start_server()
    assert (
        get(temp_auth_server.get_auth_code_url, timeout=2.5).status_code
        == HTTPStatus.OK
    )
    assert (
        "Authentication Complete"
        in get(temp_auth_server.get_auth_code_url, timeout=2.5).text
    )
    assert temp_auth_server.is_running
    assert temp_auth_server.server_thread.is_alive()

    temp_auth_server.stop_server()
    assert not temp_auth_server.is_running


def test_wait_for_request(temp_auth_server: TempAuthServer) -> None:
    """Test that the `wait_for_request` method waits for a request."""

    temp_auth_server.start_server()

    called = False

    def _make_assertions() -> None:
        nonlocal called
        assert temp_auth_server.wait_for_request("/get_auth_code", max_wait=5) == {
            "code": "abcdefghijklmnopqrstuvwxyz",
        }
        called = True

    t = Thread(target=_make_assertions)
    t.start()

    get(temp_auth_server.get_auth_code_url + "?code=abcdefghijklmnopqrstuvwxyz")

    t.join()

    assert called


def test_wait_for_request_timeout(temp_auth_server: TempAuthServer) -> None:
    """Test that the `wait_for_request` method times out."""

    temp_auth_server.start_server()

    with raises(TimeoutError) as exc_info:
        temp_auth_server.wait_for_request("/get_auth_code", max_wait=1)

    assert (
        str(exc_info.value) == "No request received to /get_auth_code within 1 seconds"
    )


def test_wait_for_request_kill_on_request(temp_auth_server: TempAuthServer) -> None:
    """Test that the `wait_for_request` method kills the server on request."""

    temp_auth_server.start_server()

    called = False

    def _make_assertions() -> None:
        nonlocal called
        assert temp_auth_server.is_running
        assert temp_auth_server.wait_for_request(
            "/get_auth_code", max_wait=5, kill_on_request=True
        ) == {
            "code": "abcdefghijklmnopqrstuvwxyz",
        }
        assert not temp_auth_server.is_running
        called = True

    t = Thread(target=_make_assertions)
    t.start()

    get(temp_auth_server.get_auth_code_url + "?code=abcdefghijklmnopqrstuvwxyz")

    t.join()

    assert called


def test_wait_for_request_starts_server(temp_auth_server: TempAuthServer) -> None:
    """Test the `wait_for_request` method starts the server if it is not is_running."""

    assert not temp_auth_server.is_running

    called = False

    def _make_assertions() -> None:
        nonlocal called
        assert not temp_auth_server.is_running
        assert temp_auth_server.wait_for_request("/get_auth_code", max_wait=5) == {
            "code": "abcdefghijklmnopqrstuvwxyz",
        }
        assert temp_auth_server.is_running
        called = True

    t = Thread(target=_make_assertions)
    t.start()

    sleep(1)

    get(
        temp_auth_server.get_auth_code_url + "?code=abcdefghijklmnopqrstuvwxyz",
        timeout=5,
    )

    t.join()

    assert called
    assert temp_auth_server.is_running


def test_get_auth_code_url_property(temp_auth_server: TempAuthServer) -> None:
    """Test the `get_auth_code_url` property returns the correct URL."""

    with raises(ValueError) as exc_info:
        _ = temp_auth_server.get_auth_code_url

    assert str(exc_info.value) == "Server is not running"

    temp_auth_server.start_server()

    assert temp_auth_server.get_auth_code_url == temp_auth_server.get_auth_code_url


def test_port_allocation(temp_auth_server: TempAuthServer) -> None:
    """Test that the `start_server` method allocates a port."""

    assert not temp_auth_server.is_running

    def make_server_side_effect(host: str, port: int, app: Flask) -> BaseWSGIServer:
        if port < 5015:
            raise OSError("Address already in use")

        return make_server(host, port, app)  # type: ignore[no-any-return]

    with patch(
        "wg_utilities.api.temp_auth_server.make_server",
        side_effect=make_server_side_effect,
    ):
        temp_auth_server.start_server()

    assert temp_auth_server.is_running
    assert temp_auth_server.port == 5015

    temp_auth_server.stop_server()
    assert not temp_auth_server.is_running


def test_port_allocation_fails(temp_auth_server: TempAuthServer) -> None:
    """Test that `start_server` raises an exception if it cannot allocate a port."""

    assert not temp_auth_server.is_running

    with patch(
        "wg_utilities.api.temp_auth_server.make_server",
        side_effect=OSError("Address already in use"),
    ), raises(OSError) as exc_info:
        temp_auth_server.start_server()

    assert str(exc_info.value) == "No available ports in range 5000-5020"
    assert not temp_auth_server.is_running


def test_hard_port_allocation(temp_auth_server: TempAuthServer) -> None:
    """Test that the `start_server` only tries one port if it is set by the user."""

    assert not temp_auth_server.is_running

    temp_auth_server.port = 5015

    def make_server_side_effect(host: str, port: int, app: Flask) -> BaseWSGIServer:
        if port == 5015:
            raise OSError("Address already in use")

        return make_server(host, port, app)  # type: ignore[no-any-return]

    with patch(
        "wg_utilities.api.temp_auth_server.make_server",
        side_effect=make_server_side_effect,
    ), raises(OSError) as exc_info:
        temp_auth_server.start_server()

    assert str(exc_info.value) == "Address already in use"


def test_port_setter_raises_exception(temp_auth_server: TempAuthServer) -> None:
    """Test that the `port` setter raises an exception if the server is running."""

    assert not temp_auth_server.is_running

    temp_auth_server.start_server()

    assert temp_auth_server.is_running

    with raises(ValueError) as exc_info:
        temp_auth_server.port = 5015

    assert str(exc_info.value) == "Cannot set port while server is running"

    temp_auth_server.stop_server()
    assert not temp_auth_server.is_running
