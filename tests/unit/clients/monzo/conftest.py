"""Fixtures for the Monzo client tests."""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from requests_mock import Mocker

from tests.conftest import FLAT_FILES_DIR, get_flat_file_from_url, read_json_file
from wg_utilities.clients.monzo import Account, MonzoClient, Pot
from wg_utilities.clients.oauth_client import OAuthCredentials


@pytest.fixture(name="monzo_account")
def monzo_account_(monzo_client: MonzoClient) -> Account:
    """Fixture for creating a Account instance."""

    return Account.from_json_response(
        read_json_file("account_type=uk_retail.json", host_name="monzo/accounts")[
            "accounts"
        ][0],
        monzo_client=monzo_client,
    )


@pytest.fixture(name="monzo_client")
def monzo_client_(
    temp_dir: Path,
    fake_oauth_credentials: OAuthCredentials,
    mock_requests: Mocker,  # noqa: ARG001
    mock_open_browser: MagicMock,  # noqa: ARG001
) -> MonzoClient:
    """Fixture for creating a MonzoClient instance."""

    (
        creds_cache_path := temp_dir / "oauth_credentials/monzo_credentials.json"
    ).write_text(fake_oauth_credentials.model_dump_json())

    return MonzoClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        log_requests=True,
        creds_cache_path=creds_cache_path,
    )


@pytest.fixture(name="monzo_pot")
def monzo_pot_() -> Pot:
    """Fixture for creating a Pot instance."""

    return Pot(
        **read_json_file(
            "current_account_id=acc_0000000000000000000000.json",
            host_name="monzo/pots",
        )["pots"][14]
    )


@pytest.fixture(name="mock_requests", autouse=True)
def mock_requests_(mock_requests_root: Mocker) -> Mocker:
    """Fixture for mocking sync HTTP requests."""

    for path_object in (monzo_dir := FLAT_FILES_DIR / "json" / "monzo").rglob("*"):
        if path_object.is_dir():
            mock_requests_root.get(
                MonzoClient.BASE_URL + "/" + str(path_object.relative_to(monzo_dir)),
                json=get_flat_file_from_url,
            )

    mock_requests_root.put(
        f"{MonzoClient.BASE_URL}/pots/pot_0000000000000000000014/deposit",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
    )

    return mock_requests_root
