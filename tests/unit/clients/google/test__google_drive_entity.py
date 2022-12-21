"""Unit tests for `wg_utilities.clients.google_drive.GoogleDriveEntity`."""
from __future__ import annotations

from pytest import raises

from wg_utilities.clients import GoogleDriveClient
from wg_utilities.clients.google_drive import Directory, Drive, GoogleDriveEntity


def test_from_json_response_instantiation(
    google_drive_client: GoogleDriveClient, drive: Drive, directory: Directory
) -> None:
    """Test instantiation of the GoogleDriveEntity class."""
    google_drive_entity = GoogleDriveEntity.from_json_response(
        {
            "id": "test-id",
            "name": "Entity Name",
            "mimeType": "application/vnd.google-apps.file",
        },
        google_client=google_drive_client,
        host_drive=drive,
        parent=directory,
    )
    assert isinstance(google_drive_entity, GoogleDriveEntity)

    assert google_drive_entity.dict() == {
        "id": "test-id",
        "name": "Entity Name",
        "mimeType": "application/vnd.google-apps.file",
    }

    assert google_drive_entity.id == "test-id"
    assert google_drive_entity.name == "Entity Name"
    assert google_drive_entity.mime_type == "application/vnd.google-apps.file"
    assert google_drive_entity.host_drive_ == drive
    assert google_drive_entity.parent_ == directory

    assert google_drive_entity.google_client == google_drive_client


def test_host_drive_property_raises_error(
    google_drive_client: GoogleDriveClient, drive: Drive, directory: Directory
) -> None:
    """Test the `host_drive` property raises an error (due to invalid class)."""
    gde = GoogleDriveEntity.from_json_response(
        {
            "id": "test-id",
            "name": "Entity Name",
            "mimeType": "application/vnd.google-apps.file",
        },
        google_client=google_drive_client,
        host_drive=drive,
        parent=directory,
    )

    with raises(TypeError) as exc_info:
        _ = gde.host_drive

    assert str(exc_info.value) == "Cannot get host drive of GoogleDriveEntity."


def test_parent_property_returns_parent__attribute(
    google_drive_client: GoogleDriveClient, drive: Drive, directory: Directory
) -> None:
    """Test the `parent` property returns the `parent_` attribute."""

    gde = GoogleDriveEntity.from_json_response(
        {
            "id": "test-id",
            "name": "Entity Name",
            "mimeType": "application/vnd.google-apps.file",
        },
        google_client=google_drive_client,
        host_drive=drive,
        parent=directory,
    )

    assert gde.parent == gde.parent_ == directory
