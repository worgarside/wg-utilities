"""Fixtures for the `TrueLayer` UTs."""
from __future__ import annotations

from pathlib import Path

from pytest import fixture
from requests_mock import Mocker

from tests.conftest import (
    FLAT_FILES_DIR,
    YieldFixture,
    get_flat_file_from_url,
    read_json_file,
)
from wg_utilities.clients.oauth_client import OAuthCredentials
from wg_utilities.clients.truelayer import Account, Bank, Card, TrueLayerClient


@fixture(scope="function", name="account")
def _account(truelayer_client: TrueLayerClient) -> Account:
    """Fixture for creating a `Account` instance."""

    return Account.from_json_response(
        read_json_file(
            "data/v1/accounts/74i84q4696c886tr0ic9z4376ql2j316.json",
            host_name="truelayer",
        )["results"][0],
        truelayer_client=truelayer_client,
    )


@fixture(scope="function", name="card")
def _card(truelayer_client: TrueLayerClient) -> Card:
    """Fixture for creating a `Card` instance."""

    return Card.from_json_response(
        read_json_file(
            "data/v1/cards/uw366ug2sjp9t2zduu706sy6y63p4x4s.json",
            host_name="truelayer",
        )["results"][0],
        truelayer_client=truelayer_client,
    )


@fixture(scope="function", name="truelayer_client")
def _truelayer_client(
    temp_dir: Path,
    fake_oauth_credentials: OAuthCredentials,
) -> TrueLayerClient:
    """Fixture for creating a `TruelayerClient` instance."""

    (
        creds_cache_path := temp_dir / "oauth_credentials/truelayer_credentials.json"
    ).write_text(fake_oauth_credentials.json())

    return TrueLayerClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
        bank=Bank.ALLIED_IRISH_BANK_CORPORATE,
        creds_cache_path=creds_cache_path,
        log_requests=True,
    )


@fixture(scope="function", name="mock_requests", autouse=True)
def _mock_requests(mock_requests_root: Mocker) -> YieldFixture[Mocker]:
    """Fixture for mocking sync HTTP requests."""

    for path_object in (truelayer_dir := FLAT_FILES_DIR / "json/truelayer/").rglob("*"):
        if path_object.is_dir() or (
            path_object.is_file() and "=" not in path_object.name
        ):
            mock_requests_root.get(
                TrueLayerClient.BASE_URL
                + "/"
                + str(path_object.relative_to(truelayer_dir)).replace(".json", ""),
                json=get_flat_file_from_url,
            )

    yield mock_requests_root
