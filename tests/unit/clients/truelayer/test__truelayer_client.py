# pylint: disable=protected-access
"""Unit tests for `TrueLayerClient`."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from requests import HTTPError
from requests_mock import Mocker

from tests.conftest import assert_mock_requests_request_history
from wg_utilities.clients.oauth_client import OAuthCredentials
from wg_utilities.clients.truelayer import Account, Bank, Card, TrueLayerClient
from wg_utilities.functions.file_management import user_data_dir


@pytest.mark.parametrize(
    "default_cache_dir",
    [
        None,
        str(Path(__file__).parent / ".wg-utilities" / "oauth_credentials"),
    ],
)
def test_instantiation(
    fake_oauth_credentials: OAuthCredentials, default_cache_dir: str | None
) -> None:
    """Test that a `TrueLayerClient` can be instantiated."""

    with patch.object(TrueLayerClient, "DEFAULT_CACHE_DIR", default_cache_dir):
        truelayer_client = TrueLayerClient(
            client_id=fake_oauth_credentials.client_id,
            client_secret=fake_oauth_credentials.client_secret,
            bank=Bank.ALLIED_IRISH_BANK_CORPORATE,
        )

        assert isinstance(truelayer_client, TrueLayerClient)
        assert truelayer_client.client_id == fake_oauth_credentials.client_id
        assert truelayer_client.client_secret == fake_oauth_credentials.client_secret
        assert truelayer_client.bank == Bank.ALLIED_IRISH_BANK_CORPORATE
        assert truelayer_client.log_requests is False
        assert truelayer_client.scopes == [
            "info",
            "accounts",
            "balance",
            "cards",
            "transactions",
            "direct_debits",
            "standing_orders",
            "offline_access",
        ]

        # Ensure credential caches are separate for each bank
        assert (
            f"{Bank.ALLIED_IRISH_BANK_CORPORATE.name.lower()}.json"
            == truelayer_client.creds_cache_path.name
        )

        if default_cache_dir:
            assert default_cache_dir == truelayer_client.DEFAULT_CACHE_DIR
            assert truelayer_client.creds_cache_path == Path(
                default_cache_dir,
                "TrueLayerClient",
                "test_client_id",
                f"{Bank.ALLIED_IRISH_BANK_CORPORATE.name.lower()}.json",
            )
        else:
            assert truelayer_client.creds_cache_path == user_data_dir().joinpath(
                "oauth_credentials",
                "TrueLayerClient",
                "test_client_id",
                f"{Bank.ALLIED_IRISH_BANK_CORPORATE.name.lower()}.json",
            )


@pytest.mark.parametrize(
    "entity",
    [
        "account",
        "card",
    ],
)
def test_get_entity_by_id(
    truelayer_client: TrueLayerClient,
    entity: str,
    request: pytest.FixtureRequest,
    mock_requests: Mocker,
) -> None:
    """Test that `_get_entity_by_id` returns the correct entity."""

    expected_entity = request.getfixturevalue(entity)

    actual_entity = truelayer_client._get_entity_by_id(
        expected_entity.id, expected_entity.__class__
    )

    assert actual_entity == expected_entity
    assert entity == actual_entity.__class__.__name__.lower()

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "method": "GET",
                "url": TrueLayerClient.BASE_URL
                + f"/data/v1/{entity}s/{expected_entity.id}",
                "headers": {},
            },
        ],
    )


@pytest.mark.parametrize(
    (
        "response_json",
        "response_status",
        "expected_outcome",
    ),
    [
        (
            {
                "results": [
                    {
                        "key": "value",
                    },
                    {
                        "key": "value",
                    },
                    {
                        "key": "value",
                    },
                ],
                "status": "Succeeded",
            },
            HTTPStatus.OK,
            ValueError("Unexpected number of results when getting Account: 3"),
        ),
        ({"error": "account_not_found"}, HTTPStatus.NOT_FOUND, None),
        (
            {"error": "internal_server_error"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPError(
                "500 Server Error: Internal Server Error for url: "
                "https://api.truelayer.com/data/v1/accounts/gabbagool"
            ),
        ),
    ],
)
def test_get_entity_by_id_exception_handling(
    truelayer_client: TrueLayerClient,
    response_json: dict[str, Any],
    response_status: HTTPStatus,
    expected_outcome: Exception,
    mock_requests: Mocker,
) -> None:
    """Test `_get_entity_by_id` raises an exception when the entity is not found."""

    mock_requests.get(
        TrueLayerClient.BASE_URL + "/data/v1/accounts/gabbagool",
        json=response_json,
        status_code=response_status,
        reason=response_status.phrase,
    )

    if isinstance(expected_outcome, Exception):
        with pytest.raises(expected_outcome.__class__) as exc_info:
            truelayer_client._get_entity_by_id("gabbagool", Account)

        assert exc_info.value.args == expected_outcome.args
    else:
        assert (
            truelayer_client._get_entity_by_id("gabbagool", Account) == expected_outcome
        )


def test_get_account_by_id(truelayer_client: TrueLayerClient) -> None:
    """Test `get_account_by_id` calls `_get_entity_by_id` with the correct arguments."""

    with patch.object(truelayer_client, "_get_entity_by_id") as mock_get_entity_by_id:
        truelayer_client.get_account_by_id("gabbagool")

    mock_get_entity_by_id.assert_called_once_with("gabbagool", Account)


def test_get_card_by_id(truelayer_client: TrueLayerClient) -> None:
    """Test `get_card_by_id` calls `_get_entity_by_id` with the correct arguments."""

    with patch.object(truelayer_client, "_get_entity_by_id") as mock_get_entity_by_id:
        truelayer_client.get_card_by_id("gabbagool")

    mock_get_entity_by_id.assert_called_once_with("gabbagool", Card)


def test_list_accounts(
    truelayer_client: TrueLayerClient, mock_requests: Mocker
) -> None:
    """Test `list_accounts` returns a list of `Account` objects."""

    accounts = truelayer_client.list_accounts()

    assert isinstance(accounts, list)
    assert all(isinstance(account, Account) for account in accounts)
    assert all(account.truelayer_client == truelayer_client for account in accounts)

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "method": "GET",
                "url": TrueLayerClient.BASE_URL + "/data/v1/accounts",
                "headers": {},
            },
        ],
    )


def test_list_cards(truelayer_client: TrueLayerClient, mock_requests: Mocker) -> None:
    """Test `list_cards` returns a list of `Card` objects."""

    cards = truelayer_client.list_cards()

    assert isinstance(cards, list)
    assert all(isinstance(card, Card) for card in cards)
    assert all(card.truelayer_client == truelayer_client for card in cards)

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "method": "GET",
                "url": TrueLayerClient.BASE_URL + "/data/v1/cards",
                "headers": {},
            },
        ],
    )


@pytest.mark.parametrize(
    (
        "response_json",
        "response_status",
        "expected_outcome",
    ),
    [
        ({"error": "endpoint_not_supported"}, HTTPStatus.NOT_IMPLEMENTED, []),
        (
            {"error": "internal_server_error"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPError(
                "500 Server Error: Internal Server Error for url: "
                "https://api.truelayer.com/data/v1/accounts"
            ),
        ),
    ],
)
def test_list_entity_exception_handling(
    truelayer_client: TrueLayerClient,
    response_json: dict[str, Any],
    response_status: HTTPStatus,
    expected_outcome: Exception,
    mock_requests: Mocker,
) -> None:
    """Test that `_list_entities` handles exceptions correctly."""

    mock_requests.get(
        f"{TrueLayerClient.BASE_URL}/data/v1/accounts",
        json=response_json,
        status_code=response_status,
        reason=response_status.phrase,
    )

    if isinstance(expected_outcome, Exception):
        with pytest.raises(expected_outcome.__class__) as exc_info:
            truelayer_client.list_accounts()

        assert exc_info.value.args == expected_outcome.args
    else:
        assert truelayer_client.list_accounts() == expected_outcome


@pytest.mark.parametrize("bank", Bank)
def test_creds_rel_file_path(bank: Bank, truelayer_client: TrueLayerClient) -> None:
    """Test `creds_rel_file_path` returns the correct path."""

    truelayer_client.bank = bank

    assert truelayer_client._creds_rel_file_path == Path(
        "TrueLayerClient", "test_client_id", bank.name.lower()
    ).with_suffix(".json")
