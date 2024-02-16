"""Fixtures and functions for OAuthClient tests."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from jwt import decode
from requests_mock import Mocker

from tests.conftest import YieldFixture
from wg_utilities.api import TempAuthServer
from wg_utilities.clients.oauth_client import OAuthClient, OAuthCredentials
from wg_utilities.functions.file_management import force_mkdir


def get_jwt_expiry(token: str) -> float:
    """Get the expiry time of a JWT token."""
    return float(decode(token, options={"verify_signature": False})["exp"])


@pytest.fixture(name="oauth_client")
def oauth_client_(
    temp_dir: Path,
    fake_oauth_credentials: OAuthCredentials,
    mock_requests: Mocker,  # noqa: ARG001
) -> OAuthClient[dict[str, Any]]:
    """Fixture for creating an OAuthClient instance."""

    (
        creds_cache_path := force_mkdir(
            temp_dir / "oauth_credentials" / "test_client_id.json",
            path_is_file=True,
        )
    ).write_text(fake_oauth_credentials.model_dump_json(exclude_none=True))

    return OAuthClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
        base_url="https://api.example.com",
        access_token_endpoint="https://api.example.com/oauth2/token",
        log_requests=True,
        creds_cache_path=Path(creds_cache_path),
        auth_link_base="https://api.example.com/oauth2/authorize",
    )


@pytest.fixture(scope="session", name="flask_app")
def flask_app_() -> Flask:
    """Fixture for Flask app."""

    return Flask(__name__)


@pytest.fixture(name="server_thread")
def server_thread_(flask_app: Flask) -> YieldFixture[TempAuthServer.ServerThread]:
    """Fixture for creating a server thread."""

    server_thread = TempAuthServer.ServerThread(flask_app)
    server_thread.start()

    yield server_thread

    server_thread.shutdown()
    del server_thread


@pytest.fixture(name="temp_auth_server")
def temp_auth_server_() -> YieldFixture[TempAuthServer]:
    """Fixture for creating a temporary auth server."""

    temp_auth_server = TempAuthServer(__name__, auto_run=False, debug=True, port=0)

    yield temp_auth_server

    temp_auth_server.stop_server()


@pytest.fixture(name="mock_requests", autouse=True)
def mock_requests_(mock_requests_root: Mocker, live_jwt_token_alt: str) -> Mocker:
    """Fixture for mocking sync HTTP requests."""

    mock_requests_root.post(
        "https://api.example.com/oauth2/token",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={
            "access_token": live_jwt_token_alt,
            "client_id": "test_client_id",
            "expires_in": 3600,
            "refresh_token": "new_test_refresh_token",
            "scope": "test_scope,test_scope_two",
            "token_type": "Bearer",
        },
    )

    return mock_requests_root
