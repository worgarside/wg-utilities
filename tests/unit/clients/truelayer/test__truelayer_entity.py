# pylint: disable=protected-access
"""Unit tests for `TrueLayerEntity`."""


from __future__ import annotations

from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Literal
from unittest.mock import patch

from freezegun import freeze_time
from pytest import mark, raises
from requests_mock import Mocker

from tests.conftest import read_json_file
from wg_utilities.clients.truelayer import (
    Account,
    Card,
    Transaction,
    TrueLayerClient,
    TrueLayerEntity,
)


def test_from_json_response_instantiation(truelayer_client: TrueLayerClient) -> None:
    """Test that a TrueLayerEntity can be instantiated."""

    tle = TrueLayerEntity.from_json_response(
        {  # type: ignore[arg-type]
            "account_id": "w93af48b27r7s0u2s4y811w6929l616x",
            "currency": "GBP",
            "display_name": "Xuccyyxl",
            "provider": {
                "display_name": "account_provider",
                # pylint: disable=line-too-long
                "logo_uri": "https://truelayer-client-logos.s3-eu-west-1.amazonaws.com/banks/banks-icons/ft-ajxyecqs-icon.svg",  # noqa: E501
                "provider_id": "ft-ajxyecqs",
            },
            "update_timestamp": "2023-03-25T18:16:20.256Z",
        },
        truelayer_client=truelayer_client,
    )

    assert isinstance(tle, TrueLayerEntity)

    assert tle.id == "w93af48b27r7s0u2s4y811w6929l616x"
    assert tle.truelayer_client == truelayer_client


@mark.parametrize(
    ("from_datetime", "to_datetime"),
    (
        (datetime(2023, 1, 1), datetime(2023, 1, 7)),
        (datetime(2023, 2, 1, 1, 2, 3), datetime(2023, 2, 7, 3, 2, 1)),
        (None, None),
    ),
)
def test_get_transactions(
    account: Account, from_datetime: datetime | None, to_datetime: datetime | None
) -> None:
    """Test that `get_transactions` returns a list of `Transaction` objects."""

    transactions = account.get_transactions(
        from_datetime=from_datetime, to_datetime=to_datetime
    )

    to_datetime = to_datetime or datetime(2023, 3, 30)
    from_datetime = from_datetime or to_datetime - timedelta(days=90)

    assert transactions
    assert all(isinstance(t, Transaction) for t in transactions)
    assert all(
        from_datetime < t.timestamp.replace(tzinfo=None) < to_datetime
        for t in transactions
    )


def test_update_balance_values(account: Account) -> None:
    """Test that `TrueLayerEntity.update_balance_values` updates the balance values."""

    assert not hasattr(account, "_available_balance")
    assert not hasattr(account, "_current_balance")
    assert not hasattr(account, "_overdraft")

    with freeze_time(frozen_datetime := datetime.utcnow()):
        account.update_balance_values()

    assert account._available_balance == 1234.56
    assert account._current_balance == 1234.56
    assert account._overdraft == 0.0

    assert frozen_datetime == account.last_balance_update


def test_update_balance_values_multiple_results(
    account: Account, mock_requests: Mocker
) -> None:
    """Test that a `ValueError` is raised if the response has two result entries."""

    response_json = read_json_file(
        "data/v1/accounts/74i84q4696c886tr0ic9z4376ql2j316/balance.json",
        host_name="truelayer",
    )

    response_json["results"].append(response_json["results"][0])

    mock_requests.get(
        f"{account.truelayer_client.base_url}/data/v1/accounts/{account.id}/balance",
        json=response_json,
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
    )

    with raises(ValueError) as exc_info:
        account.update_balance_values()

    assert (
        str(exc_info.value)
        == "Unexpected number of results when getting balance info: 2"
    )


@mark.parametrize(
    ("property_name", "expected_value"),
    (
        ("available_balance", 1234.56),
        ("current_balance", 1234.56),
        ("overdraft", 0.0),
        ("credit_limit", None),
        ("last_statement_balance", None),
        ("last_statement_date", None),
        ("payment_due", None),
        ("payment_due_date", None),
    ),
)
def test_get_balance_property_account(
    account: Account,
    property_name: Literal[
        "available_balance",
        "current_balance",
        "overdraft",
        "credit_limit",
        "last_statement_balance",
        "last_statement_date",
        "payment_due",
        "payment_due_date",
    ],
    expected_value: str | float | int | None,
) -> None:
    """Test that `TrueLayerEntity.get_balance` returns the correct balance value."""

    with patch.object(
        TrueLayerEntity, "update_balance_values", wraps=account.update_balance_values
    ) as mock_update_balance_values:
        assert account._get_balance_property(property_name) == expected_value

        # Second call shouldn't trigger updates because we're within the threshold
        _ = account._get_balance_property(property_name)

        if property_name in Account.BALANCE_FIELDS:
            mock_update_balance_values.assert_called_once()

            # Third call should trigger updates because we're now outside the threshold
            account.last_balance_update = datetime.utcnow() - timedelta(hours=1e6)
            _ = account._get_balance_property(property_name)

            assert mock_update_balance_values.call_count == 2
        else:
            mock_update_balance_values.assert_not_called()


@mark.parametrize(
    ("property_name", "expected_value"),
    (
        ("available_balance", 3279.0),
        ("current_balance", 20.0),
        ("overdraft", None),
        ("credit_limit", 1464),
        ("last_statement_balance", 319),
        ("last_statement_date", None),
        ("payment_due", 5.0),
        ("payment_due_date", datetime(2023, 3, 30).date()),
        ("invalid_value", None),
    ),
)
def test_get_balance_property_card(
    card: Card,
    property_name: Literal[
        "available_balance",
        "current_balance",
        "overdraft",
        "credit_limit",
        "last_statement_balance",
        "last_statement_date",
        "payment_due",
        "payment_due_date",
    ],
    expected_value: str | float | int | None,
) -> None:
    """Test that `TrueLayerEntity.get_balance` returns the correct balance value."""

    with patch.object(
        TrueLayerEntity, "update_balance_values", wraps=card.update_balance_values
    ) as mock_update_balance_values:
        assert card._get_balance_property(property_name) == expected_value

        # `last_statement_date` is a special case because it's `None`, so we should
        # check again. The rest of the test remains the same.
        if property_name != "last_statement_date":
            # Second call shouldn't trigger updates because we're within the threshold
            _ = card._get_balance_property(property_name)

        if property_name in Card.BALANCE_FIELDS:
            mock_update_balance_values.assert_called_once()

            # Third call should trigger updates because we're now outside the threshold
            card.last_balance_update = datetime.utcnow() - timedelta(hours=1e6)
            _ = card._get_balance_property(property_name)

            assert mock_update_balance_values.call_count == 2
        else:
            mock_update_balance_values.assert_not_called()


@mark.parametrize(
    "property_name",
    sorted(set(Account.BALANCE_FIELDS + Card.BALANCE_FIELDS)),  # type: ignore[operator]
)
def test_balance_property(
    account: Account,
    property_name: Literal[
        "available_balance",
        "current_balance",
        "overdraft",
        "credit_limit",
        "last_statement_balance",
        "last_statement_date",
        "payment_due",
        "payment_due_date",
    ],
) -> None:
    """Test that all balance properties call `_get_balance_property` correctly."""

    with patch.object(
        TrueLayerEntity, "_get_balance_property", return_value=1234.56
    ) as mock_get_balance_property:
        assert getattr(account, property_name) == 1234.56
        mock_get_balance_property.assert_called_once_with(property_name)
