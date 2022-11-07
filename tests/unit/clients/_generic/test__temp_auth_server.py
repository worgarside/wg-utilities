"""Unit Tests for `wg_utilities.api.temp_auth_server.TempAuthServer`."""

from __future__ import annotations

from threading import Thread
from unittest.mock import patch

from flask import Flask
from pytest import raises
from requests import get

from wg_utilities.api import TempAuthServer

GET_AUTH_URL = "http://0.0.0.0:5001/get_auth_code"


def test_server_thread_instantiation(flask_app: Flask) -> None:
    """Test `ServerThread` instantiation."""
    st = TempAuthServer.ServerThread(flask_app)

    assert isinstance(st, TempAuthServer.ServerThread)

    assert st.server.host == "0.0.0.0"
    assert st.server.port == 5001
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
    tas = TempAuthServer(__name__, auto_run=False, port=5001)

    assert isinstance(tas, TempAuthServer)

    assert tas.host == "0.0.0.0"
    assert tas.port == 5001
    assert tas.debug is False

    assert tas.app.name == __name__
    assert tas.app.debug is False


def test_temp_auth_server_auto_run() -> None:
    """Test that the `auto_run` argument starts the server."""

    tas = TempAuthServer(__name__, auto_run=True)

    assert tas.running
    assert tas.server.is_alive()

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
    print("testing")
    with patch(
        "wg_utilities.api.temp_auth_server.TempAuthServer.server"
    ) as mock_server:
        temp_auth_server.start_server()

    mock_server.start.assert_called_once_with()


def test_start_server_starts_server(temp_auth_server: TempAuthServer) -> None:
    """Test that the `start_server` method starts a server."""

    assert not temp_auth_server.running

    temp_auth_server.start_server()

    assert temp_auth_server.running
    assert hasattr(temp_auth_server, "_server")
    assert temp_auth_server.server.is_alive()
    assert get(GET_AUTH_URL).json() == {"statusCode": 200}


def test_server_can_be_started_multiple_times(temp_auth_server: TempAuthServer) -> None:
    """Test that the `start_server` method can be called multiple times."""

    temp_auth_server.start_server()
    assert get(GET_AUTH_URL).json() == {"statusCode": 200}
    assert temp_auth_server.running
    assert temp_auth_server.server.is_alive()

    temp_auth_server.stop_server()
    assert not temp_auth_server.running

    temp_auth_server.start_server()
    assert get(GET_AUTH_URL).json() == {"statusCode": 200}
    assert temp_auth_server.running
    assert temp_auth_server.server.is_alive()

    temp_auth_server.stop_server()
    assert not temp_auth_server.running


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

    get(GET_AUTH_URL + "?code=abcdefghijklmnopqrstuvwxyz")

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
        assert temp_auth_server.running
        assert temp_auth_server.wait_for_request(
            "/get_auth_code", max_wait=5, kill_on_request=True
        ) == {
            "code": "abcdefghijklmnopqrstuvwxyz",
        }
        assert not temp_auth_server.running
        called = True

    t = Thread(target=_make_assertions)
    t.start()

    get(GET_AUTH_URL + "?code=abcdefghijklmnopqrstuvwxyz")

    t.join()

    assert called


def test_wait_for_request_starts_server(temp_auth_server: TempAuthServer) -> None:
    """Test the `wait_for_request` method starts the server if it is not running."""

    assert not temp_auth_server.running

    called = False

    def _make_assertions() -> None:
        nonlocal called
        assert not temp_auth_server.running
        assert temp_auth_server.wait_for_request("/get_auth_code", max_wait=5) == {
            "code": "abcdefghijklmnopqrstuvwxyz",
        }
        assert temp_auth_server.running
        called = True

    t = Thread(target=_make_assertions)
    t.start()

    get(GET_AUTH_URL + "?code=abcdefghijklmnopqrstuvwxyz")

    t.join()

    assert called
    assert temp_auth_server.running
