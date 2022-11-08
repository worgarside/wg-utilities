# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.monzo.MonzoClient`."""
from __future__ import annotations

from http import HTTPStatus
from json import load
from unittest.mock import patch
from urllib.parse import urlencode

from freezegun import freeze_time
from pytest import mark, raises
from requests.exceptions import HTTPError
from requests_mock import Mocker

from conftest import monzo_account_json, monzo_pot_json
from wg_utilities.clients import MonzoClient
from wg_utilities.clients._generic import OAuthClient
from wg_utilities.clients.monzo import Account, Pot


def test_instantiation() -> None:
    """Test instantiating a `MonzoClient`."""

    client = MonzoClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
    )

    assert isinstance(client, MonzoClient)
    assert isinstance(client, OAuthClient)

    assert client.client_id == "test_client_id"
    assert client.client_secret == "test_client_secret"
    assert client.base_url == "https://api.monzo.com"
    assert client.access_token_endpoint == "https://api.monzo.com/oauth2/token"
    assert client.redirect_uri == "http://0.0.0.0:5001/get_auth_code"
    assert client.access_token_expiry_threshold == 60
    assert client.log_requests is False
    assert client.creds_cache_path == MonzoClient.CREDS_FILE_PATH


def test_deposit_into_pot_makes_correct_request(
    monzo_client: MonzoClient, monzo_pot: Pot, mock_requests: Mocker
) -> None:
    """Test that the `deposit_into_pot` method makes the correct request."""

    with freeze_time("2020-01-01 00:00:00"):
        monzo_client.deposit_into_pot(monzo_pot, 100)

    assert mock_requests.request_history[-1].method == "PUT"
    assert (
        mock_requests.request_history[-1].url
        == f"https://api.monzo.com/pots/{monzo_pot.id}/deposit"
    )
    assert mock_requests.request_history[-1].text == urlencode(
        {
            "source_account_id": "test_account_id",
            "amount": 100,
            "dedupe_id": "test_pot_id|100|1577836800",
        }
    )


def test_deposit_into_pot_raises_error_on_failure(
    monzo_client: MonzoClient, monzo_pot: Pot, mock_requests: Mocker
) -> None:
    """Test that the `deposit_into_pot` method raises an error on failure."""

    mock_requests.put(
        f"https://api.monzo.com/pots/{monzo_pot.id}/deposit",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        reason=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
    )

    with raises(HTTPError) as exc_info:
        monzo_client.deposit_into_pot(monzo_pot, 100)

    assert exc_info.value.response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc_info.value.response.reason == HTTPStatus.INTERNAL_SERVER_ERROR.phrase
    assert str(exc_info.value) == (
        "500 Server Error: Internal Server Error for url: "
        "https://api.monzo.com/pots/test_pot_id/deposit"
    )


def test_list_accounts_method(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
) -> None:
    """Test that the `list_accounts` returns the single expected `Account` instance."""

    for account_type in [
        "uk_prepaid",
        "uk_retail",
        "uk_monzo_flex_backing_loan",
        "uk_monzo_flex",
        "uk_retail_joint",
    ]:
        expected_accounts = [
            Account(acc_json, monzo_client=monzo_client)
            for acc_json in monzo_account_json(account_type=account_type)["accounts"]
        ]

        assert (
            monzo_client.list_accounts(account_type=account_type, include_closed=True)
            == expected_accounts
        )

        assert monzo_client.list_accounts(
            account_type=account_type, include_closed=False
        ) == [account for account in expected_accounts if not account.closed]

        assert mock_requests.request_history[-1].method == "GET"
        assert mock_requests.request_history[
            -1
        ].url == "https://api.monzo.com/accounts?" + urlencode(
            {"account_type": account_type}
        )


def test_list_pots_method(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
) -> None:
    """Test that the `list_pots` returns the single expected `Pot` instance."""

    all_pots = [Pot(pot_json) for pot_json in monzo_pot_json()["pots"]]

    assert monzo_client.list_pots(include_deleted=True) == all_pots

    assert monzo_client.list_pots(include_deleted=False) == [
        pot for pot in all_pots if not pot.deleted
    ]

    assert mock_requests.request_history[-1].method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "test_account_id"}
    )


def test_get_pot_by_id_method(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
) -> None:
    """Test that the `get_pot_by_id` returns the single expected `Pot` instance."""

    pot = Pot(monzo_pot_json()["pots"][0])

    assert monzo_client.get_pot_by_id(pot.id) == pot

    assert mock_requests.request_history[-1].method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "test_account_id"}
    )

    assert monzo_client.get_pot_by_id("invalid_id") is None


def test_get_pot_by_name_exact_match_true(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
) -> None:
    """Test that the `get_pot_by_name` returns the single expected `Pot` instance."""

    pot = Pot(monzo_pot_json()["pots"][3])

    assert monzo_client.get_pot_by_name(pot.name, exact_match=True) == pot

    assert mock_requests.request_history[-1].method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "test_account_id"}
    )

    assert monzo_client.get_pot_by_name("!!!Ibiza-Mad-One!!!", exact_match=True) is None


def test_get_pot_by_name_exact_match_false(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
) -> None:
    """Test that the `get_pot_by_name` returns the single expected `Pot` instance."""

    pot = Pot(monzo_pot_json()["pots"][3])

    assert pot.name == "Ibiza Mad One"

    assert monzo_client.get_pot_by_name(pot.name, exact_match=False) == pot
    assert monzo_client.get_pot_by_name("!!!Ibiza-Mad-One!!!", exact_match=False) == pot

    assert mock_requests.request_history[-1].method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "test_account_id"}
    )


def test_access_token_has_expired_property_no_access_token(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
) -> None:
    """Test that the `access_token_has_expired` property returns the expected value."""

    def _mock_load_local_credentials_side_effect() -> None:
        with open(monzo_client.creds_cache_path, encoding="UTF-8") as fin:
            monzo_client._credentials = load(fin)[monzo_client.client_id]
        del monzo_client._credentials["access_token"]  # type: ignore[misc]

    with patch.object(
        monzo_client,
        "_load_local_credentials",
        side_effect=_mock_load_local_credentials_side_effect,
    ):
        assert monzo_client.access_token_has_expired

    # Not access token was found, so we don't even need to ping the API
    assert not mock_requests.request_history


@mark.parametrize(  # type: ignore[misc]
    ["access_token", "expired"],
    (
        ("active_access_token", False),
        ("expired_access_token", True),
    ),
)
def test_access_token_has_expired_property_expired_with_access_token(
    monzo_client: MonzoClient, mock_requests: Mocker, access_token: str, expired: bool
) -> None:
    """Test that the `access_token_has_expired` property returns the expected value."""

    def _mock_load_local_credentials_side_effect() -> None:
        with open(monzo_client.creds_cache_path, encoding="UTF-8") as fin:
            monzo_client._credentials = load(fin)[monzo_client.client_id]
        monzo_client._credentials["access_token"] = access_token

    with patch.object(
        monzo_client,
        "_load_local_credentials",
        side_effect=_mock_load_local_credentials_side_effect,
    ):
        assert monzo_client.access_token_has_expired is expired

    assert mock_requests.request_history[-1].method == "GET"
    assert mock_requests.request_history[-1].url == "https://api.monzo.com/ping/whoami"


def test_credentials_property_loads_local_credentials(
    monzo_client: MonzoClient,
) -> None:
    """Test that the `credentials` property loads the local credentials."""

    def _mock_load_local_credentials_side_effect() -> None:
        monzo_client._credentials = {
            "access_token": "active_access_token",
            "client_id": "test_client_id",
            "expires_in": 10,
            "refresh_token": "test_refresh_token_new",
            "scope": "new_scope,_everything_the_light_touches",
            "token_type": "Bearer",
            "user_id": "test_user_id",
        }

    with patch.object(
        monzo_client,
        "_load_local_credentials",
        side_effect=_mock_load_local_credentials_side_effect,
    ) as mock_load_local_credentials:
        assert monzo_client.credentials == {
            "access_token": "active_access_token",
            "client_id": "test_client_id",
            "expires_in": 10,
            "refresh_token": "test_refresh_token_new",
            "scope": "new_scope,_everything_the_light_touches",
            "token_type": "Bearer",
            "user_id": "test_user_id",
        }
        mock_load_local_credentials.assert_called_once()


def test_credentials_property_runs_first_time_login(monzo_client: MonzoClient) -> None:
    """Test that the `credentials` property runs the first time login flow."""

    def _mock_load_local_credentials_side_effect() -> None:
        monzo_client._credentials = {}  # type: ignore[typeddict-item]

    with patch.object(
        monzo_client,
        "_load_local_credentials",
        side_effect=_mock_load_local_credentials_side_effect,
    ), patch("wg_utilities.clients.monzo.open_browser") as mock_open_browser, patch(
        "wg_utilities.clients.monzo.choice", side_effect=lambda _: "x"  # noqa: N803
    ), patch.object(
        monzo_client, "exchange_auth_code"
    ) as mock_exchange_auth_code, patch(
        "wg_utilities.clients._generic.TempAuthServer"
    ) as mock_temp_auth_server:

        mock_temp_auth_server.return_value.wait_for_request.return_value = {
            "state": "x" * 32,
            "code": "test_auth_code",
        }

        assert monzo_client.credentials == {
            "access_token": "test_access_token_new",
            "client_id": "test_client_id",
            "expires_in": 3600,
            "refresh_token": "test_refresh_token_new",
            "scope": "test_scope,test_scope_two",
            "token_type": "Bearer",
            "user_id": "test_user_id",
        }

        mock_open_browser.assert_called_once_with(
            "https://auth.monzo.com/?"
            + "&".join(
                [
                    f"{key}={value}"
                    for key, value in [
                        ("client_id", monzo_client.client_id),
                        ("redirect_uri", monzo_client.redirect_uri),
                        (
                            "response_type",
                            "code",
                        ),
                        ("state", "x" * 32),
                    ]
                ]
            )
        )

        mock_temp_auth_server.assert_called_once_with("wg_utilities.clients._generic")

        mock_temp_auth_server.return_value.wait_for_request.assert_called_once_with(
            "/get_auth_code", kill_on_request=True
        )

        mock_exchange_auth_code.assert_called_once_with("test_auth_code")


def test_credentials_property_raises_exception_with_invalid_state(
    monzo_client: MonzoClient,
) -> None:
    """Test `credentials` raises a `ValueError` when the state is invalid."""

    def _mock_load_local_credentials_side_effect() -> None:
        monzo_client._credentials = {}  # type: ignore[typeddict-item]

    with patch.object(
        monzo_client,
        "_load_local_credentials",
        side_effect=_mock_load_local_credentials_side_effect,
    ), patch("wg_utilities.clients.monzo.open_browser"), patch(
        "wg_utilities.clients.monzo.choice", side_effect=lambda _: "x"  # noqa: N803
    ), patch(
        "wg_utilities.clients._generic.TempAuthServer"
    ) as mock_temp_auth_server, raises(
        ValueError
    ) as exc_info:

        mock_temp_auth_server.return_value.wait_for_request.return_value = {
            "state": "y" * 32,
            "code": "test_auth_code",
        }

        _ = monzo_client.credentials

    assert str(exc_info.value) == (
        "State token received in request doesn't match expected value: "
        f"{'y'*32} != {'x'*32}"
    )


def test_credentials_setter_calls_parent_class_method(
    monzo_client: MonzoClient,
) -> None:
    """Test that the `credentials` setter sets the credentials via the parent class."""

    with patch(
        "wg_utilities.clients._generic.OAuthClient._set_credentials"
    ) as mock_set_credentials:
        monzo_client.credentials = {"foo": "bar"}  # type: ignore[typeddict-item]
        mock_set_credentials.assert_called_once_with({"foo": "bar"})


def test_current_account_property(
    monzo_client: MonzoClient, monzo_account: Account
) -> None:
    """Test that the `current_account` property returns the expected value."""

    assert not hasattr(monzo_client, "_current_account")

    assert monzo_client.current_account == monzo_account
    assert monzo_client._current_account == monzo_account
