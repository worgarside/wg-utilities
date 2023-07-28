"""Fixtures and functions for OAuthClient tests."""
from __future__ import annotations

from typing import Any

from pytest import fixture
from requests_mock import Mocker

from tests.conftest import YieldFixture
from wg_utilities.clients.json_api_client import JsonApiClient


@fixture(scope="function", name="json_api_client")
def _oauth_client(
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> JsonApiClient[dict[str, Any]]:
    """Fixture for creating an OAuthClient instance."""

    return JsonApiClient(
        base_url="https://api.example.com",
        log_requests=True,
    )


@fixture(scope="function", name="mock_requests", autouse=True)
def _mock_requests(
    mock_requests_root: Mocker,
) -> YieldFixture[Mocker]:
    """Fixture for mocking sync HTTP requests."""

    yield mock_requests_root
