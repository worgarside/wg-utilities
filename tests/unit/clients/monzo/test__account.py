"""Unit Tests for `wg_utilities.clients.monzo.Account`."""

from __future__ import annotations

from datetime import datetime, timedelta
from http import HTTPStatus
from urllib.parse import urlencode

from freezegun import freeze_time
from pytest import LogCaptureFixture
from pytz import utc
from requests_mock import Mocker

from tests.conftest import assert_mock_requests_request_history, read_json_file
from wg_utilities.clients.monzo import Account, MonzoClient


def test_instantiation(monzo_client: MonzoClient) -> None:
    """Test that the class can be instantiated."""
    account = Account(
        account_number="12345678",
        balance=10000,
        balance_including_flexible_savings=50000,
        closed=False,
        country_code="GB",
        created="2020-01-01T00:00:00.000Z",  # type: ignore[arg-type]
        currency="GBP",
        description="user_00001AbcdEfghIjklMnopQ",
        id="acc_00001AbcdEfghIjklMnopQ",
        monzo_client=monzo_client,
        owners=[],
        sort_code="123456",
        spend_today=-115,
        total_balance=50000,
        type="uk_retail",
    )

    assert isinstance(account, Account)
    assert account.dict() == {
        "account_number": "12345678",
        "closed": False,
        "country_code": "GB",
        "created": datetime(2020, 1, 1, tzinfo=utc),
        "currency": "GBP",
        "description": "user_00001AbcdEfghIjklMnopQ",
        "id": "acc_00001AbcdEfghIjklMnopQ",
        "initial_balance": 10000,
        "initial_balance_including_flexible_savings": 50000,
        "initial_spend_today": -115,
        "initial_total_balance": 50000,
        "owners": [],
        "payment_details": None,
        "sort_code": "123456",
        "type": "uk_retail",
    }
    assert account.monzo_client == monzo_client


def test_list_transactions(
    monzo_account: Account, mock_requests: Mocker, live_jwt_token: str
) -> None:
    """Test that the `list_transactions` method returns a list of transactions."""

    # Freeze time to when I made the sample data, just to ensure the URL is correct
    with freeze_time("2022-11-21T19:42:49.870206Z") as frozen_datetime:
        transactions = monzo_account.list_transactions()

    assert len(transactions) == 100
    assert all(tx.account_id == "acc_0000000000000000000000" for tx in transactions)
    assert_mock_requests_request_history(
        mock_requests.request_history,
        expected=[
            {
                "url": f"{monzo_account.monzo_client.base_url}/transactions?"
                + urlencode(
                    {
                        "account_id": monzo_account.id,
                        "since": (
                            frozen_datetime.time_to_freeze - timedelta(days=89)
                        ).isoformat()
                        + "Z",
                        "before": frozen_datetime.time_to_freeze.isoformat() + "Z",
                        "limit": 100,
                    }
                ),
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            }
        ],
    )


def test_list_transactions_with_limit(
    monzo_account: Account, mock_requests: Mocker
) -> None:
    """Test `list_transactions` with a limit parameter."""

    mock_requests.get(
        f"{monzo_account.monzo_client.base_url}/transactions",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={"transactions": []},
    )

    with freeze_time() as frozen_datetime:
        monzo_account.list_transactions(limit=20)

    assert (
        mock_requests.last_request.url
        == f"{monzo_account.monzo_client.base_url}/transactions?"
        + urlencode(
            {
                "account_id": monzo_account.id,
                "since": (
                    frozen_datetime.time_to_freeze - timedelta(days=89)
                ).isoformat()
                + "Z",
                "before": frozen_datetime.time_to_freeze.isoformat() + "Z",
                "limit": 20,
            }
        )
    )


def test_list_transactions_with_time_parameters(
    monzo_account: Account, mock_requests: Mocker
) -> None:
    """Test `list_transactions` with to and from parameters.."""

    mock_requests.get(
        f"{monzo_account.monzo_client.base_url}/transactions",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={"transactions": []},
    )

    monzo_account.list_transactions(
        from_datetime=datetime(2022, 4, 20),
        to_datetime=datetime(2022, 11, 15),
    )

    assert (
        mock_requests.last_request.url
        == f"{monzo_account.monzo_client.base_url}/transactions?"
        + urlencode(
            {
                "account_id": monzo_account.id,
                "since": datetime(2022, 4, 20).isoformat() + "Z",
                "before": datetime(2022, 11, 15).isoformat() + "Z",
                "limit": 100,
            }
        )
    )


def test_update_balance_variables(
    monzo_account: Account, mock_requests: Mocker
) -> None:
    """Test that the balance variables are updated correctly."""

    assert monzo_account.last_balance_update == datetime(1970, 1, 1)
    with freeze_time():
        monzo_account.update_balance_variables()

        assert monzo_account.last_balance_update == datetime.utcnow()

    assert monzo_account.balance_variables.dict() == {
        "balance": 177009,
        "balance_including_flexible_savings": 41472,
        "currency": "GBP",
        "local_currency": "",
        "local_exchange_rate": 0,
        "local_spend": [{"currency": "GBP", "spend_today": -12}],
        "spend_today": -12,
        "total_balance": 41472,
    }
    assert mock_requests.request_history[
        0
    ].url == f"{monzo_account.monzo_client.base_url}/balance?" + urlencode(
        {"account_id": monzo_account.id}
    )
    assert mock_requests.request_history[0].method == "GET"


def test_balance_property(monzo_account: Account, caplog: LogCaptureFixture) -> None:
    """Test that the `balance` property returns the correct value."""

    assert monzo_account.balance == 177009
    assert (
        "Balance variable update threshold crossed, getting new values" in caplog.text
    )


def test_balance_including_flexible_savings_property(
    monzo_account: Account, caplog: LogCaptureFixture
) -> None:
    """Test the `balance_including_flexible_savings` property."""

    assert monzo_account.balance_including_flexible_savings == 41472
    assert (
        "Balance variable update threshold crossed, getting new values" in caplog.text
    )


def test_spend_today_property(
    monzo_account: Account, caplog: LogCaptureFixture
) -> None:
    """Test that the `spend_today` property returns the correct value."""

    assert monzo_account.spend_today == -12
    assert (
        "Balance variable update threshold crossed, getting new values" in caplog.text
    )


def test_total_balance_property(
    monzo_account: Account, caplog: LogCaptureFixture
) -> None:
    """Test that the `total_balance` property returns the correct value."""

    assert monzo_account.total_balance == 41472
    assert (
        "Balance variable update threshold crossed, getting new values" in caplog.text
    )


def test_eq(monzo_account: Account, monzo_client: MonzoClient) -> None:
    """Test the equality operator."""
    assert monzo_account == monzo_account  # pylint: disable=comparison-with-itself
    assert monzo_account != Account.from_json_response(
        read_json_file("account_type=uk_retail_joint.json", host_name="monzo/accounts")[
            "accounts"
        ][0],
        monzo_client=monzo_client,
    )
    assert monzo_account != "test"


def test_repr(monzo_account: Account) -> None:
    """Test the repr representation of the object."""
    assert repr(monzo_account) == f"<Account {monzo_account.id}>"
