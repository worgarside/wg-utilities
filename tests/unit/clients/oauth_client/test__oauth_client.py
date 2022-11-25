# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.oauth_client.OAuthClient`."""

from __future__ import annotations

from datetime import datetime, timedelta
from http import HTTPStatus
from json import loads
from logging import DEBUG
from pathlib import Path
from re import fullmatch
from threading import Thread
from time import sleep, time
from typing import Any
from unittest.mock import ANY, MagicMock, patch

from freezegun import freeze_time
from pytest import LogCaptureFixture, raises
from requests import HTTPError, get
from requests_mock import Mocker

from conftest import assert_mock_requests_request_history, get_jwt_expiry
from wg_utilities.api import TempAuthServer
from wg_utilities.clients.oauth_client import OAuthClient, OAuthCredentials
from wg_utilities.functions import user_data_dir


def test_oauth_credentials_parse_first_time_login_attributes(
    live_jwt_token: str,
) -> None:
    """Test the OAuthCredentials.parse method for first time login."""
    creds = OAuthCredentials.parse_first_time_login(
        {
            "client_id": "test_client_id",
            "access_token": live_jwt_token,
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "scope": "test_scope",
            "token_type": "Bearer",
        }
    )

    assert creds.access_token == live_jwt_token
    assert creds.refresh_token == "test_refresh_token"
    assert creds.expiry_epoch == get_jwt_expiry(live_jwt_token)
    assert creds.scope == "test_scope"
    assert creds.token_type == "Bearer"
    assert creds.client_id == "test_client_id"
    assert creds.is_expired is False

    with freeze_time(datetime.now() + timedelta(seconds=3600)):
        assert creds.is_expired is True


def test_oauth_credentials_parse_first_time_login_expiry_mismatch() -> None:
    """Test that if `expiry` != the JWT token expiry, an error is raised."""
    with raises(ValueError) as exc_info:
        OAuthCredentials.parse_first_time_login(
            {
                "client_id": "test_client_id",
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                # This is after the JWT token expiry
                "expiry": ((datetime.now() + timedelta(seconds=3700)).isoformat()),
                "expires_in": 3600,
                "scope": "test_scope",
                "token_type": "Bearer",
            }
        )

    assert fullmatch(
        r"^`expiry` and `expires_in` are not consistent with each other: expiry:"
        r" \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3,6}, expires_in: \d+\.?\d*$",
        str(exc_info.value),
    )


def test_oauth_credentials_update_access_token(
    oauth_client: OAuthClient[dict[str, Any]], fake_oauth_credentials: OAuthCredentials
) -> None:
    """Test the `update_access_token` method updates the access token."""
    assert oauth_client.access_token == fake_oauth_credentials.access_token
    assert oauth_client.credentials.expiry_epoch < time() + 3600

    oauth_client.credentials.update_access_token(
        "new_access_token", expires_in=3700, refresh_token="new_refresh_token"
    )
    assert not oauth_client.credentials.expiry_epoch < time() + 3600

    assert oauth_client.access_token == "new_access_token"
    assert oauth_client.credentials.refresh_token == "new_refresh_token"


def test_instantiation(temp_dir: Path) -> None:
    """Test instantiation."""
    client = OAuthClient[dict[str, Any]](
        client_id="test_client_id",
        client_secret="test_client_secret",
        base_url="https://api.example.com",
        access_token_endpoint="https://api.example.com/oauth2/token",
        log_requests=True,
        creds_cache_path=temp_dir / "oauth_credentials" / "test_client_id.json",
        auth_link_base="https://api.example.com/oauth2/authorize",
    )

    assert isinstance(client, OAuthClient)
    assert client.client_id == "test_client_id"
    assert client.client_secret == "test_client_secret"
    assert client.base_url == "https://api.example.com"
    assert client.access_token_endpoint == "https://api.example.com/oauth2/token"
    assert client.redirect_uri == "http://0.0.0.0:5001/get_auth_code"
    assert client.ACCESS_TOKEN_EXPIRY_THRESHOLD == 150
    assert client.log_requests is True
    assert (
        client.creds_cache_path
        == temp_dir / "oauth_credentials" / "test_client_id.json"
    )
    assert client.auth_link_base == "https://api.example.com/oauth2/authorize"


def test_get_method_sends_correct_request(
    oauth_client: OAuthClient[dict[str, Any]],
    mock_requests: Mocker,
    caplog: LogCaptureFixture,
    live_jwt_token: str,
) -> None:
    """Test that the get method sends the correct request."""

    mock_requests.get(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={"key": "value"},
    )

    res = oauth_client._get(
        "/test_endpoint",
        params={"test_param": "test_value"},
    )

    assert res.json() == {"key": "value"}
    assert res.status_code == HTTPStatus.OK
    assert res.reason == HTTPStatus.OK.phrase

    request = mock_requests.request_history.pop(0)

    assert len(mock_requests.request_history) == 0

    assert request.method == "GET"
    assert request.url == "https://api.example.com/test_endpoint?test_param=test_value"
    assert request.headers["Authorization"] == f"Bearer {live_jwt_token}"

    assert caplog.records[0].levelno == DEBUG
    assert caplog.records[0].message == ("GET https://api.example.com/test_endpoint")


def test_get_raises_exception_for_non_200_response(
    oauth_client: OAuthClient[dict[str, Any]], mock_requests: Mocker
) -> None:
    """Test that the get method raises an exception for non-200 responses."""

    mock_requests.get(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.NOT_FOUND,
        reason=HTTPStatus.NOT_FOUND.phrase,
        json={"key": "value"},
    )

    with raises(HTTPError) as exc_info:
        oauth_client._get(
            "/test_endpoint",
            params={"test_param": "test_value"},
        )

    assert exc_info.value.response.status_code == HTTPStatus.NOT_FOUND
    assert exc_info.value.response.reason == HTTPStatus.NOT_FOUND.phrase
    assert exc_info.value.response.json() == {"key": "value"}

    assert (
        str(exc_info.value) == "404 Client Error: Not Found for url: "
        "https://api.example.com/test_endpoint?test_param=test_value"
    )


def test_load_local_credentials(
    oauth_client: OAuthClient[dict[str, Any]],
    fake_oauth_credentials: OAuthCredentials,
) -> None:
    """Test that the load_local_credentials method loads credentials from the cache."""
    del oauth_client._credentials

    assert not hasattr(oauth_client, "_credentials")
    assert oauth_client._load_local_credentials()
    assert oauth_client._credentials == fake_oauth_credentials

    del oauth_client._credentials

    assert not hasattr(oauth_client, "_credentials")
    oauth_client.creds_cache_path.unlink()
    assert not oauth_client._load_local_credentials()
    assert not hasattr(oauth_client, "_credentials")


def test_post_method_sends_correct_request(
    oauth_client: OAuthClient[dict[str, Any]],
    mock_requests: Mocker,
    caplog: LogCaptureFixture,
    live_jwt_token: str,
) -> None:
    """Test that the post method sends the correct request."""

    mock_requests.post(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={"key": "value"},
    )

    res = oauth_client._post(
        "/test_endpoint",
        json={"test_key": "test_value"},
    )

    assert res.json() == {"key": "value"}
    assert res.status_code == HTTPStatus.OK
    assert res.reason == HTTPStatus.OK.phrase

    request = mock_requests.request_history.pop(0)

    assert len(mock_requests.request_history) == 0

    assert request.method == "POST"
    assert request.url == "https://api.example.com/test_endpoint"
    assert request.headers["Authorization"] == f"Bearer {live_jwt_token}"

    assert caplog.records[0].levelno == DEBUG
    assert caplog.records[0].message == ("POST https://api.example.com/test_endpoint")


def test_post_raises_exception_for_non_200_response(
    oauth_client: OAuthClient[dict[str, Any]], mock_requests: Mocker
) -> None:
    """Test that the post method raises an exception for non-200 responses."""

    mock_requests.post(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.NOT_FOUND,
        reason=HTTPStatus.NOT_FOUND.phrase,
    )

    with raises(HTTPError) as exc_info:
        oauth_client._post(
            "/test_endpoint",
        )

    assert exc_info.value.response.status_code == HTTPStatus.NOT_FOUND
    assert exc_info.value.response.reason == HTTPStatus.NOT_FOUND.phrase

    assert (
        str(exc_info.value) == "404 Client Error: Not Found for url: "
        "https://api.example.com/test_endpoint"
    )


def test_delete_creds_file(oauth_client: OAuthClient[dict[str, Any]]) -> None:
    """Test that the `delete_creds_file` method deletes the credentials file."""
    assert oauth_client.creds_cache_path.exists()
    oauth_client.delete_creds_file()
    assert not oauth_client.creds_cache_path.exists()
    oauth_client.delete_creds_file()
    assert not oauth_client.creds_cache_path.exists()


def test_get_json_response(
    oauth_client: OAuthClient[dict[str, Any]], mock_requests: Mocker
) -> None:
    """Test the `get_json_response` method returns the expected JSON object."""
    mock_requests.get(
        "https://api.example.com/test_get_json_response",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={
            "foo": "bar",
            "baz": "qux",
            "quux": "quuz",
            "corge": "grault",
            "garply": "waldo",
            "fred": "plugh",
            "xyzzy": "thud",
        },
    )

    response = oauth_client.get_json_response("/test_get_json_response")

    assert response == {
        "foo": "bar",
        "baz": "qux",
        "quux": "quuz",
        "corge": "grault",
        "garply": "waldo",
        "fred": "plugh",
        "xyzzy": "thud",
    }


def test_get_json_response_no_content(
    oauth_client: OAuthClient[dict[str, Any]], mock_requests: Mocker
) -> None:
    """Test that `get_json_response` returns None if the response has no content."""
    mock_requests.get(
        "https://api.example.com/test_get_json_response_no_content",
        status_code=HTTPStatus.NO_CONTENT,
        reason=HTTPStatus.NO_CONTENT.phrase,
    )

    response = oauth_client.get_json_response("/test_get_json_response_no_content")

    assert isinstance(response, dict)
    assert not response


def test_get_json_response_invalid_response_json(
    oauth_client: OAuthClient[dict[str, Any]], mock_requests: Mocker
) -> None:
    """Test that `get_json_response` returns `{}` if the response has no valid JSON."""
    mock_requests.get(
        "https://api.example.com/test_get_json_response_invalid_response_json",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        text="This is not valid JSON",
    )

    assert (
        oauth_client.get_json_response("/test_get_json_response_invalid_response_json")
        == {}
    )


def test_refresh_access_token(
    oauth_client: OAuthClient[dict[str, Any]],
    live_jwt_token_alt: str,
) -> None:
    """Test the `refresh_access_token` method loads local credentials if needed."""

    del oauth_client._credentials

    assert not hasattr(oauth_client, "_credentials")
    oauth_client.refresh_access_token()
    assert hasattr(oauth_client, "_credentials")

    assert (
        loads(oauth_client.creds_cache_path.read_text())
        == oauth_client.credentials.dict(exclude_none=True)
        == {
            "access_token": live_jwt_token_alt,
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "expiry_epoch": ANY,
            "refresh_token": "new_test_refresh_token",
            "scope": "test_scope,test_scope_two",
            "token_type": "Bearer",
        }
    )


def test_refresh_access_token_with_no_local_credentials(
    oauth_client: OAuthClient[dict[str, Any]]
) -> None:
    """Test the `refresh_access_token` method runs the first time login."""

    oauth_client.creds_cache_path.unlink()
    del oauth_client._credentials

    with patch.object(
        oauth_client, "run_first_time_login"
    ) as mock_run_first_time_login:
        oauth_client.refresh_access_token()

    mock_run_first_time_login.assert_called_once()


@patch("wg_utilities.clients.oauth_client.ascii_letters", "x")
def test_run_first_time_login(
    oauth_client: OAuthClient[dict[str, Any]],
    mock_requests: Mocker,
    mock_open_browser: MagicMock,
    live_jwt_token_alt: str,
) -> None:
    """Test the `run_first_time_login` method runs the correct process."""

    # Remove the credentials cache file so that the credentials are not loaded
    mock_requests.get(
        oauth_client.redirect_uri,
        real_http=True,
    )

    called = False

    def _worker() -> None:
        nonlocal called
        sleep(1)
        res = get(
            "http://0.0.0.0:5001/get_auth_code?code=test_auth_code&state=" + "x" * 32
        )

        assert res.status_code == HTTPStatus.OK
        assert res.reason == HTTPStatus.OK.phrase

        called = True

    t = Thread(target=_worker)
    t.start()

    oauth_client.run_first_time_login()
    t.join()

    mock_open_browser.assert_called_once()
    assert called

    assert not oauth_client.temp_auth_server.is_running

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "http://0.0.0.0:5001/get_auth_code?code=test_auth_code&state="
                + "x" * 32,
                "method": "GET",
                "headers": {},
            },
            {
                "url": "https://api.example.com/oauth2/token",
                "method": "POST",
                "headers": {},
            },
        ],
    )

    assert oauth_client.credentials.dict(exclude_none=True) == {
        "access_token": live_jwt_token_alt,
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "expiry_epoch": ANY,
        "refresh_token": "new_test_refresh_token",
        "scope": "test_scope,test_scope_two",
        "token_type": "Bearer",
    }


@patch("wg_utilities.clients.oauth_client.ascii_letters", "x")
def test_run_time_first_login_validates_state_token(
    oauth_client: OAuthClient[dict[str, Any]],
    mock_requests: Mocker,
    mock_open_browser: MagicMock,
) -> None:
    """Test that an invalid state token throws a ValueError."""

    mock_requests.get(
        oauth_client.redirect_uri,
        real_http=True,
    )

    def _worker() -> None:
        sleep(1)
        res = get(
            "http://0.0.0.0:5001/get_auth_code?code=test_auth_code&state=invalid_value"
        )

        assert res.status_code == HTTPStatus.OK
        assert res.reason == HTTPStatus.OK.phrase
        assert res.json() == {"statusCode": 200}

    t = Thread(target=_worker)
    t.start()

    with raises(ValueError) as exc_info:
        oauth_client.run_first_time_login()

    t.join()
    mock_open_browser.assert_called_once()

    assert (
        str(exc_info.value)
        == "State token received in request doesn't match expected value:"
        f" `invalid_value` != `{'x' * 32}`"
    )


def test_access_token(
    oauth_client: OAuthClient[dict[str, Any]], fake_oauth_credentials: OAuthCredentials
) -> None:
    """Test the `access_token` property returns the expected value."""
    assert oauth_client.access_token == fake_oauth_credentials.access_token


def test_access_token_with_expired_token(
    oauth_client: OAuthClient[dict[str, Any]],
    live_jwt_token: str,
    live_jwt_token_alt: str,
) -> None:
    """Test the `access_token` property refreshes the token when expired."""
    assert oauth_client.access_token == live_jwt_token
    oauth_client.credentials.expiry_epoch = int(time()) - 1

    with patch.object(
        oauth_client, "refresh_access_token", wraps=oauth_client.refresh_access_token
    ) as mock_refresh_access_token:
        assert oauth_client.access_token == live_jwt_token_alt

    mock_refresh_access_token.assert_called_once()


def test_access_token_has_expired(oauth_client: OAuthClient[dict[str, Any]]) -> None:
    """Test the `access_token_has_expired` property returns the expected value."""

    assert oauth_client.access_token_has_expired is False

    oauth_client._credentials.expiry_epoch = int(time()) - 1

    assert oauth_client.access_token_has_expired is True


def test_access_token_has_expired_no_local_credentials(
    oauth_client: OAuthClient[dict[str, Any]],
) -> None:
    """Test the `access_token_has_expired` property returns the expected value."""

    del oauth_client._credentials
    oauth_client.creds_cache_path.unlink()

    assert not hasattr(oauth_client, "_credentials")

    with patch.object(
        oauth_client,
        "_load_local_credentials",
        wraps=oauth_client._load_local_credentials,
    ) as mock_load_local_credentials:
        assert oauth_client.access_token_has_expired is True

    mock_load_local_credentials.assert_called_once()
    assert oauth_client._load_local_credentials() is False


def test_client_id(
    oauth_client: OAuthClient[dict[str, Any]], fake_oauth_credentials: OAuthCredentials
) -> None:
    """Test the `client_id` property returns the expected value."""
    assert oauth_client.client_id == fake_oauth_credentials.client_id


def test_client_secret(
    oauth_client: OAuthClient[dict[str, Any]], fake_oauth_credentials: OAuthCredentials
) -> None:
    """Test the `client_secret` property returns the expected value."""
    assert oauth_client.client_secret == fake_oauth_credentials.client_secret


def test_credentials(
    oauth_client: OAuthClient[dict[str, Any]], fake_oauth_credentials: OAuthCredentials
) -> None:
    """Test the `credentials` property returns the expected value."""
    assert oauth_client.credentials == fake_oauth_credentials

    del oauth_client._credentials
    assert not hasattr(oauth_client, "_credentials")
    with patch.object(
        oauth_client,
        "_load_local_credentials",
        wraps=oauth_client._load_local_credentials,
    ) as mock_load_local_credentials:
        assert oauth_client.credentials == fake_oauth_credentials
    mock_load_local_credentials.assert_called_once()

    del oauth_client._credentials
    oauth_client.creds_cache_path.unlink()
    assert not hasattr(oauth_client, "_credentials")

    def _side_effect() -> None:
        oauth_client._credentials = fake_oauth_credentials

    with patch.object(
        oauth_client, "run_first_time_login"
    ) as mock_run_first_time_login:
        mock_run_first_time_login.side_effect = _side_effect
        assert oauth_client.credentials == fake_oauth_credentials

    mock_run_first_time_login.assert_called_once()


def test_credentials_setter_writes_local_cache(
    oauth_client: OAuthClient[dict[str, Any]],
    fake_oauth_credentials: OAuthCredentials,
    live_jwt_token_alt: str,
) -> None:
    """Test that setting the `credentials` property writes the local cache."""
    assert (
        oauth_client.credentials.dict(exclude_none=True)
        == fake_oauth_credentials.dict(exclude_none=True)
        == loads(oauth_client.creds_cache_path.read_text())
    )

    new_oauth_credentials = OAuthCredentials(
        access_token=live_jwt_token_alt,
        client_id="new_test_client_id",
        client_secret="new_test_client_secret",
        expiry_epoch=int(time()) + 3600,
        refresh_token="new_test_refresh_token",
        scope="new_test_scope",
        token_type="Bearer",
    )

    oauth_client.credentials = new_oauth_credentials
    assert fake_oauth_credentials.dict(exclude_none=True) != loads(
        oauth_client.creds_cache_path.read_text()
    )
    assert new_oauth_credentials.dict(exclude_none=True) == loads(
        oauth_client.creds_cache_path.read_text()
    )


def test_creds_cache_path_raises_value_error_with_no_client_id(
    oauth_client: OAuthClient[dict[str, Any]],
) -> None:
    """Test that `creds_cache_path` raises a ValueError when no `client_id` is set."""
    oauth_client._creds_cache_path = None
    del oauth_client._credentials
    oauth_client._client_id = None

    with raises(ValueError) as exc_info:
        _ = oauth_client.creds_cache_path

    assert (
        str(exc_info.value)
        == "Unable to get client ID to generate path for credentials cache file."
    )


def test_creds_cache_path_returns_expected_value(
    oauth_client: OAuthClient[dict[str, Any]],
) -> None:
    """Test that `creds_cache_path` returns the expected value."""

    oauth_client._creds_cache_path = None
    del oauth_client._credentials

    assert (
        oauth_client.creds_cache_path
        == user_data_dir()
        / "oauth_credentials"
        / "OAuthClient"
        / f"{oauth_client.client_id}.json"
    )


def test_request_headers(
    oauth_client: OAuthClient[dict[str, Any]], fake_oauth_credentials: OAuthCredentials
) -> None:
    """Test the `request_headers` property returns the expected value."""
    assert oauth_client.request_headers == {
        "Authorization": f"Bearer {fake_oauth_credentials.access_token}",
    }


def test_refresh_token(
    oauth_client: OAuthClient[dict[str, Any]], fake_oauth_credentials: OAuthCredentials
) -> None:
    """Test the `refresh_token` property returns the expected value."""
    assert oauth_client.refresh_token == fake_oauth_credentials.refresh_token


def test_temp_auth_server_property(oauth_client: OAuthClient[dict[str, Any]]) -> None:
    """Test the `temp_auth_server` property creates and returns a `TempAuthServer`."""

    assert not hasattr(oauth_client, "_temp_auth_server")

    assert isinstance(oauth_tas := oauth_client.temp_auth_server, TempAuthServer)
    assert oauth_client.temp_auth_server.is_running is True

    assert hasattr(oauth_client, "_temp_auth_server")

    oauth_client.temp_auth_server.stop_server()

    with patch(
        "wg_utilities.clients.oauth_client.TempAuthServer"
    ) as mock_temp_auth_server:
        assert oauth_client.temp_auth_server == oauth_tas
        mock_temp_auth_server.assert_not_called()
