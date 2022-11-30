# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.monzo.MonzoClient`."""
from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from urllib.parse import urlencode

from freezegun import freeze_time
from pytest import mark, raises
from requests.exceptions import HTTPError
from requests_mock import Mocker

from conftest import assert_mock_requests_request_history, read_json_file
from wg_utilities.clients import MonzoClient
from wg_utilities.clients.monzo import Account, AccountJson, Pot, PotJson, Transaction
from wg_utilities.clients.monzo import TransactionCategory as TxCategory
from wg_utilities.clients.monzo import TransactionJson
from wg_utilities.clients.oauth_client import OAuthClient
from wg_utilities.functions import user_data_dir


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
    assert client.log_requests is False
    assert client.creds_cache_path == user_data_dir(
        file_name=f"oauth_credentials/MonzoClient/{client.client_id}.json"
    )


def test_deposit_into_pot_makes_correct_request(
    monzo_client: MonzoClient, monzo_pot: Pot, mock_requests: Mocker
) -> None:
    """Test that the `deposit_into_pot` method makes the correct request."""

    with freeze_time("2020-01-01 00:00:00"):
        monzo_client.deposit_into_pot(monzo_pot, 100)

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
        "https://api.monzo.com/pots/pot_0000000000000000000014/deposit"
    )


@mark.parametrize("include_closed", (True, False))  # type: ignore[misc]
@mark.parametrize(  # type: ignore[misc]
    "account_type",
    (
        "uk_retail",
        "uk_retail_joint",
    ),
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
            acc["created"].rstrip("Z")
        ).replace(tzinfo=timezone.utc)

    assert [
        acc.dict(exclude_none=True)
        for acc in monzo_client.list_accounts(
            include_closed=include_closed, account_type=account_type
        )
    ] == expected_accounts

    expected_request: list[dict[str, str | dict[str, str]]] = [
        {
            "url": f"https://api.monzo.com/accounts?account_type={account_type}",
            "method": "GET",
            "headers": {"Authorization": f"Bearer {live_jwt_token}"},
        }
    ]

    assert_mock_requests_request_history(
        mock_requests.request_history,
        expected_request,
    )
    assert all(
        acc.type == account_type
        for acc in monzo_client.list_accounts(
            include_closed=include_closed, account_type=account_type
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
                include_closed=include_closed, account_type=account_type
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
            "current_account_id=acc_0000000000000000000000.json", host_name="monzo/pots"
        )["pots"]
    ]

    assert monzo_client.list_pots(include_deleted=True) == all_pots

    assert monzo_client.list_pots(include_deleted=False) == [
        pot for pot in all_pots if not pot.deleted
    ]

    assert mock_requests.last_request.method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "acc_0000000000000000000000"}
    )


def test_get_pot_by_id_method(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
    monzo_pot: Pot,
) -> None:
    """Test that the `get_pot_by_id` returns the single expected `Pot` instance."""
    assert monzo_client.get_pot_by_id(monzo_pot.id) == monzo_pot

    assert mock_requests.last_request.method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "acc_0000000000000000000000"}
    )

    assert monzo_client.get_pot_by_id("invalid_id") is None


def test_get_pot_by_name_exact_match_true(
    monzo_client: MonzoClient,
    mock_requests: Mocker,
    monzo_pot: Pot,
) -> None:
    """Test that the `get_pot_by_name` returns the single expected `Pot` instance."""

    assert monzo_client.get_pot_by_name(monzo_pot.name, exact_match=True) == monzo_pot

    assert mock_requests.last_request.method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "acc_0000000000000000000000"}
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

    assert mock_requests.last_request.method == "GET"
    assert mock_requests.request_history[
        -1
    ].url == "https://api.monzo.com/pots?" + urlencode(
        {"current_account_id": "acc_0000000000000000000000"}
    )


def test_current_account_property(
    monzo_client: MonzoClient, monzo_account: Account
) -> None:
    """Test that the `current_account` property returns the expected value."""

    assert not hasattr(monzo_client, "_current_account")

    assert monzo_client.current_account == monzo_account
    assert monzo_client._current_account == monzo_account


def test_pot_json_annotations_vs_pot_fields() -> None:
    """Test that the `PotJson` annotations match the `Pot` fields."""

    for ak, av in PotJson.__annotations__.items():
        assert ak in Pot.__fields__

        pot_field_type = Pot.__fields__[ak].type_.__name__
        if pot_field_type == "Literal":
            pot_field_type = f"Literal{list(Pot.__fields__[ak].type_.__args__)!r}"

        if Pot.__fields__[ak].required is False:
            assert (
                " | ".join(
                    typ for typ in av.__forward_arg__.split(" | ") if typ != "None"
                )
                == pot_field_type
            )
        else:
            assert av.__forward_arg__ == pot_field_type


def test_transaction_json_annotations_vs_transaction_fields() -> None:
    """Test that the `TransactionJson` annotations match the `Transaction` fields."""

    for ak, av in TransactionJson.__annotations__.items():
        assert ak in Transaction.__fields__

        if str(annotation := Transaction.__fields__[ak].annotation).startswith(
            "<class"
        ):
            tx_field_type = annotation.__name__
        else:
            tx_field_type = str(annotation)

        if tx_field_type == "Literal":
            tx_field_type = (
                f"Literal{list(Transaction.__fields__[ak].type_.__args__)!r}"
            )

        tx_field_type = tx_field_type.replace("typing.", "").replace("NoneType", "None")

        forward_arg = av.__forward_arg__.replace(
            "TransactionCategory",
            f"Literal{sorted(TxCategory.__args__)!r}",  # type: ignore[attr-defined]
        )

        assert forward_arg == tx_field_type
