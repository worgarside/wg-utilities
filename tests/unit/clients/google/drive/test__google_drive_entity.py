"""Unit tests for `wg_utilities.clients.google_drive._GoogleDriveEntity`."""
from __future__ import annotations

from json import loads

from pytest import raises

from wg_utilities.clients import GoogleDriveClient
from wg_utilities.clients.google_drive import _GoogleDriveEntity


def test_model_dump_method(
    google_drive_client: GoogleDriveClient,
) -> None:
    """Test the `model_dump` method."""
    google_drive_entity = _GoogleDriveEntity.model_validate(
        {
            "id": "test-id",
            "name": "Entity Name",
            "google_client": google_drive_client,
            "mimeType": "application/vnd.google-apps.file",
        },
    )

    assert google_drive_entity.model_dump() == {
        "id": "test-id",
        "name": "Entity Name",
        "mimeType": "application/vnd.google-apps.file",
    }


def test_model_dump_json_method(
    google_drive_client: GoogleDriveClient,
) -> None:
    """Test the `model_dump_json` method."""
    google_drive_entity = _GoogleDriveEntity.model_validate(
        {
            "id": "test-id",
            "name": "Entity Name",
            "google_client": google_drive_client,
            "mimeType": "application/vnd.google-apps.file",
        },
    )

    assert loads(google_drive_entity.model_dump_json()) == {
        "id": "test-id",
        "name": "Entity Name",
        "mimeType": "application/vnd.google-apps.file",
    }


def test_host_drive_property_raises_error(
    google_drive_client: GoogleDriveClient,
) -> None:
    """Test the `host_drive` property raises an error (due to invalid class)."""
    google_drive_entity = _GoogleDriveEntity.model_validate(
        {
            "id": "test-id",
            "name": "Entity Name",
            "google_client": google_drive_client,
            "mimeType": "application/vnd.google-apps.file",
        },
    )

    with raises(TypeError) as exc_info:
        _ = google_drive_entity.host_drive

    assert str(exc_info.value) == "Cannot get host drive of _GoogleDriveEntity."
