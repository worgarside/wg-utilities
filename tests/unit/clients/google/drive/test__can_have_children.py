# pylint: disable=protected-access
"""Unit tests for `wg_utilities.clients.google_drive._CanHaveChildren`."""
from __future__ import annotations

from textwrap import dedent
from unittest.mock import call, patch
from urllib.parse import urlencode

from pydantic.fields import FieldInfo
from pytest import mark, raises
from requests_mock import Mocker

from conftest import FLAT_FILES_DIR, assert_mock_requests_request_history
from wg_utilities.clients.google_drive import (
    Directory,
    Drive,
    File,
    GoogleDriveClient,
    ItemMetadataRetrieval,
    _CanHaveChildren,
    _GoogleDriveEntity,
)
from wg_utilities.clients.oauth_client import GenericModelWithConfig


def test_add_directory_method_first_call(directory: Directory) -> None:
    """Test the first call of `_add_directory` instantiates `_directories`."""

    assert isinstance(directory._directories, FieldInfo)

    new_dir = directory.copy(update={"name": "new_dir", "id": "new_dir_id"})

    with patch.object(
        GenericModelWithConfig, "_set_private_attr", wraps=directory._set_private_attr
    ) as mock_set_private_attr:
        directory._add_directory(new_dir)

    mock_set_private_attr.assert_called_once_with("_directories", [new_dir])

    assert directory._directories == [new_dir]


def test_add_directory_method_second_call(directory: Directory) -> None:
    """Test that a second call of `_add_directory` only appends to `_directories`."""

    assert isinstance(directory._directories, FieldInfo)

    new_dir = directory.copy(update={"name": "new_dir", "id": "new_dir_id"})
    new_dir_2 = directory.copy(update={"name": "new_dir_2", "id": "new_dir_2_id"})

    with patch.object(
        GenericModelWithConfig, "_set_private_attr", wraps=directory._set_private_attr
    ) as mock_set_private_attr:
        directory._add_directory(new_dir)
        mock_set_private_attr.assert_called_once_with("_directories", [new_dir])
        mock_set_private_attr.reset_mock()
        directory._add_directory(new_dir_2)
        mock_set_private_attr.assert_not_called()

    assert directory._directories == [new_dir, new_dir_2]


def test_add_directory_ignores_known_directory(directory: Directory) -> None:
    """Test that if a known directory is added, it is ignored."""

    assert isinstance(directory._directories, FieldInfo)

    new_dir = directory.copy(update={"name": "new_dir", "id": "new_dir_id"})

    with patch.object(
        GenericModelWithConfig, "_set_private_attr", wraps=directory._set_private_attr
    ) as mock_set_private_attr:
        directory._add_directory(new_dir)
        mock_set_private_attr.assert_called_once_with("_directories", [new_dir])
        mock_set_private_attr.reset_mock()
        directory._add_directory(new_dir)
        mock_set_private_attr.assert_not_called()

    assert directory._directories == [new_dir]


def test_add_directory_raises_type_error_for_wrong_type(
    directory: Directory, file: File
) -> None:
    """Test that `_add_directory` raises a `TypeError` if the wrong type is passed."""

    with patch.object(
        GenericModelWithConfig, "_set_private_attr", wraps=directory._set_private_attr
    ) as mock_set_private_attr, raises(TypeError) as exc_info:
        directory._add_directory(file)  # type: ignore[arg-type]

    mock_set_private_attr.assert_not_called()
    assert str(exc_info.value) == "Cannot add `File` instance to `self.directories`."


def test_add_file_method_first_call(directory: Directory, file: File) -> None:
    """Test the first call of `_add_file` instantiates `_files`."""

    assert isinstance(directory._files, FieldInfo)

    with patch.object(
        GenericModelWithConfig, "_set_private_attr", wraps=directory._set_private_attr
    ) as mock_set_private_attr:
        directory._add_file(file)

    mock_set_private_attr.assert_called_once_with("_files", [file])

    assert directory._files == [file]


def test_add_file_method_second_call(directory: Directory, file: File) -> None:
    """Test that a second call of `_add_file` only appends to `_files`."""

    assert isinstance(directory._files, FieldInfo)

    new_file = file.copy(update={"name": "new_file", "id": "new_file_id"})

    with patch.object(
        GenericModelWithConfig, "_set_private_attr", wraps=directory._set_private_attr
    ) as mock_set_private_attr:
        directory._add_file(file)
        mock_set_private_attr.assert_called_once_with("_files", [file])
        mock_set_private_attr.reset_mock()
        directory._add_file(new_file)
        mock_set_private_attr.assert_not_called()

    assert directory._files == [file, new_file]


def test_add_file_ignores_known_file(directory: Directory, file: File) -> None:
    """Test that if a known directory is added, it is ignored."""

    assert isinstance(directory._files, FieldInfo)

    with patch.object(
        GenericModelWithConfig, "_set_private_attr", wraps=directory._set_private_attr
    ) as mock_set_private_attr:
        directory._add_file(file)
        mock_set_private_attr.assert_called_once_with("_files", [file])
        mock_set_private_attr.reset_mock()
        directory._add_file(file)
        mock_set_private_attr.assert_not_called()

    assert directory._files == [file]


def test_add_file_raises_type_error_for_wrong_type(directory: Directory) -> None:
    """Test that `_add_file` raises a `TypeError` if the wrong type is passed."""

    with patch.object(
        GenericModelWithConfig, "_set_private_attr", wraps=directory._set_private_attr
    ) as mock_set_private_attr, raises(TypeError) as exc_info:
        directory._add_file(directory)

    mock_set_private_attr.assert_not_called()
    assert str(exc_info.value) == "Cannot add `Directory` instance to `self.files`."


def test_add_child_method_file(
    drive: Drive,
    file: File,
) -> None:
    """Test that `add_child` adds a File to the correct attribute."""

    with patch.object(
        _CanHaveChildren, "_add_directory", wraps=drive._add_directory
    ) as mock_add_directory, patch.object(
        _CanHaveChildren, "_add_file", wraps=drive._add_file
    ) as mock_add_file:
        drive.add_child(file)
        mock_add_directory.assert_not_called()
        mock_add_file.assert_called_once_with(file)


def test_add_child_method_directory(drive: Drive, directory: Directory) -> None:
    """Test that `add_child` adds a Directory to the correct attribute."""

    with patch.object(
        _CanHaveChildren, "_add_directory", wraps=drive._add_directory
    ) as mock_add_directory, patch.object(
        _CanHaveChildren, "_add_file", wraps=drive._add_file
    ) as mock_add_file:
        drive.add_child(directory)
        mock_add_directory.assert_called_once_with(directory)
        mock_add_file.assert_not_called()


def test_add_child_invalid_type(drive: Drive) -> None:
    """Test that `add_child` raises a `TypeError` if the wrong type is passed."""

    with raises(TypeError) as exc_info:
        drive.add_child("not a file or directory")  # type: ignore[arg-type]

    assert str(exc_info.value) == "Cannot add `str` instance to My Drive's children."


@mark.parametrize(  # type: ignore[misc]
    ("navigate_path", "instance_path"),
    (
        # pylint: disable=line-too-long
        (
            ".",
            "/My Drive/Archives",
        ),
        (
            "./MacBook Clones",
            "/My Drive/Archives/MacBook Clones",
        ),
        (
            "..",
            "/My Drive",
        ),
        (
            "../",
            "/My Drive",
        ),
        (
            "/",
            "/My Drive",
        ),
        (
            "MacBook Clones",
            "/My Drive/Archives/MacBook Clones",
        ),
        (
            "MacBook Clones/..",
            "/My Drive/Archives",
        ),
        (
            "./MacBook Clones/../..",
            "/My Drive",
        ),
        (
            "./MacBook Clones/../../Archives",
            "/My Drive/Archives",
        ),
        (
            "MacBook Clones/../../Archives/MacBook Clones",
            "/My Drive/Archives/MacBook Clones",
        ),
        (
            "MacBook Clones/../../Archives/MacBook Clones/128GB SD Card - Old MacBook.zip",
            "/My Drive/Archives/MacBook Clones/128GB SD Card - Old MacBook.zip",
        ),
        (
            "../Archives/./MacBook Clones/../../Archives/MacBook Clones/./128GB SD Card - Old MacBook.zip",
            "/My Drive/Archives/MacBook Clones/128GB SD Card - Old MacBook.zip",
        ),
        (
            "~/Archives/./MacBook Clones/../../Archives/MacBook Clones",
            "/My Drive/Archives/MacBook Clones",
        ),
        (
            "~/Archives/./MacBook Clones/../../Archives/MacBook Clones/../MacBook Clones/Photos Library.zip",
            "/My Drive/Archives/MacBook Clones/Photos Library.zip",
        ),
        (
            "/My Drive/Archives",
            "/My Drive/Archives",
        ),
        (
            "/My Drive/Archives/Archive Log",
            "/My Drive/Archives/Archive Log",
        ),
        (
            "/My Drive/Archives/Old Documents",
            "/My Drive/Archives/Old Documents",
        ),
        (
            "/My Drive/Archives/Old Documents/Harvard Transcripts.zip",
            "/My Drive/Archives/Old Documents/Harvard Transcripts.zip",
        ),
        (
            "~/Archives/Old Documents/Harvard Transcripts.zip",
            "/My Drive/Archives/Old Documents/Harvard Transcripts.zip",
        ),
        (
            "~/Archives/Old Documents/School Reports.zip",
            "/My Drive/Archives/Old Documents/School Reports.zip",
        ),
    ),
)
def test_navigate_method(
    directory: Directory,
    navigate_path: str,
    instance_path: str,
    drive_comparison_entity_lookup: dict[str, File | Directory | Drive],
) -> None:
    """Test that the `navigate` method behaves as expected.

    The starting point of this test is the `Archives` directory, and the below is the
    relevant parts of the file tree:

    My Drive
    └─── Archives
         ├──> Archive Log
         ├─── Old Documents
         │    ├──> Harvard Transcripts.zip
         │    └──> School Reports.zip
         └─── MacBook Clones
              ├──> 128GB SD Card - Old MacBook.zip
              └──> Photos Library.zip
    """

    expected = drive_comparison_entity_lookup[instance_path.split("/")[-1]]

    actual = directory.navigate(navigate_path)

    assert actual.path == instance_path
    assert actual == expected


@mark.parametrize(  # type: ignore[misc]
    ("navigate_path", "exception_message"),
    (
        (
            "MacBook Clones//128GB SD Card - Old MacBook.zip",
            "Path cannot contain `//`.",
        ),
        ("../../../..", "Cannot navigate to parent of Drive."),
        ("/..", "Cannot navigate to Drive '..' from `My Drive`."),
        ("/Another Drive", "Cannot navigate to Drive 'Another Drive' from `My Drive`."),
    ),
)
def test_navigate_method_raises_value_error_for_invalid_path(
    directory: Directory, navigate_path: str, exception_message: str
) -> None:
    """Test that `navigate` raises a `ValueError` if an invalid path is passed."""

    with raises(ValueError) as exc_info:
        directory.navigate(navigate_path)

    assert str(exc_info.value) == exception_message


def test_navigate_method_no_results_found(
    directory: Directory, mock_requests: Mocker
) -> None:
    """Test that a zero-result response is handled correctly."""

    mock_requests.get(
        # pylint: disable=line-too-long
        "https://www.googleapis.com/drive/v3/files?pagesize=1&fields=files(*)&q='7tqryz0a9oyjfzf1cpbmllsblj-ohbi1e'+in+parents+and+name+=+'path'",
        json={"files": []},
    )

    with raises(ValueError, match="^Invalid path: 'path/to/nowhere.jpg'$"):
        directory.navigate("path/to/nowhere.jpg")


def test_reset_known_children(directory: Directory) -> None:
    """Test that `reset_known_children` resets the `known_children` attribute."""

    with patch.object(_CanHaveChildren, "_set_private_attr") as mock_set_private_attr:
        directory.reset_known_children()

    assert mock_set_private_attr.call_args_list == [
        call("_directories", None),
        call("_directories_loaded", False),
        call("_files", None),
        call("_files_loaded", False),
    ]


@mark.parametrize(  # type: ignore[misc]
    (
        "include_files",
        "archive_files_only_tree",
        "archive_directories_tree",
        "complete_tree",
    ),
    (
        (
            True,
            "My Drive\n└─── Archives\n     └──> Archive Log",
            dedent(
                """
                My Drive
                └─── Archives
                     ├──> Archive Log
                     ├─── MacBook Clones
                     └─── Old Documents
                """
            ).strip(),
            dedent(
                """
                My Drive
                └─── Archives
                     ├──> Archive Log
                     ├─── MacBook Clones
                     │    ├──> 128GB SD Card - Old MacBook.zip
                     │    └──> Photos Library.zip
                     └─── Old Documents
                          ├──> Harvard Transcripts.zip
                          └──> School Reports.zip
                """
            ).strip(),
        ),
        (
            False,
            "My Drive\n└─── Archives",
            dedent(
                """
                My Drive
                └─── Archives
                     ├─── MacBook Clones
                     └─── Old Documents
                """
            ).strip(),
            dedent(
                """
                My Drive
                └─── Archives
                     ├─── MacBook Clones
                     └─── Old Documents
                """
            ).strip(),
        ),
    ),
)
def test_tree_method_local_only(
    drive: Drive,
    include_files: bool,
    archive_files_only_tree: str,
    archive_directories_tree: str,
    complete_tree: str,
) -> None:
    """Test that the `tree` method behaves as expected when `local_only` is `True`."""

    # Populate local children variables
    archives = drive.navigate("Archives")

    _ = archives.files

    assert (
        drive.tree(include_files=include_files, local_only=True)
        == archive_files_only_tree
    )

    directories = archives.directories
    assert (
        drive.tree(include_files=include_files, local_only=True)
        == archive_directories_tree
    )

    for d in directories:
        _ = d.files

    assert drive.tree(include_files=include_files, local_only=True) == complete_tree


def test_tree_not_local_only(drive: Drive) -> None:
    """Test that the `tree` method behaves as expected when `local_only` is `False`."""

    drive.google_client.item_metadata_retrieval = ItemMetadataRetrieval.ON_DEMAND

    expected = (FLAT_FILES_DIR / "text/google_drive_tree.txt").read_text().strip()

    assert drive.tree(include_files=True, local_only=False) == expected


@mark.parametrize(  # type: ignore[misc]
    ("preload_paths", "expected"),
    (
        (
            [],
            [],
        ),
        (
            ["MacBook Clones"],
            ["MacBook Clones"],
        ),
        (
            ["MacBook Clones", "Old Documents/Harvard Transcripts.zip"],
            ["MacBook Clones", "Old Documents"],
        ),
        (
            ["MacBook Clones", "Old Documents/Harvard Transcripts.zip", "Archive Log"],
            ["Archive Log", "MacBook Clones", "Old Documents"],
        ),
        (
            ["Archive Log"],
            ["Archive Log"],
        ),
        (
            ["Old Documents/Harvard Transcripts.zip"],
            ["Old Documents"],
        ),
    ),
)
def test_all_known_children_property(
    directory: Directory,
    drive_comparison_entity_lookup: dict[str, _GoogleDriveEntity],
    preload_paths: list[str],
    expected: list[str],
) -> None:
    """Test that the `all_known_children` property behaves as expected."""

    for path in preload_paths:
        directory.navigate(path)

    assert directory.all_known_children == [
        drive_comparison_entity_lookup[entity_name] for entity_name in expected
    ]
    assert isinstance(directory._files, list)
    assert isinstance(directory._directories, list)


def test_children_property(
    directory: Directory, drive_comparison_entity_lookup: dict[str, _GoogleDriveEntity]
) -> None:
    """Test that the `children` property behaves as expected."""

    with patch.object(
        _CanHaveChildren, "reset_known_children"
    ) as mock_reset_known_children, patch.object(
        _CanHaveChildren,
        "files",
        [
            drive_comparison_entity_lookup["128GB SD Card - Old MacBook.zip"],
            drive_comparison_entity_lookup["Archive Log"],
        ],
    ), patch.object(
        _CanHaveChildren,
        "directories",
        [drive_comparison_entity_lookup["MacBook Clones"]],
    ):
        assert directory.children == [
            drive_comparison_entity_lookup["128GB SD Card - Old MacBook.zip"],
            drive_comparison_entity_lookup["Archive Log"],
            drive_comparison_entity_lookup["MacBook Clones"],
        ]

        mock_reset_known_children.assert_called_once()


def test_directories(
    directory: Directory,
    mock_requests: Mocker,
    live_jwt_token: str,
    drive_comparison_entity_lookup: dict[str, Directory],
    google_drive_client: GoogleDriveClient,
) -> None:
    """Test that the `directories` property behaves as expected."""

    assert directory._directories_loaded is not True

    with patch.object(
        directory.google_client, "get_items", wraps=google_drive_client.get_items
    ) as mock_get_items:
        assert directory.directories == [
            drive_comparison_entity_lookup["MacBook Clones"],
            drive_comparison_entity_lookup["Old Documents"],
        ]
        assert directory._directories_loaded is True
        assert directory.directories == [
            drive_comparison_entity_lookup["MacBook Clones"],
            drive_comparison_entity_lookup["Old Documents"],
        ]

    params = {
        "pageSize": 1000,
        "q": "mimeType = 'application/vnd.google-apps.folder' and "
        "'7tqryz0A9oYJfzF1cpBMLLsblJ-oHBi1e' in parents",
        "fields": "nextPageToken, files(*)",
    }

    mock_get_items.assert_called_once_with(
        "/files",
        list_key="files",
        params=params,
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"https://www.googleapis.com/drive/v3/files?{urlencode(params)}",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            }
        ],
    )


def test_files(
    directory: Directory,
    mock_requests: Mocker,
    live_jwt_token: str,
    drive_comparison_entity_lookup: dict[str, Directory],
    google_drive_client: GoogleDriveClient,
) -> None:
    """Test that the `files` property behaves as expected."""

    assert directory._files_loaded is not True

    with patch.object(
        directory.google_client, "get_items", wraps=google_drive_client.get_items
    ) as mock_get_items:
        assert directory.files == [
            drive_comparison_entity_lookup["Archive Log"],
        ]
        assert directory._files_loaded is True
        assert directory.files == [
            drive_comparison_entity_lookup["Archive Log"],
        ]

    params = {
        "pageSize": 1000,
        "q": "mimeType != 'application/vnd.google-apps.folder' and "
        "'7tqryz0A9oYJfzF1cpBMLLsblJ-oHBi1e' in parents",
        "fields": "nextPageToken, files(*)",
    }

    mock_get_items.assert_called_once_with(
        "/files",
        list_key="files",
        params=params,
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"https://www.googleapis.com/drive/v3/files?{urlencode(params)}",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            }
        ],
    )
