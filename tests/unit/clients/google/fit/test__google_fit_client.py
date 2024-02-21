"""Unit Tests for `wg_utilities.clients.google_fit.GoogleFitClient`."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from wg_utilities.clients import GoogleFitClient
from wg_utilities.clients.google_fit import DataSource

if TYPE_CHECKING:
    from wg_utilities.clients.oauth_client import OAuthCredentials


def test_instantiation(fake_oauth_credentials: OAuthCredentials) -> None:
    """Test that the `GoogleFitClient` class can be instantiated."""

    client = GoogleFitClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
    )

    assert isinstance(client, GoogleFitClient)
    assert client.data_sources == {}


def test_get_data_source(google_fit_client: GoogleFitClient) -> None:
    """Test that the `get_data_source` method returns a `DataSource` object."""

    expected_id = (
        "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
    )

    assert google_fit_client.data_sources == {}

    with patch(
        "wg_utilities.clients.google_fit.DataSource",
        wraps=DataSource,
    ) as mock_data_source:
        data_source = google_fit_client.get_data_source(data_source_id=expected_id)

    assert isinstance(data_source, DataSource)

    mock_data_source.assert_called_once_with(
        data_source_id=expected_id,
        google_client=google_fit_client,
    )

    assert google_fit_client.data_sources == {expected_id: data_source}
