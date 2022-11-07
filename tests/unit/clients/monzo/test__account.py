# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.monzo.Account`."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time
from pytest import LogCaptureFixture
from requests_mock import Mocker

from wg_utilities.clients.monzo import Account, MonzoClient


def test_instantiation(monzo_client: MonzoClient) -> None:
    """Test that the class can be instantiated."""
    account = Account(
        json={
            "account_number": "12345678",
            "balance": 10000,
            "balance_including_flexible_savings": 50000,
            "created": "2020-01-01T00:00:00.000Z",
            "description": "user_00001AbcdEfghIjklMnopQ",
            "id": "acc_00001AbcdEfghIjklMnopQ",
            "sort_code": "123456",
            "spend_today": 0.0,
            "total_balance": 50000,
        },
        monzo_client=monzo_client,
    )

    assert isinstance(account, Account)
    assert account.json == {
        "account_number": "12345678",
        "balance": 10000,
        "balance_including_flexible_savings": "",
        "created": "2020-01-01T00:00:00.000Z",
        "description": "user_00001AbcdEfghIjklMnopQ",
        "id": "acc_00001AbcdEfghIjklMnopQ",
        "sort_code": "123456",
        "spend_today": 0.0,
        "total_balance": 10000,
    }
    assert account._monzo_client == monzo_client
    assert account.last_balance_update == datetime(1970, 1, 1)
    assert account.balance_update_threshold == 15


def test_get_balance_property_method(monzo_account: Account) -> None:
    """Test that `_get_balance_property` returns the correct value."""

    monzo_account.last_balance_update = datetime.now()

    assert not hasattr(monzo_account, "_balance_variables")
    monzo_account._balance_variables = {"balance": 123}  # type: ignore[typeddict-item]
    assert hasattr(monzo_account, "_balance_variables")
    assert monzo_account._get_balance_property("balance") == 123
    assert monzo_account._get_balance_property("currency") is None

    with patch.object(
        monzo_account, "update_balance_variables"
    ) as mock_update_balance_variables, freeze_time(
        datetime.utcnow() + timedelta(minutes=20)
    ):
        assert monzo_account._get_balance_property("balance") == 123
        mock_update_balance_variables.assert_called_once()


def test_update_balance_variables(
    monzo_account: Account, mock_requests: Mocker
) -> None:
    """Test that the balance variables are updated correctly."""

    monzo_account.update_balance_variables()

    assert monzo_account._balance_variables == {
        "balance": 10000,
        "balance_including_flexible_savings": 50000,
        "currency": "GBP",
        "local_currency": "",
        "local_exchange_rate": "",
        "local_spend": [{"spend_today": -115, "currency": "GBP"}],
        "spend_today": -115,
        "total_balance": 10000,
    }
    assert (
        mock_requests.request_history[1].url
        == f"{monzo_account._monzo_client.base_url}/balance?"
        f"account_id={monzo_account.id}"
    )
    assert mock_requests.request_history[1].method == "GET"


def test_account_number_property(monzo_account: Account) -> None:
    """Test that the `account_number` property returns the correct value."""

    assert monzo_account.account_number == "12345678"

    monzo_account.json["account_number"] = "87654321"
    assert monzo_account.account_number == "87654321"


def test_balance_property(monzo_account: Account, caplog: LogCaptureFixture) -> None:
    """Test that the `balance` property returns the correct value."""

    assert monzo_account.balance == 10000
    assert (
        "Balance variable update threshold crossed, getting new values" in caplog.text
    )


def test_balance_including_flexible_savings_property(
    monzo_account: Account, caplog: LogCaptureFixture
) -> None:
    """Test the `balance_including_flexible_savings` property."""

    assert monzo_account.balance_including_flexible_savings == 50000
    assert (
        "Balance variable update threshold crossed, getting new values" in caplog.text
    )


def test_created_datetime_property(monzo_account: Account) -> None:
    """Test that the `created_datetime` property returns the correct value."""

    assert monzo_account.created_datetime == datetime(2020, 1, 1)

    monzo_account.json["created"] = "2021-02-02T00:00:00Z"
    assert monzo_account.created_datetime == datetime(2021, 2, 2)

    del monzo_account.json["created"]  # type: ignore[misc]
    assert monzo_account.created_datetime is None


def test_description_property(monzo_account: Account) -> None:
    """Test that the `description` property returns the correct value."""

    assert monzo_account.description == "test_user_id"


def test_id_property(monzo_account: Account) -> None:
    """Test that the `id` property returns the correct value."""

    assert monzo_account.id == "test_account_id"


def test_sort_code_property(monzo_account: Account) -> None:
    """Test that the `sort_code` property returns the correct value."""

    assert monzo_account.sort_code == "123456"

    monzo_account.json["sort_code"] = "654321"
    assert monzo_account.sort_code == "654321"


def test_spend_today_property(
    monzo_account: Account, caplog: LogCaptureFixture
) -> None:
    """Test that the `spend_today` property returns the correct value."""

    assert monzo_account.spend_today == -115
    assert (
        "Balance variable update threshold crossed, getting new values" in caplog.text
    )


def test_total_balance_property(
    monzo_account: Account, caplog: LogCaptureFixture
) -> None:
    """Test that the `total_balance` property returns the correct value."""

    assert monzo_account.total_balance == 10000
    assert (
        "Balance variable update threshold crossed, getting new values" in caplog.text
    )
