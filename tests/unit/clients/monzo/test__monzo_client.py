"""Unit Tests for `wg_utilities.clients.monzo.MonzoClient`."""

from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import pytest
from freezegun import freeze_time
from requests.exceptions import HTTPError

from tests.conftest import assert_mock_requests_request_history, read_json_file
from wg_utilities.clients import MonzoClient
from wg_utilities.clients.monzo import (
    Account,
    AccountJson,
    Pot,
    Transaction,
    TransactionCategory,
    TransactionJson,
)
from wg_utilities.clients.oauth_client import OAuthClient, OAuthCredentials
from wg_utilities.functions import user_data_dir

if TYPE_CHECKING:
    from requests_mock import Mocker


def test_instantiation(fake_oauth_credentials: OAuthCredentials) -> None:
    """Test instantiating a `MonzoClient`."""

    client = MonzoClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
    )

    assert isinstance(client, MonzoClient)
    assert isinstance(client, OAuthClient)

    assert client.client_id == fake_oauth_credentials.client_id
    assert client.client_secret == fake_oauth_credentials.client_secret
    assert client.base_url == "https://api.monzo.com"
    assert client.access_token_endpoint == "https://api.monzo.com/oauth2/token"
    assert client.log_requests is False
    assert client.creds_cache_path == user_data_dir(
        file_name=f"oauth_credentials/MonzoClient/{client.client_id}.json",
    )


def test_deposit_into_pot_makes_correct_request(
    monzo_client: MonzoClient,
    monzo_pot: Pot,
    mock_requests: Mocker,
) -> None:
    """Test that the `deposit_into_pot` method makes the correct request."""

    with freeze_time("2020-01-01 00:00:00"):
        monzo_client.deposit_into_pot(monzo_pot, 100)

    assert mock_requests.last_request

    assert mock_requests.last_request.method == "PUT"
    assert (
        mock_requests.last_request.url
        == f"https://api.monzo.com/pots/{monzo_pot.id}/deposit"
    )
    assert mock_requests.last_request.text == urlencode(
        {
            "source_account_id": "acc_0000000000000000000000",
            "amount": 100,
            "dedupe_id": "pot_0000000000000000000014|100|1577836800",
        },
    )


def test_deposit_into_pot_raises_error_on_failure(
    monzo_client: MonzoClient,
    monzo_pot: Pot,
    mock_requests: Mocker,
) -> None:
    """Test that the `deposit_into_pot` method raises an error on failure."""

    mock_requests.put(
        f"https://api.monzo.com/pots/{monzo_pot.id}/deposit",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        reason=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
    )

    with pytest.raises(HTTPError) as exc_info:
        monzo_client.deposit_into_pot(monzo_pot, 100)

    assert exc_info.value.response is not None
    assert exc_info.value.response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc_info.value.response.reason == HTTPStatus.INTERNAL_SERVER_ERROR.phrase
    assert str(exc_info.value) == (
        "500 Server Error: Internal Server Error for url: "
        "https://api.monzo.com/pots/pot_0000000000000000000014/deposit"
    )


@pytest.mark.parametrize("include_closed", [True, False])
@pytest.mark.parametrize(
    "account_type",
    [
        "uk_retail",
        "uk_retail_joint",
    ],
)
def test_list_accounts_method(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
    include_closed: bool,
    account_type: str,
    live_jwt_token: str,
) -> None:
    """Test that the `list_accounts` returns the single expected `Account` instance."""

    expected_accounts: list[AccountJson] = [
        acc
        for acc in read_json_file("accounts.json", host_name="monzo")["accounts"]
        if acc["type"] == account_type and (include_closed or not acc["closed"])
    ]

    for acc in expected_accounts:
        acc["created"] = datetime.fromisoformat(  # type: ignore[typeddict-item]
            acc["created"].rstrip("Z"),
        ).replace(tzinfo=timezone.utc)

    assert [
        acc.model_dump(exclude_none=True)
        for acc in monzo_client.list_accounts(
            include_closed=include_closed,
            account_type=account_type,
        )
    ] == expected_accounts

    expected_request: list[dict[str, str | dict[str, str]]] = [
        {
            "url": f"https://api.monzo.com/accounts?account_type={account_type}",
            "method": "GET",
            "headers": {"Authorization": f"Bearer {live_jwt_token}"},
        },
    ]

    assert_mock_requests_request_history(
        mock_requests.request_history,
        expected_request,
    )
    assert all(
        acc.type == account_type
        for acc in monzo_client.list_accounts(
            include_closed=include_closed,
            account_type=account_type,
        )
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        expected_request * 2,
    )

    if not include_closed:
        assert all(
            acc.closed is False
            for acc in monzo_client.list_accounts(
                include_closed=include_closed,
                account_type=account_type,
            )
        )


def test_list_pots_method(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
) -> None:
    """Test that the `list_pots` returns the single expected `Pot` instance."""

    all_pots = [
        Pot(**pot_json)
        for pot_json in read_json_file(
            "current_account_id=acc_0000000000000000000000.json",
            host_name="monzo/pots",
        )["pots"]
    ]

    assert monzo_client.list_pots(include_deleted=True) == all_pots

    assert monzo_client.list_pots(include_deleted=False) == [
        pot for pot in all_pots if not pot.deleted
    ]

    assert mock_requests.last_request
    assert mock_requests.last_request.method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "acc_0000000000000000000000"},
    )


def test_get_pot_by_id_method(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
    monzo_pot: Pot,
) -> None:
    """Test that the `get_pot_by_id` returns the single expected `Pot` instance."""
    assert monzo_client.get_pot_by_id(monzo_pot.id) == monzo_pot

    assert mock_requests.last_request
    assert mock_requests.last_request.method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "acc_0000000000000000000000"},
    )

    assert monzo_client.get_pot_by_id("invalid_id") is None


def test_get_pot_by_name_exact_match_true(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
    monzo_pot: Pot,
) -> None:
    """Test that the `get_pot_by_name` returns the single expected `Pot` instance."""

    assert monzo_client.get_pot_by_name(monzo_pot.name, exact_match=True) == monzo_pot

    assert mock_requests.last_request
    assert mock_requests.last_request.method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "acc_0000000000000000000000"},
    )

    assert monzo_client.get_pot_by_name("!!!Ibiza-Mad-One!!!", exact_match=True) is None


def test_get_pot_by_name_exact_match_false(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
    monzo_pot: Pot,
) -> None:
    """Test that the `get_pot_by_name` returns the single expected `Pot` instance."""

    assert monzo_pot.name == "Ibiza Mad One"

    assert monzo_client.get_pot_by_name(monzo_pot.name, exact_match=False) == monzo_pot
    assert (
        monzo_client.get_pot_by_name("!!!Ibiza-Mad-One!!!", exact_match=False)
        == monzo_pot
    )

    assert mock_requests.last_request
    assert mock_requests.last_request.method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "acc_0000000000000000000000"},
    )


def test_current_account_property(
    monzo_client: MonzoClient,
    monzo_account: Account,
) -> None:
    """Test that the `current_account` property returns the expected value."""

    assert not hasattr(monzo_client, "_current_account")

    assert monzo_client.current_account == monzo_account
    assert monzo_client._current_account == monzo_account


def test_transaction_json_annotations_vs_transaction_fields() -> None:
    """Test that the `TransactionJson` annotations match the `Transaction` fields."""

    for ak, av in TransactionJson.__annotations__.items():
        assert ak in Transaction.model_fields

        if str(annotation := Transaction.model_fields[ak].annotation).startswith(
            "<class",
        ):
            tx_field_type = annotation.__name__  # type: ignore[union-attr]
        else:
            tx_field_type = str(annotation)

        if tx_field_type == "Literal":  # pragma: no cover
            tx_field_type = (
                f"Literal{list(Transaction.model_fields[ak].annotation.__args__)!r}"  # type: ignore[union-attr]
            )

        tx_field_type = tx_field_type.replace("typing.", "").replace("NoneType", "None")

        forward_arg = av.__forward_arg__.replace(
            "TransactionCategory",
            f"Literal{sorted(TransactionCategory.__args__)!r}",  # type: ignore[attr-defined]
        )

        assert forward_arg == tx_field_type
