# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.oauth_client.OAuthClient`."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from logging import DEBUG, Logger
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote_plus

from freezegun import freeze_time
from jwt import DecodeError, decode, encode
from pytest import LogCaptureFixture, raises
from requests import HTTPError
from requests_mock import Mocker

from wg_utilities.api import TempAuthServer
from wg_utilities.clients.oauth_client import OAuthClient, OAuthCredentialsInfo
from wg_utilities.functions import DatetimeFixedUnit, utcnow


def test_instantiation(logger: Logger, temp_dir: Path) -> None:
    """Test instantiation."""

    client = OAuthClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        base_url="https://api.example.com",
        access_token_endpoint="https://api.example.com/oauth2/token",
        log_requests=True,
        creds_cache_path=temp_dir / "test_creds_cache.json",
        logger=logger,
    )

    assert isinstance(client, OAuthClient)
    assert client.client_id == "test_client_id"
    assert client.client_secret == "test_client_secret"
    assert client.base_url == "https://api.example.com"
    assert client.access_token_endpoint == "https://api.example.com/oauth2/token"
    assert client.redirect_uri == "http://0.0.0.0:5001/get_auth_code"
    assert client.access_token_expiry_threshold == 60
    assert client.log_requests is True
    assert client.creds_cache_path == temp_dir / "test_creds_cache.json"
    assert client.logger == logger


def test_instantiation_with_no_logger(temp_dir: Path) -> None:
    """Test instantiation with no logger."""

    client = OAuthClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        base_url="https://api.example.com",
        access_token_endpoint="https://api.example.com/oauth2/token",
        log_requests=True,
        creds_cache_path=temp_dir / "test_creds_cache.json",
    )

    assert isinstance(client.logger, Logger)
    assert client.logger.level == DEBUG
    assert client.logger.name == "wg_utilities.clients.oauth_client"


def test_get_method_sends_correct_request(
    oauth_client: OAuthClient, mock_requests: Mocker, caplog: LogCaptureFixture
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
    assert request.headers["Authorization"] == "Bearer test_access_token"

    assert caplog.records[0].levelno == DEBUG
    assert caplog.records[0].message == (
        'GET https://api.example.com/test_endpoint with params {"test_param": '
        '"test_value"}'
    )


def test_get_raises_exception_for_non_200_response(
    oauth_client: OAuthClient, mock_requests: Mocker
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
    oauth_client: OAuthClient,
    fake_oauth_credentials: OAuthCredentialsInfo,
) -> None:
    """Test that the load_local_credentials method loads credentials from the cache."""
    del oauth_client._credentials
    assert not hasattr(oauth_client, "_credentials")

    oauth_client._load_local_credentials()

    assert oauth_client._credentials == fake_oauth_credentials


def test_exchange_auth_code_sends_correct_request(
    oauth_client: OAuthClient, mock_requests: Mocker
) -> None:
    """Test the `exchange_auth_code` method sends the expected request."""

    # Remove the credentials cache file so that the credentials are not loaded
    del oauth_client._credentials
    oauth_client.creds_cache_path.unlink()

    assert not hasattr(oauth_client, "_credentials")
    assert not oauth_client.credentials

    mock_requests.post(
        "https://api.example.com/oauth2/token",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={
            "access_token": "new_test_access_token",
            "client_id": "test_client_id",
            "expires_in": 3600,
            "refresh_token": "new_test_refresh_token",
            "scope": "test_scope,test_scope_two",
            "token_type": "Bearer",
            "user_id": "test_user_id",
        },
    )

    oauth_client.exchange_auth_code("test_auth_code")

    assert oauth_client.credentials == {
        "access_token": "new_test_access_token",
        "client_id": "test_client_id",
        "expires_in": 3600,
        "refresh_token": "new_test_refresh_token",
        "scope": "test_scope,test_scope_two",
        "token_type": "Bearer",
        "user_id": "test_user_id",
    }

    request_data = "&".join(
        [
            f"{k}={quote_plus(v)}"
            for k, v in [
                ("grant_type", "authorization_code"),
                ("client_id", "test_client_id"),
                ("client_secret", "test_client_secret"),
                ("redirect_uri", "http://0.0.0.0:5001/get_auth_code"),
                ("code", "test_auth_code"),
            ]
        ]
    )

    assert mock_requests.request_history[0].method == "POST"
    assert (
        mock_requests.request_history[0].url == "https://api.example.com/oauth2/token"
    )
    assert mock_requests.request_history[0].text == request_data


def test_exchange_auth_code_raises_exception(
    oauth_client: OAuthClient, mock_requests: Mocker
) -> None:
    """Test the `exchange_auth_code` method raises an exception if the request fails."""

    mock_requests.post(
        "https://api.example.com/oauth2/token",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        reason=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
        json={
            "ka": "boom",
        },
    )

    with raises(HTTPError) as exc_info:
        oauth_client.exchange_auth_code("test_auth_code")

    assert exc_info.value.response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc_info.value.response.reason == HTTPStatus.INTERNAL_SERVER_ERROR.phrase
    assert exc_info.value.response.json() == {
        "ka": "boom",
    }

    assert str(exc_info.value) == (
        "500 Server Error: Internal Server Error for url: "
        "https://api.example.com/oauth2/token"
    )


def test_get_json_response(oauth_client: OAuthClient, mock_requests: Mocker) -> None:
    """Test the `get_json_response` method returns the expected JSON object."""
    mock_requests.get(
        "https://api.example.com/test_get_json_response",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={
            "foo": "bar",
            "baz": "qux",
            "quux": "quuz",
            # Thanks, Copilot...
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


def test_refresh_access_token(
    oauth_client: OAuthClient,
    mock_requests: Mocker,
) -> None:
    """Test the `refresh_access_token` method loads local credentials if needed."""

    del oauth_client._credentials

    mock_requests.post(
        "https://api.example.com/oauth2/token",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={
            "access_token": "new_test_access_token",
            "client_id": "test_client_id",
            "expires_in": 3600,
            "refresh_token": "new_test_refresh_token",
            "scope": "test_scope,test_scope_two",
            "token_type": "Bearer",
            "user_id": "test_user_id",
        },
    )

    def _load_local_credentials_side_effect() -> None:
        oauth_client._credentials = {
            "existing": "value",  # type: ignore[typeddict-item]
            "access_token": "this will be overwritten",
        }

    with patch.object(
        oauth_client,
        "_load_local_credentials",
        side_effect=_load_local_credentials_side_effect,
    ) as mock_load_local_credentials:
        assert not hasattr(oauth_client, "_credentials")
        oauth_client.refresh_access_token()
        assert hasattr(oauth_client, "_credentials")

    mock_load_local_credentials.assert_called_once()

    assert oauth_client.credentials == {
        "existing": "value",
        "access_token": "new_test_access_token",
        "client_id": "test_client_id",
        "expires_in": 3600,
        "refresh_token": "new_test_refresh_token",
        "scope": "test_scope,test_scope_two",
        "token_type": "Bearer",
        "user_id": "test_user_id",
    }


def test_access_token(
    oauth_client: OAuthClient, fake_oauth_credentials: OAuthCredentialsInfo
) -> None:
    """Test the `access_token` property returns the expected value."""
    assert oauth_client.access_token == fake_oauth_credentials["access_token"]


def test_access_token_has_expired_with_invalid_token(
    oauth_client: OAuthClient, fake_oauth_credentials: OAuthCredentialsInfo
) -> None:
    """Test the `access_token_has_expired` property returns the expected value."""

    def _load_local_credentials_side_effect() -> None:
        oauth_client._credentials = fake_oauth_credentials

    with raises(DecodeError) as exc_info:
        # The below is how the JWT is decoded in the `access_token_has_expired`
        # property; this is to prove that this is testing the exception path.
        decode(
            fake_oauth_credentials["access_token"],
            options={"verify_signature": False},
        ).get("exp", 0)

    assert str(exc_info.value) == "Not enough segments"

    with patch.object(
        oauth_client,
        "_load_local_credentials",
        side_effect=_load_local_credentials_side_effect,
    ):
        assert oauth_client.access_token_has_expired is True

    # Now just to prove that `KeyError`s are caught too
    del oauth_client._credentials["access_token"]  # type: ignore[misc]

    assert oauth_client.access_token_has_expired is True


def test_access_token_has_expired_with_valid_token(oauth_client: OAuthClient) -> None:
    """Test the `access_token_has_expired` property returns the expected value."""

    oauth_client._load_local_credentials()
    oauth_client._credentials["access_token"] = encode(
        # TODO remove the `int` cast once the overloading is done
        {"exp": utcnow(DatetimeFixedUnit.SECOND) + 120},  # type: ignore[operator]
        "secret",
        algorithm="HS256",
    )

    assert oauth_client.access_token_has_expired is False

    with freeze_time(utcnow() + timedelta(seconds=121)):  # type: ignore[operator]
        assert oauth_client.access_token_has_expired is True


def test_refresh_token(
    oauth_client: OAuthClient, fake_oauth_credentials: OAuthCredentialsInfo
) -> None:
    """Test the `refresh_token` property returns the expected value."""
    assert oauth_client.refresh_token == fake_oauth_credentials["refresh_token"]


def test_temp_auth_server_property(oauth_client: OAuthClient) -> None:
    """Test the `temp_auth_server` property creates and returns a `TempAuthServer`."""

    assert not hasattr(oauth_client, "_temp_auth_server")

    assert isinstance(oauth_tas := oauth_client.temp_auth_server, TempAuthServer)
    assert oauth_client.temp_auth_server.running is True

    assert hasattr(oauth_client, "_temp_auth_server")

    oauth_client.temp_auth_server.stop_server()

    with patch(
        "wg_utilities.clients.oauth_client.TempAuthServer"
    ) as mock_temp_auth_server:
        assert oauth_client.temp_auth_server == oauth_tas
        mock_temp_auth_server.assert_not_called()
