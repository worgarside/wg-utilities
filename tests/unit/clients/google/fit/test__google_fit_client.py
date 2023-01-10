"""Unit Tests for `wg_utilities.clients.google_fit.GoogleFitClient`."""
from __future__ import annotations

from unittest.mock import patch

from wg_utilities.clients import GoogleFitClient
from wg_utilities.clients.google_fit import DataSource


def test_instantiation() -> None:
    """Test that the `GoogleFitClient` class can be instantiated."""

    client = GoogleFitClient(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret",
    )

    assert isinstance(client, GoogleFitClient)
    # pylint: disable=use-implicit-booleaness-not-comparison
    assert client.data_sources == {}


def test_get_data_source(google_fit_client: GoogleFitClient) -> None:
    """Test that the `get_data_source` method returns a `DataSource` object."""

    expected_id = (
        "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
    )

    assert google_fit_client.data_sources == {}

    with patch(
        "wg_utilities.clients.google_fit.DataSource", wraps=DataSource
    ) as mock_data_source:
        data_source = google_fit_client.get_data_source(data_source_id=expected_id)

    assert isinstance(data_source, DataSource)

    mock_data_source.assert_called_once_with(
        data_source_id=expected_id,
        google_client=google_fit_client,
    )

    assert google_fit_client.data_sources == {expected_id: data_source}
