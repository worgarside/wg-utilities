"""Unit tests for the `wg_utilities.clients.google_drive.Directory` class."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.conftest import read_json_file
from wg_utilities.clients import GoogleDriveClient
from wg_utilities.clients.google_drive import Directory, Drive, EntityKind


def test_kind_validation(drive: Drive, google_drive_client: GoogleDriveClient) -> None:
    """Test that the `kind` field is validated."""

    directory_json = read_json_file(
        "v3/files/7tqryz0a9oyjfzf1cpbmllsblj-ohbi1e/fields=%2a.json",
        host_name="google/drive",
    )

    directory_json["kind"] = EntityKind.FILE

    Directory.from_json_response(
        directory_json,
        google_client=google_drive_client,
        host_drive=drive,
        parent=drive,
    )

    directory_json["kind"] = EntityKind.DIRECTORY

    Directory.from_json_response(
        directory_json,
        google_client=google_drive_client,
        host_drive=drive,
        parent=drive,
    )

    directory_json["kind"] = EntityKind.USER

    with pytest.raises(ValueError) as exc_info:
        Directory.from_json_response(
            directory_json,
            google_client=google_drive_client,
            host_drive=drive,
            parent=drive,
        )
    assert "Invalid kind for Directory: drive#user" in str(
        exc_info.value
    ) or "Invalid kind for Directory: EntityKind.USER" in str(exc_info.value)


def test_mime_type_validation(
    drive: Drive, google_drive_client: GoogleDriveClient
) -> None:
    """Test that the `mimeType` value is validated."""

    directory_json = read_json_file(
        "v3/files/7tqryz0a9oyjfzf1cpbmllsblj-ohbi1e/fields=%2a.json",
        host_name="google/drive",
    )

    directory_json["mimeType"] = "application/vnd.google-apps.spreadsheet"

    with pytest.raises(ValidationError) as exc_info:
        Directory.from_json_response(
            directory_json, google_client=google_drive_client, host_drive=drive
        )

    assert "Input should be 'application/vnd.google-apps.folder'" in str(exc_info.value)
