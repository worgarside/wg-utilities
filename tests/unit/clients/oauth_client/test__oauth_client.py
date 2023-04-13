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
from unittest.mock import ANY, MagicMock, call, patch

from freezegun import freeze_time
from pydantic import BaseModel, Extra
from pytest import LogCaptureFixture, mark, raises
from requests import HTTPError, get, post
from requests_mock import Mocker

from tests.conftest import assert_mock_requests_request_history
from tests.unit.clients.oauth_client.conftest import get_jwt_expiry
from wg_utilities.api import TempAuthServer
from wg_utilities.clients.oauth_client import (
    BaseModelWithConfig,
    GenericModelWithConfig,
    OAuthClient,
    OAuthCredentials,
)
from wg_utilities.functions import user_data_dir


@mark.parametrize("model_class", (BaseModelWithConfig, GenericModelWithConfig))
def test_x_model_with_config_has_correct_config(model_class: BaseModel) -> None:
    """Check the `Config` options for `Base/GenericModelWithConfig` are correct."""

    assert model_class.__config__.arbitrary_types_allowed is True
    assert model_class.__config__.extra == Extra.forbid
    assert model_class.__config__.validate_assignment is True


@mark.parametrize(
    "attribute_value",
    (
        0,
        -1,
        2,
        False,
        True,
        "a",
        "abc",
        ["a", "b", 1, 2],
        {"a", "b", 1, 2},
        {"a": "b", 1: 2},
    ),
)
@mark.parametrize("model_class", (BaseModelWithConfig, GenericModelWithConfig))
def test_x_model_with_config_set_private_attr_method(
    model_class: type[BaseModelWithConfig | GenericModelWithConfig],
    attribute_value: int | bool | str | list[Any] | set[Any] | dict[str, Any],
) -> None:
    """Check the `Config` options for `Base/GenericModelWithConfig` are correct."""

    instance = model_class()

    assert not hasattr(instance, "_attribute")

    instance._set_private_attr("_attribute", attribute_value)

    assert instance._attribute == attribute_value  # type: ignore[union-attr]

    with raises(ValueError) as exc_info:
        instance._set_private_attr("attribute", attribute_value)

    assert str(exc_info.value) == "Only private attributes can be set via this method."


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
    with raises(ValueError) as exc_info:
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
    assert oauth_client.credentials.expiry_epoch < time() + 3600

    oauth_client.credentials.update_access_token(
        "new_access_token", expires_in=3700, refresh_token="new_refresh_token"
    )
    assert not oauth_client.credentials.expiry_epoch < time() + 3600

    assert oauth_client.access_token == "new_access_token"
    assert oauth_client.credentials.refresh_token == "new_refresh_token"


def test_oauth_credentials_is_expired_property(
    fake_oauth_credentials: OAuthCredentials,
) -> None:
    """Test the `is_expired` property."""
    assert fake_oauth_credentials.is_expired is False

    with freeze_time(datetime.utcnow() + timedelta(seconds=3600)):
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
    assert not client.DEFAULT_PARAMS and isinstance(client.DEFAULT_PARAMS, dict)


def test_get_method_calls_request_correctly(
    oauth_client: OAuthClient[dict[str, Any]],
) -> None:
    """Test the `_get` method calls `request` correctly."""

    with patch.object(oauth_client, "_request") as mock_request:
        oauth_client._get(
            "test_endpoint",
        )
        oauth_client._get(
            "test_endpoint",
            params={"param_key": "param_value"},
            header_overrides={"header_key": "header_value"},
            timeout=10,
            json={"json_key": "json_value"},
        )

    assert mock_request.call_args_list == [
        call(
            method=get,
            url="test_endpoint",
            params=None,
            header_overrides=None,
            timeout=None,
            json=None,
            data=None,
        ),
        call(
            method=get,
            url="test_endpoint",
            params={"param_key": "param_value"},
            header_overrides={"header_key": "header_value"},
            timeout=10,
            json={"json_key": "json_value"},
            data=None,
        ),
    ]


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


def test_post_method_calls_request_correctly(
    oauth_client: OAuthClient[dict[str, Any]],
) -> None:
    """Test the `_post` method calls `request` correctly."""

    with patch.object(oauth_client, "_request") as mock_request:
        oauth_client._post(
            "test_endpoint",
        )
        oauth_client._post(
            "test_endpoint",
            params={"param_key": "param_value"},
            header_overrides={"header_key": "header_value"},
            timeout=10,
            json={"json_key": "json_value"},
        )

    assert mock_request.call_args_list == [
        call(
            method=post,
            url="test_endpoint",
            params=None,
            header_overrides=None,
            timeout=None,
            json=None,
            data=None,
        ),
        call(
            method=post,
            url="test_endpoint",
            params={"param_key": "param_value"},
            header_overrides={"header_key": "header_value"},
            timeout=10,
            json={"json_key": "json_value"},
            data=None,
        ),
    ]


def test_request_method_sends_correct_request(
    oauth_client: OAuthClient[dict[str, Any]],
    mock_requests: Mocker,
    caplog: LogCaptureFixture,
) -> None:
    """Test that the `_request`` method sends the correct request."""

    mock_requests.post(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={"key": "value"},
    )

    res = oauth_client._request(
        method=post,
        url="/test_endpoint",
        params={"test_param": "test_value"},
        json={"test_json_key": "test_json_value"},
        header_overrides={"test_header": "test_value"},
    )

    assert res.json() == {"key": "value"}
    assert res.status_code == HTTPStatus.OK
    assert res.reason == HTTPStatus.OK.phrase

    request = mock_requests.request_history.pop(0)

    assert len(mock_requests.request_history) == 0

    assert request.method == "POST"
    assert request.url == "https://api.example.com/test_endpoint?test_param=test_value"
    assert "Authorization" not in request.headers
    assert request.headers["test_header"] == "test_value"
    assert request.json() == {"test_json_key": "test_json_value"}
    assert request.qs == {"test_param": ["test_value"]}

    assert caplog.records[0].levelno == DEBUG
    assert (
        caplog.records[0].message
        == 'POST https://api.example.com/test_endpoint: {"test_param": "test_value"}'
    )


def test_request_raises_exception_for_non_200_response(
    oauth_client: OAuthClient[dict[str, Any]], mock_requests: Mocker
) -> None:
    """Test that the `_request`` method raises an exception for non-200 responses."""

    mock_requests.post(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.NOT_FOUND,
        reason=HTTPStatus.NOT_FOUND.phrase,
    )

    with raises(HTTPError) as exc_info:
        oauth_client._request(
            method=post,
            url="/test_endpoint",
        )

    assert exc_info.value.response.status_code == HTTPStatus.NOT_FOUND
    assert exc_info.value.response.reason == HTTPStatus.NOT_FOUND.phrase

    assert (
        str(exc_info.value) == "404 Client Error: Not Found for url: "
        "https://api.example.com/test_endpoint"
    )


def test_request_json_response(
    oauth_client: OAuthClient[dict[str, Any]], mock_requests: Mocker
) -> None:
    """Test that the request method returns a JSON response."""

    mock_requests.get(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={"key": "value"},
    )
    with patch.object(
        oauth_client,
        "_request_json_response",
        wraps=oauth_client._request_json_response,
    ) as mock_request:
        res = oauth_client._request_json_response(
            method=get,
            url="/test_endpoint",
            params={"test_param": "test_value"},
            json={"test_key": "test_value"},
            header_overrides={"test_header": "test_value"},
        )

    mock_request.assert_called_once_with(
        method=get,
        url="/test_endpoint",
        params={"test_param": "test_value"},
        json={"test_key": "test_value"},
        header_overrides={"test_header": "test_value"},
    )

    assert res == {"key": "value"}


def test_request_json_response_defaults_to_empty_dict_for_no_content(
    oauth_client: OAuthClient[dict[str, Any]], mock_requests: Mocker
) -> None:
    """Test that the request method returns an empty dict for no content."""

    mock_requests.get(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.NO_CONTENT,
        reason=HTTPStatus.NO_CONTENT.phrase,
    )

    res = oauth_client._request_json_response(
        method=get,
        url="/test_endpoint",
    )

    assert res == {}


def test_request_json_response_defaults_to_empty_dict_with_json_decode_error(
    oauth_client: OAuthClient[dict[str, Any]], mock_requests: Mocker
) -> None:
    """Test that the request method returns an empty dict for JSON decode errors."""

    mock_requests.get(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        text="",
    )

    res = oauth_client._request_json_response(
        method=get,
        url="/test_endpoint",
    )

    assert res == {}


def test_request_json_response_raises_exception_with_invalid_json(
    oauth_client: OAuthClient[dict[str, Any]], mock_requests: Mocker
) -> None:
    """Test that the request method returns an empty dict for JSON decode errors."""

    mock_requests.get(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        text="invalid_json",
    )

    with raises(ValueError) as exc_info:
        oauth_client._request_json_response(
            method=get,
            url="/test_endpoint",
        )

    assert str(exc_info.value) == "invalid_json"


def test_delete_creds_file(oauth_client: OAuthClient[dict[str, Any]]) -> None:
    """Test that the `delete_creds_file` method deletes the credentials file."""
    assert oauth_client.creds_cache_path.exists()
    oauth_client.delete_creds_file()
    assert not oauth_client.creds_cache_path.exists()
    oauth_client.delete_creds_file()
    assert not oauth_client.creds_cache_path.exists()


def test_get_json_response_calls_request_json_response(
    oauth_client: OAuthClient[dict[str, Any]],
) -> None:
    """Test the `get_json_response` method calls `_request_json_response` correctly."""

    with patch.object(
        oauth_client, "_request_json_response"
    ) as mock_request_json_response:
        oauth_client.get_json_response(
            url="/test_endpoint",
            params={"test_param": "test_value"},
            header_overrides={"test_header": "test_value"},
            timeout=10,
            json={"test_key": "test_value"},
        )

    mock_request_json_response.assert_called_once_with(
        method=get,
        url="/test_endpoint",
        params={"test_param": "test_value"},
        header_overrides={"test_header": "test_value"},
        timeout=10,
        json={"test_key": "test_value"},
        data=None,
    )


def test_post_json_response_calls_request_json_response(
    oauth_client: OAuthClient[dict[str, Any]],
) -> None:
    """Test the `post_json_response` method calls `_request_json_response` correctly."""

    with patch.object(
        oauth_client, "_request_json_response"
    ) as mock_request_json_response:
        oauth_client.post_json_response(
            url="/test_endpoint",
            params={"test_param": "test_value"},
            header_overrides={"test_header": "test_value"},
            timeout=10,
            json={"test_key": "test_value"},
        )

    mock_request_json_response.assert_called_once_with(
        method=post,
        url="/test_endpoint",
        params={"test_param": "test_value"},
        header_overrides={"test_header": "test_value"},
        timeout=10,
        json={"test_key": "test_value"},
        data=None,
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

    with raises(ValueError) as exc_info:
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


@patch.object(
    OAuthClient,
    "DEFAULT_CACHE_DIR",
    str(Path(__file__).parent / ".wg-utilities" / "oauth_credentials"),
)
def test_creds_cache_path_with_env_var(
    oauth_client: OAuthClient[dict[str, Any]],
) -> None:
    """Test `creds_cache_path` returns the expected value when the env var is set.

    I've had to patch the `DEFAULT_CACHE_DIR` attribute because I can't set the env
    var for _just_ this test.
    """
    oauth_client._creds_cache_path = None
    del oauth_client._credentials

    assert oauth_client.DEFAULT_CACHE_DIR == str(
        Path(__file__).parent / ".wg-utilities" / "oauth_credentials"
    )

    assert oauth_client.creds_cache_path == (
        Path(__file__).parent
        / ".wg-utilities"
        / "oauth_credentials"
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

    assert isinstance(oauth_tas := oauth_client.temp_auth_server, TempAuthServer)
    assert oauth_client.temp_auth_server.is_running is False

    assert hasattr(oauth_client, "_temp_auth_server")

    oauth_client.temp_auth_server.stop_server()

    with patch(
        "wg_utilities.clients.oauth_client.TempAuthServer"
    ) as mock_temp_auth_server:
        assert oauth_client.temp_auth_server == oauth_tas
        mock_temp_auth_server.assert_not_called()
