"""Unit tests for `wg_utilities.clients.google_drive.GoogleDriveClient`."""

from __future__ import annotations

from unittest.mock import patch

from wg_utilities.clients import GoogleDriveClient
from wg_utilities.clients.google_drive import Drive, ItemMetadataRetrieval
from wg_utilities.clients.oauth_client import OAuthCredentials


def test_instantiation(fake_oauth_credentials: OAuthCredentials) -> None:
    """Test that the `GoogleDriveClient` class can be instantiated."""

    client = GoogleDriveClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
    )

    assert isinstance(client, GoogleDriveClient)
    assert client.item_metadata_retrieval == ItemMetadataRetrieval.ON_FIRST_REQUEST


def test_my_drive_property(google_drive_client: GoogleDriveClient) -> None:
    """Test that the `my_drive` property returns a `Drive` object."""

    with patch.object(
        google_drive_client,
        "get_json_response",
        wraps=google_drive_client.get_json_response,
    ) as mock_get_json_response:
        my_drive = google_drive_client.my_drive

    assert isinstance(my_drive, Drive)
    assert my_drive.google_client is google_drive_client

    mock_get_json_response.assert_called_once_with(
        "/files/root", params={"fields": "*", "pageSize": None}
    )

    assert my_drive.id == "6HP-cwhAzI78zEi4NNZ"


def test_shared_drives_property(google_drive_client: GoogleDriveClient) -> None:
    """Test that the `shared_drives` property returns a list of `Drive` objects."""

    with patch.object(
        google_drive_client, "get_items", wraps=google_drive_client.get_items
    ) as mock_get_items:
        shared_drives = google_drive_client.shared_drives

    assert isinstance(shared_drives, list)
    assert all(isinstance(d, Drive) for d in shared_drives)
    assert all(d.google_client is google_drive_client for d in shared_drives)

    mock_get_items.assert_called_once_with(
        "/drives", list_key="drives", params={"fields": "*"}
    )

    assert len(shared_drives) == 2
    assert shared_drives[0].id == "2MRTrlO0S2aKbXx3OIN"
    assert shared_drives[1].id == "7LUC-DSr43i5CPz8IHB"
