"""Fixtures and functions for OAuthClient tests."""

from __future__ import annotations

from typing import Any

import pytest
from requests_mock import Mocker

from wg_utilities.clients.json_api_client import JsonApiClient


@pytest.fixture(name="json_api_client")
def oauth_client_(
    mock_requests: Mocker,  # noqa: ARG001
) -> JsonApiClient[dict[str, Any]]:
    """Fixture for creating an OAuthClient instance."""

    return JsonApiClient(
        base_url="https://api.example.com",
        log_requests=True,
    )


@pytest.fixture(name="mock_requests", autouse=True)
def mock_requests_(
    mock_requests_root: Mocker,
) -> Mocker:
    """Fixture for mocking sync HTTP requests."""

    return mock_requests_root
