"""Custom client for interacting with Google's Drive API"""
from __future__ import annotations

from copy import deepcopy
from logging import Logger
from typing import Any, Collection, Dict, Iterable, cast

from wg_utilities.clients._google import GoogleClient
from wg_utilities.exceptions import ResourceNotFound


class File:
    """A file object within Google Drive

    Args:
        id (str): the unique ID of this file
        name (str): the name of the file
        parents (list): a list of parent directory IDs (should always be of length 1)
        google_client (GoogleDriveClient): a Google client for use in other requests

    Attributes:
        file_id (str): the unique ID of this file
        name (str): the name of the file
        parent_id (str): the unique ID of the parent directory
        google_client (GoogleDriveClient): a Google client for use in other requests

    """

    DESCRIPTION_FIELDS = [
        "appProperties",
        "capabilities",
        "contentHints",
        "contentRestrictions",
        "copyRequiresWriterPermission",
        "createdTime",
        "description",
        "driveId",
        "explicitlyTrashed",
        "exportLinks",
        "fileExtension",
        "folderColorRgb",
        "fullFileExtension",
        "hasAugmentedPermissions",
        "hasThumbnail",
        "headRevisionId",
        "iconLink",
        "id",
        "imageMediaMetadata",
        "isAppAuthorized",
        "kind",
        "lastModifyingUser",
        "linkShareMetadata",
        "md5Checksum",
        "mimeType",
        "modifiedByMe",
        "modifiedByMeTime",
        "modifiedTime",
        "name",
        "originalFilename",
        "ownedByMe",
        "owners",
        "parents",
        "permissionIds",
        "permissions",
        "properties",
        "quotaBytesUsed",
        "resourceKey",
        "shared",
        "sharedWithMeTime",
        "sharingUser",
        "shortcutDetails",
        "size",
        "spaces",
        "starred",
        "teamDriveId",
        "thumbnailLink",
        "thumbnailVersion",
        "trashed",
        "trashedTime",
        "trashingUser",
        "version",
        "videoMediaMetadata",
        "viewedByMe",
        "viewedByMeTime",
        "viewersCanCopyContent",
        "webContentLink",
        "webViewLink",
        "writersCanShare",
    ]

    # noinspection PyShadowingBuiltins
    # pylint: disable=redefined-builtin
    def __init__(
        self,
        *,
        id: str,
        name: str,
        google_client: GoogleDriveClient,
        parents: list[str] | None = None,
        **_: Any,
    ):
        self.file_id = id
        self.name = name
        self.parent_id = parents.pop() if parents else None
        self.google_client = google_client

        self._description: dict[str, str | bool | float | int]
        self._parent: Directory

    def describe(
        self, force_update: bool = False
    ) -> dict[str, str | bool | float | int]:
        """Describe the file by requesting all available fields from the Drive API

        Args:
            force_update (bool): re-pull the description from Google Drive, even if we
             already have the description locally

        Returns:
            dict: the description JSON for this file
        """
        if force_update or not hasattr(self, "_description"):
            self._description = self.google_client.session.get(
                f"{self.google_client.BASE_URL}/files/{self.file_id}",
                params={"fields": ", ".join(self.DESCRIPTION_FIELDS)},
            ).json()

        return self._description

    @property
    def parent(self) -> Directory:
        """
        Returns:
            Directory: the parent directory of this file
        """
        if not hasattr(self, "_parent"):
            self._parent = self.google_client.get_directory_by(
                "file_id", self.parent_id
            )

        return self._parent

    @property
    def path(self) -> str:
        """
        Returns:
            str: the path to this file in Google Drive
        """
        current_path = self.name

        parent_dir = self.parent
        while True:
            current_path = "/".join([parent_dir.name, current_path])

            if not (next_parent := parent_dir.parent):
                break

            parent_dir = next_parent

        return "/" + current_path

    def __gt__(self, other: File) -> bool:
        return self.name.lower() > other.name.lower()

    def __lt__(self, other: File) -> bool:
        return self.name.lower() < other.name.lower()

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name


class Directory(File):
    """A Google Drive directory - basically a File with extended functionality

    Attributes:
        children (set): the directories contained within this directory
    """

    # noinspection PyShadowingBuiltins
    # pylint: disable=redefined-builtin
    def __init__(
        self,
        *,
        id: str,
        name: str,
        google_client: GoogleDriveClient,
        parents: list[str] | None = None,
        **_: Any,
    ):
        super().__init__(id=id, name=name, parents=parents, google_client=google_client)
        self.children: set[Directory] = set()
        self._files: list[File] | None = None

    @property
    def files(self) -> list[File]:
        """
        Returns:
            list: the list of files contained within this directory
        """
        if not self._files:
            self._files = [
                File(**item, google_client=self.google_client)  # type: ignore[arg-type]
                # TODO make this just pass in the JSON like everything else...
                for item in cast(
                    Iterable[Dict[str, str]],
                    self.google_client.get_items(
                        f"{self.google_client.BASE_URL}/files",
                        "files",
                        params={
                            "pageSize": "1000",
                            "q": "mimeType != 'application/vnd.google-apps.folder' and"
                            f" '{self.file_id}' in parents",
                            "fields": "nextPageToken, files(id, name, parents)",
                        },
                    ),
                )
            ]

        return list(self._files)

    @property
    def parent(self) -> Directory:
        """
        Returns:
            Directory: the parent directory of this directory
        """
        return self._parent

    @parent.setter
    def parent(self, value: Directory) -> None:
        self._parent = value

    @property
    def tree(self) -> str:
        """A simple copy of the Linux `tree` command, this builds a directory tree in
        text form for quick visualisation

        Returns:
            str: the full directory tree in text form
        """

        output = self.name

        def build_sub_tree(
            parent_dir: Directory,
            level: int,
            block_pipes_at_levels: list[int] | None = None,
            show_files: bool = True,
        ) -> None:
            """Builds a subtree of a given directory

            Args:
                parent_dir (Directory): the directory to create the subtree of
                level (int): the depth level of this directory
                block_pipes_at_levels (list): a list of levels to block further pipes at
                show_files (bool): flag to load files too - this could take
                 considerably longer to load (proportional to the number of files you've
                 got)
            """

            nonlocal output

            # Creating a deep copy means that when we go back up from the recursion,
            # the previous iteration still has the correct levels in the list
            block_pipes_at_levels = deepcopy(block_pipes_at_levels) or []

            item_list: Collection[File] = parent_dir.children

            if not item_list and show_files:
                item_list = parent_dir.files

            for i, child_item in enumerate(sorted(item_list)):
                prefix = "\n"

                # build out the spaces and pipes on this line, in such a way to
                # maintain continuity from the previous line
                for j in range(level):
                    prefix += " " if j in block_pipes_at_levels else "│"
                    prefix += "    "

                # if this is the last child
                if i + 1 == len(item_list):
                    prefix += "└"
                    block_pipes_at_levels.append(level)
                else:
                    prefix += "├"

                if isinstance(child_item, Directory):
                    prefix += "─── "
                else:
                    prefix += "--> "

                output += prefix + child_item.name

                if isinstance(child_item, Directory):
                    build_sub_tree(child_item, level + 1, block_pipes_at_levels)

        build_sub_tree(self, 0)

        return output


class GoogleDriveClient(GoogleClient):
    """Custom client specifically for Google's Drive API

    Args:
        project (str): the name of the project which this client is being used for
        scopes (list): a list of scopes the client can be given
        client_id_json_path (str): the path to the `client_id.json` file downloaded
         from Google's API Console
        creds_cache_path (str): file path for where to cache credentials
        access_token_expiry_threshold (int): the threshold for when the access token is
         considered expired
        logger (RootLogger): a logger to use throughout the client functions

    """

    BASE_URL = "https://www.googleapis.com/drive/v3"

    def __init__(
        self,
        project: str,
        scopes: list[str] | None = None,
        client_id_json_path: str | None = None,
        creds_cache_path: str | None = None,
        access_token_expiry_threshold: int = 60,
        logger: Logger | None = None,
    ):
        super().__init__(
            project=project,
            scopes=scopes,
            client_id_json_path=client_id_json_path,
            creds_cache_path=creds_cache_path,
            access_token_expiry_threshold=access_token_expiry_threshold,
            logger=logger,
        )
        self._root_directory: Directory

        self._directories: list[Directory]

    def _build_directory_structure(self) -> None:
        """Build the complete tree of directories, including parent-child relationships
        by listing all directories and then iterating through them to build the
        relationships
        """
        self._directories = [self.root_directory]

        # List every single directory
        directory: dict[str, str]
        for directory in self.get_items(
            f"{self.BASE_URL}/files",
            "files",
            params=dict(
                pageSize="1000",
                q="mimeType = 'application/vnd.google-apps.folder'",
                fields="nextPageToken, files(id, name, parents)",
            ),
        ):
            self._directories.append(Directory(**directory, google_client=self))

        # Iterate through the directories, adding their parents and children as
        # applicable
        for directory_ in self._directories:
            if parent_dir := self.get_directory_by("file_id", directory_.parent_id):
                directory_.parent = parent_dir
                parent_dir.children.add(directory_)

    def get_directory_by(self, attribute: str, value: Any) -> Directory:
        """Get a Directory instance by any attribute

        Args:
            attribute (str): the name of the attribute to search for
            value (Any): the target value of the attribute

        Returns:
            Directory: the directory being searched for, if it was found

        Raises:
            ResourceNotFound: if no matching directory exists
        """
        for directory in self.directories:
            if getattr(directory, attribute) == value:
                return directory

        raise ResourceNotFound(
            f"Unable to find directory where attribute {attribute!r} == {str(value)}"
        )

    def get_file_from_id(
        self,
        file_id: str,
        params: dict[str, str | int | float | bool] | None = None,
    ) -> File:
        """Find a file by its UUID

        Args:
            file_id (str): the unique ID of the file
            params (dict): any params to pass in the request

        Returns:
            File: the target file, if found
        """

        if not self._directories:
            self._build_directory_structure()

        params = params or {}

        if "fields" not in params:
            params["fields"] = "id, name, parents"

        return File(
            **self.session.get(
                f"{self.BASE_URL}/files/{file_id}", params=params
            ).json(),
            google_client=self,
        )

    @property
    def shared_drives(self) -> list[dict[str, str]]:
        """
        Returns:
            list: a list of Shared Drives the current user has access to
        """
        # pylint: disable=line-too-long
        return self.get_items(f"{self.BASE_URL}/drives", "drives")  # type: ignore[return-value]

    @property
    def directories(self) -> list[Directory]:
        """
        Returns:
            list: a list of all directories in the user's Drive
        """
        if not self._directories:
            self._build_directory_structure()

        return self._directories

    @property
    def root_directory(self) -> Directory:
        """
        Returns:
            Directory: the user's root directory/main Drive
        """
        if not hasattr(self, "_root_directory"):
            res = self.session.get(f"{self.BASE_URL}/files/root")
            res.raise_for_status()
            self._root_directory = Directory(
                **res.json(),
                google_client=self,
            )
            if not self._directories:
                self._build_directory_structure()

        return self._root_directory
