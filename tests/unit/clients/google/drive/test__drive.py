# pylint: disable=protected-access
"""Unit tests for the `wg_utilities.clients.google_drive.Drive` class."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from random import choice
from typing import Any
from unittest.mock import Mock, call, patch

from pytest import mark, param, raises

from tests.conftest import read_json_file
from wg_utilities.clients import GoogleDriveClient
from wg_utilities.clients.google_drive import (
    Directory,
    Drive,
    EntityKind,
    EntityType,
    File,
    ItemMetadataRetrieval,
)


@mark.parametrize(
    "drive_json",
    (
        param(
            read_json_file(
                "v3/files/root/fields=%2a.json",
                host_name="google/drive",
            ),
            id="My Drive",
        ),
        param(
            read_json_file(  # type: ignore[index]
                "v3/drives/pagesize=50&fields=%2a.json",
                host_name="google/drive",
            )["drives"][
                0  # type: ignore[index]
            ],
            id="Shared Drive 1",
        ),
        param(
            read_json_file(  # type: ignore[index]
                "v3/drives/pagesize=50&fields=%2a.json",
                host_name="google/drive",
            )["drives"][
                1  # type: ignore[index]
            ],
            id="Shared Drive 2",
        ),
    ),
)
def test_from_json_response(
    drive_json: Mapping[str, Any], google_drive_client: GoogleDriveClient
) -> None:
    """Test that a `Drive` instance can be created from a JSON response."""

    drive = Drive.from_json_response(
        drive_json,
        google_client=google_drive_client,
    )

    assert drive.id == drive_json["id"]
    assert drive.name == drive_json["name"]
    assert drive.kind == EntityKind.DRIVE
    assert drive.google_client == google_drive_client


def test_kind_validation(google_drive_client: GoogleDriveClient) -> None:
    """Test that the `kind` field is validated."""

    drive_json = read_json_file(
        "v3/files/root/fields=%2a.json",
        host_name="google/drive",
    )

    drive_json["kind"] = EntityKind.FILE

    Drive.from_json_response(
        drive_json,
        google_client=google_drive_client,
    )

    drive_json["kind"] = EntityKind.DRIVE

    Drive.from_json_response(
        drive_json,
        google_client=google_drive_client,
    )

    drive_json["kind"] = EntityKind.USER

    with raises(ValueError) as exc_info:
        Drive.from_json_response(
            drive_json,
            google_client=google_drive_client,
        )
    assert "Invalid kind for Drive: drive#user" in str(exc_info.value) or (
        # Python 3.11
        "Invalid kind for Drive: EntityKind.USER "
        in str(exc_info.value)
    )


@mark.parametrize(
    ("cls", "entity_id", "expected_path"),
    (
        (
            File,
            "1X9XHqui0CHzAGahgr1d0lIOn2jj5MZO-WU7l5fhCn4B",
            "/My Drive/Archives/Archive Log",
        ),
        (
            Directory,
            "3yz1SpGR2YtgnocrGzphb-qkKTfU4htSx",
            "/My Drive/Archives/Old Documents",
        ),
    ),
)
def test_get_entity_by_id(
    drive: Drive, cls: type[File | Directory], entity_id: str, expected_path: str
) -> None:
    """Test the generic `_get_entity_by_id` method."""

    expected = drive.navigate(expected_path)

    with patch.object(
        drive.google_client,
        "get_json_response",
        wraps=drive.google_client.get_json_response,
    ) as mock_get_json_response:
        actual = drive._get_entity_by_id(
            cls,
            entity_id,
        )

        mock_get_json_response.assert_called_once_with(
            f"/files/{entity_id}",
            params={"fields": "*", "pageSize": None},
        )

        mock_get_json_response.reset_mock()
        drive.google_client.item_metadata_retrieval = ItemMetadataRetrieval.ON_DEMAND

        drive._get_entity_by_id(
            cls,
            entity_id,
        )

        mock_get_json_response.assert_called_once_with(
            f"/files/{entity_id}",
            params={"fields": "id, name, parents, mimeType, kind", "pageSize": None},
        )

    assert actual == expected


def test_get_directory_by_id_no_matching_children(
    directory: Directory, drive: Drive
) -> None:
    """Test the `get_directory_by_id` method."""

    # Populate the `_directories` attribute
    _ = drive.directories

    drive._all_directories.remove(directory)

    assert directory not in drive._all_directories

    with patch.object(
        drive,
        "_get_entity_by_id",
        wraps=drive._get_entity_by_id,
    ) as mock_get_entity_by_id:
        assert drive.get_directory_by_id(directory.id) == directory

    mock_get_entity_by_id.assert_called_once_with(Directory, directory.id)


def test_get_directory_by_id_known_child(directory: Directory, drive: Drive) -> None:
    """Test the `get_directory_by_id` method."""

    # Just to populate the `_directories` attribute
    drive.navigate("/My Drive/Archives/Old Documents")

    assert directory in drive.all_known_children

    with patch.object(
        drive,
        "_get_entity_by_id",
        wraps=drive._get_entity_by_id,
    ) as mock_get_entity_by_id:
        assert drive.get_directory_by_id(directory.id) == directory

    mock_get_entity_by_id.assert_not_called()


def test_get_file_by_id_no_matching_children(file: File, drive: Drive) -> None:
    """Test the `get_file_by_id` method."""

    # Populate the `_files` attribute
    _ = drive.files

    assert file not in drive.all_known_children

    with patch.object(
        drive,
        "_get_entity_by_id",
        wraps=drive._get_entity_by_id,
    ) as mock_get_entity_by_id:
        assert drive.get_file_by_id(file.id) == file

    mock_get_entity_by_id.assert_called_once_with(
        File,
        file.id,
    )


def test_get_file_by_id_known_child(drive: Drive) -> None:
    """Test the `get_file_by_id` method."""

    # This will inherently populate the `_files` attribute
    expected = choice(drive.files)

    with patch.object(
        drive,
        "_get_entity_by_id",
        wraps=drive._get_entity_by_id,
    ) as mock_get_entity_by_id:
        assert drive.get_file_by_id(expected.id) == expected

    mock_get_entity_by_id.assert_not_called()


def test_map_directories_only(drive: Drive) -> None:
    """Test the `map` method."""

    assert drive._directories_mapped is not True

    _ = drive.directories

    with patch.object(
        drive.google_client,
        "get_items",
        wraps=drive.google_client.get_items,
    ) as mock_get_items:
        mock_get_directory_by_id = Mock(wraps=drive.get_directory_by_id)
        object.__setattr__(drive, "get_directory_by_id", mock_get_directory_by_id)

        mock_get_file_by_id = Mock(wraps=drive.get_file_by_id)
        object.__setattr__(drive, "get_file_by_id", mock_get_file_by_id)

        drive.map(EntityType.DIRECTORY)

    assert drive._directories_mapped is True

    mock_get_items.assert_called_once_with(
        "/files",
        list_key="files",
        params={
            "pageSize": 1000,
            "fields": "nextPageToken, files(*)",
            "q": "mimeType = 'application/vnd.google-apps.folder'",
        },
    )

    mock_get_file_by_id.assert_not_called()

    assert sorted(mock_get_directory_by_id.call_args_list) == sorted(
        call(directory.id) for directory in drive._directories
    )

    assert drive._all_files == []

    assert isinstance(drive._all_directories, list)
    assert all(isinstance(d, Directory) for d in drive._all_directories)

    # This list is of *all* directories in the drive, not just the children
    assert not all(d.parent == drive for d in drive._all_directories)


def test_map_directories_and_files(drive: Drive) -> None:
    """Test the `map` method with a `map_type` of File."""

    assert drive._directories_mapped is not True
    assert drive._files_mapped is not True

    _ = drive.directories
    _ = drive.files

    assert drive.all_known_children != []

    with patch.object(
        drive.google_client,
        "get_items",
        wraps=drive.google_client.get_items,
    ) as mock_get_items:
        mock_get_directory_by_id = Mock(wraps=drive.get_directory_by_id)
        object.__setattr__(drive, "get_directory_by_id", mock_get_directory_by_id)

        mock_get_file_by_id = Mock(wraps=drive.get_file_by_id)
        object.__setattr__(drive, "get_file_by_id", mock_get_file_by_id)

        drive.google_client.item_metadata_retrieval = ItemMetadataRetrieval.ON_DEMAND
        drive.map(EntityType.FILE)

        assert drive._directories_mapped is True
        assert drive._files_mapped is True

    mock_get_items.assert_called_once_with(
        "/files",
        list_key="files",
        params={
            "pageSize": 1000,
            "fields": "nextPageToken, files(id, name, parents, mimeType, kind)",
        },
    )

    assert sorted(mock_get_directory_by_id.call_args_list) == sorted(
        call(directory.id) for directory in drive._directories
    )

    mock_get_file_by_id.assert_not_called()

    assert isinstance(drive._all_files, list)
    assert all(isinstance(f, File) for f in drive._all_files)

    assert isinstance(drive._all_directories, list)
    assert all(isinstance(d, Directory) for d in drive._all_directories)

    # This list is of *all* directories in the drive, not just the children
    assert not all(d.parent == drive for d in drive._all_directories)


def test_map_files_already_mapped(drive: Drive) -> None:
    """Test the `map` method when the files are already mapped."""

    drive._files_mapped = True
    assert drive._files_mapped is True

    with patch.object(
        drive.google_client,
        "get_items",
        wraps=drive.google_client.get_items,
    ) as mock_get_items:
        drive.map(EntityType.FILE)

        mock_get_items.assert_not_called()


def test_map_directories_already_mapped(drive: Drive) -> None:
    """Test the `map` method when the directories are already mapped."""

    drive._directories_mapped = True
    assert drive._directories_mapped is True

    with patch.object(
        drive.google_client,
        "get_items",
        wraps=drive.google_client.get_items,
    ) as mock_get_items:
        drive.map(EntityType.DIRECTORY)

    mock_get_items.assert_not_called()


@mark.parametrize(
    (
        "term",
        "entity_type",
        "max_results",
        "exact_match",
        "created_range",
        "expected_params",
    ),
    (
        (
            "test",
            EntityType.FILE,
            10,
            False,
            None,
            {
                "pageSize": 10,
                "fields": "nextPageToken, files(*)",
                "q": f"name contains 'test' and mimeType != '{Directory.MIME_TYPE}'",
            },
        ),
        (
            "test",
            EntityType.FILE,
            99999,
            False,
            None,
            {
                "pageSize": 1000,
                "fields": "nextPageToken, files(*)",
                "q": f"name contains 'test' and mimeType != '{Directory.MIME_TYPE}'",
            },
        ),
        (
            "test",
            EntityType.FILE,
            10,
            True,
            None,
            {
                "pageSize": 1,
                "fields": "nextPageToken, files(*)",
                "q": f"name = 'test' and mimeType != '{Directory.MIME_TYPE}'",
            },
        ),
        (
            "test",
            EntityType.FILE,
            10,
            False,
            (datetime(2020, 1, 1), datetime(2020, 1, 2)),
            {
                "pageSize": 10,
                "fields": "nextPageToken, files(*)",
                "q": f"name contains 'test' and mimeType != '{Directory.MIME_TYPE}' and"
                " createdTime > '2020-01-01T00:00:00' and createdTime <="
                " '2020-01-02T00:00:00'",
            },
        ),
        (
            "test",
            EntityType.DIRECTORY,
            10,
            False,
            None,
            {
                "pageSize": 10,
                "fields": "nextPageToken, files(*)",
                "q": f"name contains 'test' and mimeType = '{Directory.MIME_TYPE}'",
            },
        ),
        (
            "test",
            EntityType.DIRECTORY,
            10,
            True,
            None,
            {
                "pageSize": 1,
                "fields": "nextPageToken, files(*)",
                "q": f"name = 'test' and mimeType = '{Directory.MIME_TYPE}'",
            },
        ),
        (
            "test",
            EntityType.DIRECTORY,
            10,
            False,
            (datetime(2020, 1, 1), datetime(2020, 1, 2)),
            {
                "pageSize": 10,
                "fields": "nextPageToken, files(*)",
                "q": f"name contains 'test' and mimeType = '{Directory.MIME_TYPE}' and"
                " createdTime > '2020-01-01T00:00:00' and createdTime <="
                " '2020-01-02T00:00:00'",
            },
        ),
        (
            "test",
            None,
            10,
            False,
            (datetime(2020, 1, 1), datetime(2020, 1, 2)),
            {
                "pageSize": 10,
                "fields": "nextPageToken, files(*)",
                "q": "name contains 'test' and createdTime > '2020-01-01T00:00:00' and"
                " createdTime <= '2020-01-02T00:00:00'",
            },
        ),
    ),
)
def test_search(
    drive: Drive,
    term: str,
    entity_type: EntityType,
    max_results: int,
    exact_match: bool,
    created_range: tuple[datetime, datetime] | None,
    expected_params: dict[str, Any],
) -> None:
    """Test the `search` method."""

    with patch.object(
        drive.google_client,
        "get_items",
    ) as mock_get_items:
        mock_get_items.return_value = []

        results = drive.search(
            term,
            entity_type=entity_type,
            max_results=max_results,
            exact_match=exact_match,
            created_range=created_range,
        )

    assert results == []

    mock_get_items.assert_called_once_with(
        "/files",
        list_key="files",
        params=expected_params,
    )


def test_search_invalid_entity_type(drive: Drive) -> None:
    """Test the `search` method with an invalid entity type."""

    with raises(
        ValueError,
        match="`entity_type` must be either EntityType.FILE or EntityType.DIRECTORY,"
        " or None to search for both",
    ):
        drive.search("test", entity_type="invalid type")  # type: ignore[arg-type]


def test_all_known_descendents(
    drive: Drive, file: File, simple_file: File, directory: Directory
) -> None:
    """Test the `all_known_descendents` method."""

    assert not isinstance(drive._all_files, list)
    assert not isinstance(drive._all_directories, list)

    assert drive.all_known_descendents == []
    assert drive._all_files == []
    assert drive._all_directories == []

    drive._all_files = [file, simple_file]
    drive._all_directories = [directory]

    assert drive.all_known_descendents == [file, simple_file, directory]


def test_all_directories(drive: Drive) -> None:
    """Test the `all_directories` method."""

    assert drive._directories_mapped is not True

    mock_map = Mock(wraps=drive.map)
    object.__setattr__(drive, "map", mock_map)

    assert all(isinstance(d, Directory) for d in drive.all_directories)
    assert isinstance(drive._all_directories, list)
    assert drive._directories_mapped is True

    mock_map.assert_called_once_with(map_type=EntityType.DIRECTORY)


def test_all_files(drive: Drive) -> None:
    """Test the `all_files` method."""

    drive.google_client.item_metadata_retrieval = ItemMetadataRetrieval.ON_DEMAND

    assert drive._files_mapped is not True

    mock_map = Mock(wraps=drive.map)
    object.__setattr__(drive, "map", mock_map)

    assert all(isinstance(f, File) for f in drive.all_files)
    assert isinstance(drive.all_files, list)
    assert drive._files_mapped is True

    mock_map.assert_called_once_with()
