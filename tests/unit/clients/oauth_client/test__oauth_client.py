# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.oauth_client.OAuthClient`."""

from __future__ import annotations

from datetime import datetime, timedelta
from http import HTTPStatus
from json import loads
from pathlib import Path
from re import fullmatch
from threading import Thread
from time import sleep, time
from typing import Any
from unittest.mock import ANY, MagicMock, patch
from urllib.parse import urlencode

import pytest
from freezegun import freeze_time
from requests import get
from requests_mock import Mocker

from tests.conftest import assert_mock_requests_request_history
from tests.unit.clients.oauth_client.conftest import get_jwt_expiry
from wg_utilities.api import TempAuthServer
from wg_utilities.clients.oauth_client import (
    BaseModelWithConfig,
    OAuthClient,
    OAuthCredentials,
)
from wg_utilities.functions import user_data_dir


def test_x_model_with_config_has_correct_config() -> None:
    """Check the `Config` options for `BaseModelWithConfig` are correct."""

    assert BaseModelWithConfig.model_config["arbitrary_types_allowed"] is True
    assert BaseModelWithConfig.model_config["extra"] == "ignore"
    assert BaseModelWithConfig.model_config["validate_assignment"] is True


def test_oauth_credentials_parse_first_time_login_attributes(
    live_jwt_token: str,
) -> None:
    """Test the `OAuthCredentials.parse` method for first time login."""
    creds = OAuthCredentials.parse_first_time_login(
        {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
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
    assert creds.client_secret == "test_client_secret"
    assert creds.is_expired is False

    with freeze_time(datetime.utcnow() + timedelta(seconds=3600)):
        assert creds.is_expired is True


def test_oauth_credentials_parse_first_time_login_expiry_mismatch() -> None:
    """Test that if `expiry` != the JWT token expiry, an error is raised."""
    with pytest.raises(ValueError) as exc_info:
        OAuthCredentials.parse_first_time_login(
            {
                "client_id": "test_client_id",
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                # This is after the JWT token expiry
                "expiry": ((datetime.utcnow() + timedelta(seconds=3700)).isoformat()),
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
    assert oauth_client.credentials.expiry_epoch == pytest.approx(
        int(time()) + 3600, abs=5
    )

    oauth_client.credentials.update_access_token(
        "new_access_token", expires_in=7200, refresh_token="new_refresh_token"
    )
    assert oauth_client.credentials.expiry_epoch == pytest.approx(
        int(time()) + 7200, abs=5
    )

    assert oauth_client.access_token == "new_access_token"
    assert oauth_client.credentials.refresh_token == "new_refresh_token"


def test_oauth_credentials_is_expired_property(
    fake_oauth_credentials: OAuthCredentials,
) -> None:
    """Test the `is_expired` property."""
    assert fake_oauth_credentials.is_expired is False

    with freeze_time(datetime.fromtimestamp(fake_oauth_credentials.expiry_epoch + 1)):
        assert fake_oauth_credentials.is_expired is True


def test_instantiation(
    temp_dir: Path, fake_oauth_credentials: OAuthCredentials
) -> None:
    """Test instantiation."""
    client = OAuthClient[dict[str, Any]](
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
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
    assert client.ACCESS_TOKEN_EXPIRY_THRESHOLD == 150
    assert client.log_requests is True
    assert (
        client.creds_cache_path
        == temp_dir / "oauth_credentials" / "test_client_id.json"
    )
    assert client.auth_link_base == "https://api.example.com/oauth2/authorize"

    assert client.DEFAULT_CACHE_DIR is None
    assert not client.DEFAULT_PARAMS
    assert isinstance(client.DEFAULT_PARAMS, dict)


def test_load_local_credentials(
    oauth_client: OAuthClient[dict[str, Any]],
    fake_oauth_credentials: OAuthCredentials,
) -> None:
    """Test that the `load_local_credentials` method loads creds from the cache."""
    del oauth_client._credentials

    assert not hasattr(oauth_client, "_credentials")
    assert oauth_client._load_local_credentials()
    assert oauth_client._credentials == fake_oauth_credentials

    del oauth_client._credentials

    assert not hasattr(oauth_client, "_credentials")
    oauth_client.creds_cache_path.unlink()
    assert not oauth_client._load_local_credentials()
    assert not hasattr(oauth_client, "_credentials")


def test_delete_creds_file(oauth_client: OAuthClient[dict[str, Any]]) -> None:
    """Test that the `delete_creds_file` method deletes the credentials file."""
    assert oauth_client.creds_cache_path.exists()
    oauth_client.delete_creds_file()
    assert not oauth_client.creds_cache_path.exists()
    oauth_client.delete_creds_file()
    assert not oauth_client.creds_cache_path.exists()


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
        == oauth_client.credentials.model_dump(exclude_none=True)
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

    oauth_client.temp_auth_server.start_server()

    called = False

    def _worker() -> None:
        nonlocal called
        sleep(1)
        res = get(
            # pylint: disable=line-too-long
            f"{oauth_client.temp_auth_server.get_auth_code_url}?code=test_auth_code&state={'x' * 32}",
            timeout=5,
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
                # pylint: disable=line-too-long
                "url": f"{oauth_client.temp_auth_server.get_auth_code_url}?code=test_auth_code&state={'x' * 32}",
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

    assert oauth_client.credentials.model_dump(exclude_none=True) == {
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
    mock_open_browser: MagicMock,
) -> None:
    """Test that an invalid state token throws a ValueError."""

    called = False

    def _worker() -> None:
        nonlocal called
        sleep(1)
        res = get(
            # pylint: disable=line-too-long
            f"{oauth_client.temp_auth_server.get_auth_code_url}?code=test_auth_code&state=invalid_value",
            timeout=5,
        )

        assert res.status_code == HTTPStatus.OK
        assert res.reason == HTTPStatus.OK.phrase

        called = True

    t = Thread(target=_worker)
    t.start()

    with pytest.raises(ValueError) as exc_info:
        oauth_client.run_first_time_login()

    t.join()
    mock_open_browser.assert_called_once()

    assert (
        str(exc_info.value)
        == "State token received in request doesn't match expected value:"
        f" `invalid_value` != `{'x' * 32}`"
    )
    assert called


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
        oauth_client.credentials.model_dump(exclude_none=True)
        == fake_oauth_credentials.model_dump(exclude_none=True)
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
    assert fake_oauth_credentials.model_dump(exclude_none=True) != loads(
        oauth_client.creds_cache_path.read_text()
    )
    assert new_oauth_credentials.model_dump(exclude_none=True) == loads(
        oauth_client.creds_cache_path.read_text()
    )


def test_creds_cache_path_raises_value_error_with_no_client_id(
    oauth_client: OAuthClient[dict[str, Any]],
) -> None:
    """Test that `creds_cache_path` raises a ValueError when no `client_id` is set."""
    oauth_client._creds_cache_path = None
    del oauth_client._credentials
    oauth_client._client_id = None

    with pytest.raises(ValueError) as exc_info:
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


@patch.object(
    OAuthClient,
    "DEFAULT_CACHE_DIR",
    str(Path(__file__).parent / ".wg-utilities" / "oauth_credentials"),
)
def test_creds_cache_path_with_env_var(
    fake_oauth_credentials: OAuthCredentials,
) -> None:
    """Test `creds_cache_path` returns the expected value when the env var is set.

    I've had to patch the `DEFAULT_CACHE_DIR` attribute because I can't set the env
    var for _just_ this test.
    """

    oauth_client: OAuthClient[dict[str, Any]] = OAuthClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
        base_url="https://api.example.com",
        access_token_endpoint="https://api.example.com/oauth2/token",
        log_requests=True,
        auth_link_base="https://api.example.com/oauth2/authorize",
    )

    assert (
        str(Path(__file__).parent / ".wg-utilities" / "oauth_credentials")
        == oauth_client.DEFAULT_CACHE_DIR
    )

    assert oauth_client.creds_cache_path == (
        Path(__file__).parent
        / ".wg-utilities"
        / "oauth_credentials"
        / "OAuthClient"
        / f"{oauth_client.client_id}.json"
    )


@patch.object(
    OAuthClient,
    "DEFAULT_CACHE_DIR",
    str(Path(__file__).parent / ".wg-utilities" / "oauth_credentials"),
)
def test_creds_cache_dir(fake_oauth_credentials: OAuthCredentials) -> None:
    """Test `creds_cache_dir` overrides the default value."""

    oauth_client: OAuthClient[dict[str, Any]] = OAuthClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
        base_url="https://api.example.com",
        access_token_endpoint="https://api.example.com/oauth2/token",
        log_requests=True,
        creds_cache_dir=Path(__file__).parent
        / ".wg-utilities"
        / "a_different_directory",
        auth_link_base="https://api.example.com/oauth2/authorize",
    )

    assert (
        str(Path(__file__).parent / ".wg-utilities" / "oauth_credentials")
        == oauth_client.DEFAULT_CACHE_DIR
    )

    assert oauth_client.creds_cache_path == (
        Path(__file__).parent
        / ".wg-utilities"
        / "a_different_directory"
        / "OAuthClient"
        / f"{oauth_client.client_id}.json"
    )


def test_request_headers(
    oauth_client: OAuthClient[dict[str, Any]], live_jwt_token: str
) -> None:
    """Test the `request_headers` property returns the expected value."""
    assert oauth_client.request_headers == {
        "Authorization": f"Bearer {live_jwt_token}",
        "Content-Type": "application/json",
    }


def test_refresh_token(
    oauth_client: OAuthClient[dict[str, Any]], fake_oauth_credentials: OAuthCredentials
) -> None:
    """Test the `refresh_token` property returns the expected value."""
    assert oauth_client.refresh_token == fake_oauth_credentials.refresh_token


def test_temp_auth_server_property(oauth_client: OAuthClient[dict[str, Any]]) -> None:
    """Test the `temp_auth_server` property creates and returns a `TempAuthServer`."""

    assert not hasattr(oauth_client, "_temp_auth_server")

    oauth_tas = oauth_client.temp_auth_server

    assert isinstance(oauth_tas, TempAuthServer)
    assert oauth_client.temp_auth_server.is_running is False

    assert hasattr(oauth_client, "_temp_auth_server")

    oauth_client.temp_auth_server.stop_server()

    with patch(
        "wg_utilities.clients.oauth_client.TempAuthServer"
    ) as mock_temp_auth_server:
        assert oauth_client.temp_auth_server == oauth_tas
        mock_temp_auth_server.assert_not_called()


@pytest.mark.parametrize(
    "redirect_uri_override", [None, "https://some-proxy-site.com/path/to/stuff"]
)
@patch.object(
    OAuthClient,
    "HEADLESS_MODE",
    new=True,
)
@patch("wg_utilities.clients.oauth_client.ascii_letters", "x")
@patch("wg_utilities.clients.oauth_client.open_browser")
def test_headless_mode_first_time_login(
    mock_open_browser: MagicMock,
    oauth_client: OAuthClient[dict[str, Any]],
    mock_requests: Mocker,
    live_jwt_token_alt: str,
    redirect_uri_override: str | None,
) -> None:
    """Test the `run_first_time_login` calls the callback correctly.

    `redirect_uri` is parameterised to test that the auth link is formed correctly.
    """

    if redirect_uri_override:
        oauth_client.oauth_redirect_uri_override = redirect_uri_override

    headless_cb_called = False

    def _cb(auth_link: str) -> None:
        nonlocal headless_cb_called, redirect_uri_override

        # pylint: disable=line-too-long
        expected_redirect_uri = (
            redirect_uri_override
            or f"http://{oauth_client.oauth_login_redirect_host}:{oauth_client.temp_auth_server.port}/get_auth_code"
        )

        assert auth_link == oauth_client.auth_link_base + "?" + urlencode(
            {
                "client_id": oauth_client.client_id,
                "redirect_uri": expected_redirect_uri,
                "response_type": "code",
                "state": "x" * 32,
                "access_type": "offline",
                "prompt": "consent",
            }
        )

        sleep(1)

        res = get(
            oauth_client.temp_auth_server.get_auth_code_url
            + "?"
            + urlencode({"code": "test_auth_code", "state": "x" * 32}),
            timeout=5,
        )

        assert res.status_code == HTTPStatus.OK
        assert res.reason == HTTPStatus.OK.phrase

        headless_cb_called = True

    oauth_client.headless_auth_link_callback = _cb

    oauth_client.run_first_time_login()

    assert headless_cb_called
    mock_open_browser.assert_not_called()

    assert not oauth_client.temp_auth_server.is_running

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                # pylint: disable=line-too-long
                "url": f"{oauth_client.temp_auth_server.get_auth_code_url}?code=test_auth_code&state={'x' * 32}",
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

    assert oauth_client.credentials.model_dump(exclude_none=True) == {
        "access_token": live_jwt_token_alt,
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "expiry_epoch": ANY,
        "refresh_token": "new_test_refresh_token",
        "scope": "test_scope,test_scope_two",
        "token_type": "Bearer",
    }


@patch.object(
    OAuthClient,
    "HEADLESS_MODE",
    new=True,
)
@patch("wg_utilities.clients.oauth_client.ascii_letters", "x")
@patch("wg_utilities.clients.oauth_client.open_browser")
def test_headless_mode_first_time_login_missing_callback(
    mock_open_browser: MagicMock,
    oauth_client: OAuthClient[dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the `run_first_time_login` logs the auth link with no callback."""

    oauth_client.scopes = ["test_scope", "test_scope_two"]

    with patch.object(OAuthClient, "temp_auth_server") as mock_temp_auth_server:
        mock_temp_auth_server.port = 5000
        mock_temp_auth_server.wait_for_request.return_value = {
            "state": "x" * 32,
            "code": "test_auth_code",
        }
        oauth_client.run_first_time_login()

    mock_open_browser.assert_not_called()

    assert (
        "Headless mode is enabled, but no headless auth link callback "
        "has been set. The auth link will not be opened."
    ) in caplog.text

    auth_link_params = {
        "client_id": oauth_client.client_id,
        "redirect_uri": "http://localhost:5000/get_auth_code",
        "response_type": "code",
        "state": "x" * 32,
        "access_type": "offline",
        "prompt": "consent",
        "scope": "test_scope test_scope_two",
    }

    assert (
        f"Auth link: {oauth_client.auth_link_base}?{urlencode(auth_link_params)}"
    ) in caplog.text


def test_use_existing_credentials_only(
    oauth_client: OAuthClient[dict[str, Any]]
) -> None:
    """Test that the `use_existing_credentials_only` property works correctly."""

    oauth_client.use_existing_credentials_only = True

    with pytest.raises(
        RuntimeError,
        match="^No existing credentials found, and `use_existing_credentials_only` is "
        "set to True$",
    ):
        oauth_client.run_first_time_login()


def test_creds_rel_file_path_no_client_id(
    oauth_client: OAuthClient[dict[str, Any]]
) -> None:
    """Test that `None` is returns when there is no client ID available."""

    oauth_client._client_id = None
    del oauth_client._credentials

    assert oauth_client._creds_rel_file_path is None
