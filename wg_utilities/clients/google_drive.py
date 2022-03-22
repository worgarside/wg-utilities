"""Custom client for interacting with Google's Drive API"""

from copy import deepcopy

from wg_utilities.clients._generic import GoogleClient


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
    def __init__(self, id, name, parents=None, google_client=None, **_):
        self.file_id = id
        self.name = name
        self.parent_id = parents.pop() if parents else None
        self.google_client = google_client

        self._description = None
        self._parent = None

    def describe(self, force_update=False):
        """Describe the file by requesting all available fields from the Drive API

        Args:
            force_update (bool): re-pull the description from Google Drive, even if we
             already have the description locally

        Returns:
            dict: the description JSON for this file
        """
        if force_update or self._description is None:
            self._description = self.google_client.session.get(
                f"{self.google_client.BASE_URL}/files/{self.file_id}",
                params={"fields": ", ".join(self.DESCRIPTION_FIELDS)},
            ).json()

        return self._description

    @property
    def parent(self):
        """
        Returns:
            Directory: the parent directory of this file
        """
        if not self._parent:
            self._parent = self.google_client.get_directory_by(
                "file_id", self.parent_id
            )

        return self._parent

    @property
    def path(self):
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

    def __gt__(self, other):
        return self.name.lower() > other.name.lower()

    def __lt__(self, other):
        return self.name.lower() < other.name.lower()

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class Directory(File):
    """A Google Drive directory - basically a File with extended functionality

    Attributes:
        children (set): the directories contained within this directory
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.children = set()
        self._files = None

    @property
    def files(self):
        """
        Returns:
            list: the list of files contained within this directory
        """
        if not self._files:
            self._files = [
                File(**directory, google_client=self.google_client)
                for directory in self.google_client.get_items(
                    f"{self.google_client.BASE_URL}/files",
                    "files",
                    params=dict(
                        pageSize="1000",
                        q="mimeType != 'application/vnd.google-apps.folder' and"
                        f" '{self.file_id}' in parents",
                        fields="nextPageToken, files(id, name, parents)",
                    ),
                )
            ]

        return self._files

    @property
    def parent(self):
        """
        Returns:
            Directory: the parent directory of this directory
        """
        return self._parent

    @parent.setter
    def parent(self, value):
        self._parent = value

    @property
    def tree(self):
        """A simple copy of the Linux `tree` command, this builds a directory tree in
        text form for quick visualisation

        Returns:
            str: the full directory tree in text form
        """

        def build_sub_tree(parent_dir, level, block_pipes_at_levels=None):
            """Builds a subtree of a given directory

            Args:
                parent_dir (Directory): the directory to create the subtree of
                level (int): the depth level of this directory
                block_pipes_at_levels (list): a list of levels to block further pipes at
            """

            nonlocal output

            # Creating a deep copy means that when we go back up from the recursion,
            # the previous iteration still has the correct levels in the list
            block_pipes_at_levels = deepcopy(block_pipes_at_levels) or []

            for i, child_dir in enumerate(sorted(parent_dir.children)):
                prefix = "\n"

                # build out the spaces and pipes on this line, in such a way to
                # maintain continuity from the previous line
                for j in range(level):
                    prefix += " " if j in block_pipes_at_levels else "│"
                    prefix += "    "

                # if this is the last child
                if i + 1 == len(parent_dir.children):
                    prefix += "└"
                    block_pipes_at_levels.append(level)
                else:
                    prefix += "├"

                prefix += "─── "
                output += prefix + child_dir.name

                build_sub_tree(child_dir, level + 1, block_pipes_at_levels)

        output = self.name
        build_sub_tree(self, 0)

        return output

    def __str__(self):
        return self.name


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._root_directory = None

        self._directories = None

    def _build_directory_structure(self):
        """Build the complete tree of directories, including parent-child relationships
        by listing all directories and then iterating through them to build the
        relationships
        """
        self._directories = [self.root_directory]

        # List every single directory
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
        for directory in self._directories:
            if parent_dir := self.get_directory_by("file_id", directory.parent_id):
                directory.parent = parent_dir
                parent_dir.children.add(directory)

    def get_directory_by(self, attribute, value):
        """Get a Directory instance by any attribute

        Args:
            attribute (str): the name of the attribute to search for
            value (Any): the target value of the attribute

        Returns:
            Directory: the directory being searched for, if it was found
        """
        for directory in self.directories:
            if getattr(directory, attribute) == value:
                return directory

        return None

    def get_file_from_id(self, file_id, params=None):
        """Find a file by its UUID

        Args:
            file_id (str): the unique ID of the file
            params (dict): ny params to pass in the request

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
    def shared_drives(self):
        """
        Returns:
            list: a list of Shared Drives the current user has access to
        """
        return self.get_items(f"{self.BASE_URL}/drives", "drives")

    @property
    def directories(self):
        """
        Returns:
            list: a list of all directories in the user's Drive
        """
        if not self._directories:
            self._build_directory_structure()

        return self._directories

    @property
    def root_directory(self):
        """
        Returns:
            Directory: the user's root directory/main Drive
        """
        if not self._root_directory:
            self._root_directory = Directory(
                **self.session.get(f"{self.BASE_URL}/files/root").json(),
                google_client=self,
            )
            if not self._directories:
                self._build_directory_structure()

        return self._root_directory
