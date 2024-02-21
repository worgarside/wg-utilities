"""Unit tests for the `wg_utilities.clients.google_drive.File` class."""
from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pytz import utc

from tests.conftest import read_json_file
from wg_utilities.clients.google_drive import (
    Directory,
    Drive,
    EntityKind,
    File,
    ItemMetadataRetrieval,
    _User,
)

if TYPE_CHECKING:
    from requests_mock import Mocker

    from wg_utilities.clients import GoogleDriveClient


def test_from_json_response_instantiation(
    drive: Drive,
    google_drive_client: GoogleDriveClient,
) -> None:
    """Test that the `File` class can be instantiated."""

    file_json = read_json_file(
        "v3/files/1qx74t7epvdq55uqnwxgakohfnydxmc21/fields=%2a.json",
        host_name="google/drive",
    )

    file = File.from_json_response(
        file_json,
        google_client=google_drive_client,
        host_drive=drive,
    )

    assert isinstance(file, File)
    assert file.google_client == google_drive_client
    assert file.host_drive == drive


def test_getattr_override_on_demand_retrieval(
    google_drive_client: GoogleDriveClient,
    simple_file: File,
) -> None:
    """Test that null attributes are retrieved individually for `ON_INIT` IMR."""

    google_drive_client.item_metadata_retrieval = ItemMetadataRetrieval.ON_DEMAND

    # Can't directly access the attribute because that's what I'm testing
    assert simple_file.__dict__["size"] is None

    with patch.object(File, "describe") as mock_describe, patch.object(
        simple_file.google_client,
        "get_json_response",
        wraps=simple_file.google_client.get_json_response,
    ) as mock_get_json_response:
        assert simple_file.size == 1024

    assert simple_file.__dict__["size"] == 1024

    mock_describe.assert_not_called()
    mock_get_json_response.assert_called_once_with(
        "/files/1X9XHqui0CHzAGahgr1d0lIOn2jj5MZO-WU7l5fhCn4B",
        params={"fields": "size", "pageSize": None},
    )


def test_getattr_override_on_first_request_retrieval(
    google_drive_client: GoogleDriveClient,
    simple_file: File,
) -> None:
    """Test null attributes are retrieved individually for `ON_FIRST_REQUEST` IMR."""

    google_drive_client.item_metadata_retrieval = ItemMetadataRetrieval.ON_FIRST_REQUEST

    # Can't directly access the attribute because that's what I'm testing
    assert simple_file.__dict__["size"] is None

    with patch.object(
        File,
        "describe",
        wraps=simple_file.describe,
    ) as mock_describe, patch.object(
        simple_file.google_client,
        "get_json_response",
        wraps=simple_file.google_client.get_json_response,
    ) as mock_get_json_response:
        assert simple_file.size == simple_file.__dict__["size"] == 1024
        assert (
            simple_file.created_time
            == simple_file.__dict__["created_time"]
            == datetime(2022, 12, 22, 11, 34, 54, 221000, tzinfo=utc)
        )
        assert (
            simple_file.last_modifying_user
            == simple_file.__dict__["last_modifying_user"]
            == _User(
                kind=EntityKind.USER,
                displayName="Google User",
                photoLink="https://lh3.googleusercontent.com/a/ZPjPRv4wncXC5rJVs2U96b00Tdp85YYJq4FnPUyCLahXoMx=s64",
                me=True,
                permissionId="31838237028322295771",
                emailAddress="google-user@gmail.com",
            )
        )
        assert (
            simple_file.web_view_link
            == simple_file.__dict__["web_view_link"]
            == "https://docs.google.com/spreadsheets/d/1X9XHqui0CHzAGahgr1d0lIOn2jj5MZO-WU7l5fhCn4B/edit?usp=drivesdk"
        )

    mock_describe.assert_called_once()
    mock_get_json_response.assert_called_once_with(
        "/files/1X9XHqui0CHzAGahgr1d0lIOn2jj5MZO-WU7l5fhCn4B",
        params={"fields": "*", "pageSize": None},
    )


def test_mime_type_validation(
    drive: Drive,
    google_drive_client: GoogleDriveClient,
) -> None:
    """Test that the `mimeType` value is validated."""

    file_json = read_json_file(
        "v3/files/1qx74t7epvdq55uqnwxgakohfnydxmc21/fields=%2a.json",
        host_name="google/drive",
    )

    file_json["mimeType"] = "application/vnd.google-apps.folder"

    with pytest.raises(ValueError) as exc_info:
        File.from_json_response(
            file_json,
            google_client=google_drive_client,
            host_drive=drive,
        )

    assert "Use `Directory` class to create a directory" in str(exc_info.value)


@pytest.mark.parametrize(
    "parents_value",
    [
        pytest.param([], id="empty list"),
        pytest.param(
            ["a", "b"],  # length is immaterial
            id="multiple parents",
        ),
    ],
)
def test_parents_validation(
    drive: Drive,
    google_drive_client: GoogleDriveClient,
    parents_value: list[str],
) -> None:
    """Test that the `parents` value is validated."""

    file_json = read_json_file(
        "v3/files/1qx74t7epvdq55uqnwxgakohfnydxmc21/fields=%2a.json",
        host_name="google/drive",
    )

    file_json["parents"] = parents_value

    with pytest.raises(ValueError) as exc_info:
        File.from_json_response(
            file_json,
            google_client=google_drive_client,
            host_drive=drive,
        )

    assert "A File must have exactly one parent." in str(exc_info.value)


def test_parent_instance_validation(
    drive: Drive,
    google_drive_client: GoogleDriveClient,
) -> None:
    """Test that the `parent` value is validated."""

    file_json = read_json_file(
        "v3/files/1qx74t7epvdq55uqnwxgakohfnydxmc21/fields=%2a.json",
        host_name="google/drive",
    )

    assert drive.id != file_json["parents"][0]  # type: ignore[index]

    with pytest.raises(ValueError) as exc_info:
        File.from_json_response(
            file_json,
            google_client=google_drive_client,
            host_drive=drive,
            parent=drive,
        )

    assert f"Parent ID mismatch: {drive.id} != 3yz1SpGR2YtgnocrGzphb-qkKTfU4htSx" in str(
        exc_info.value,
    )


def test_describe(simple_file: File) -> None:
    """Test that the `describe` method gets all available data."""

    assert not simple_file._description

    with patch.object(
        simple_file.google_client,
        "get_json_response",
        wraps=simple_file.google_client.get_json_response,
    ) as mock_get_json_response:
        assert simple_file.describe() == read_json_file(
            "v3/files/1x9xhqui0chzagahgr1d0lion2jj5mzo-wu7l5fhcn4b/fields=%2a.json",
            host_name="google/drive",
        )

        assert isinstance(simple_file._description, dict)

        mock_get_json_response.assert_called_once_with(
            "/files/1X9XHqui0CHzAGahgr1d0lIOn2jj5MZO-WU7l5fhCn4B",
            params={"fields": "*", "pageSize": None},
        )

        # Check that a sample of values has been loaded
        mock_get_json_response.reset_mock()

        assert simple_file.created_time == datetime(
            2022,
            12,
            22,
            11,
            34,
            54,
            221000,
            tzinfo=utc,
        )
        assert simple_file.size == 1024
        assert (
            simple_file.web_view_link
            == "https://docs.google.com/spreadsheets/d/1X9XHqui0CHzAGahgr1d0lIOn2jj5MZO-WU7l5fhCn4B/edit?usp=drivesdk"
        )

        mock_get_json_response.assert_not_called()


def test_describe_force_update(simple_file: File) -> None:
    """Test that `describe` method refreshes all available data with `force_update`."""

    assert not simple_file._description

    with patch.object(
        simple_file.google_client,
        "get_json_response",
        wraps=simple_file.google_client.get_json_response,
    ) as mock_get_json_response:
        assert simple_file.describe() == read_json_file(
            "v3/files/1x9xhqui0chzagahgr1d0lion2jj5mzo-wu7l5fhcn4b/fields=%2a.json",
            host_name="google/drive",
        )

        simple_file.describe()

        assert isinstance(simple_file._description, dict)

        mock_get_json_response.assert_called_once_with(
            "/files/1X9XHqui0CHzAGahgr1d0lIOn2jj5MZO-WU7l5fhCn4B",
            params={"fields": "*", "pageSize": None},
        )

        mock_get_json_response.reset_mock()

        simple_file.describe()
        simple_file.describe(force_update=True)

        mock_get_json_response.assert_called_once_with(
            "/files/1X9XHqui0CHzAGahgr1d0lIOn2jj5MZO-WU7l5fhCn4B",
            params={"fields": "*", "pageSize": None},
        )


def test_describe_with_invalid_field(simple_file: File, mock_requests: Mocker) -> None:
    """Test that `describe` method raises `ValueError` with an invalid field."""

    res = read_json_file(
        "v3/files/1x9xhqui0chzagahgr1d0lion2jj5mzo-wu7l5fhcn4b/fields=%2a.json",
        host_name="google/drive",
    )

    res["invalidField"] = "invalid_value"

    mock_requests.get(
        "https://www.googleapis.com/drive/v3/files/1X9XHqui0CHzAGahgr1d0lIOn2jj5MZO-WU7l5fhCn4B",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json=res,
    )

    with pytest.raises(ValueError) as exc_info:
        simple_file.describe()

    assert (
        str(exc_info.value)
        == "Received unexpected field 'invalidField' with value 'invalid_value' from Google Drive API"
    )


def test_parent_property(simple_file: File, directory: Directory, drive: Drive) -> None:
    """Test that the `parent` property returns the parent Folder."""

    simple_file.parent_ = None

    assert directory.all_known_children == []

    with patch.object(
        Drive,
        "get_directory_by_id",
        wraps=drive.get_directory_by_id,
    ) as mock_get_directory_by_id:
        assert simple_file.parent == directory

        mock_get_directory_by_id.assert_called_once_with(directory.id)

    assert simple_file.parent.all_known_children == [simple_file]

    # This looks like I'm testing the Directory class, but it's a File subclass, so it's
    # fine :)

    directory.parent_ = None
    drive._directories = []

    assert drive.all_known_children == []
    assert directory.parent == drive
    assert drive.all_known_children == [directory]


def test_gt(file: File, drive: Drive) -> None:
    """Test that the `>` behaves as expected."""

    assert "Archive Log" > "128GB SD Card - Old MacBook.zip"
    assert file > drive.get_file_by_id("7FVjoh2-g6v1sNPXPNRkl2PF174lRKHe6")
    assert not drive.get_file_by_id("7FVjoh2-g6v1sNPXPNRkl2PF174lRKHe6") > file
    assert not file > file


def test_lt(file: File, drive: Drive) -> None:
    """Test that the `<` behaves as expected."""

    assert "128GB SD Card - Old MacBook.zip" < "Archive Log"
    assert drive.get_file_by_id("7FVjoh2-g6v1sNPXPNRkl2PF174lRKHe6") < file
    assert not file < drive.get_file_by_id("7FVjoh2-g6v1sNPXPNRkl2PF174lRKHe6")
    assert not file < file
