# pylint: disable=too-few-public-methods,too-many-lines,no-self-argument
"""Custom client for interacting with Google's Drive API."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Set
from copy import deepcopy
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from re import sub
from typing import Any, ClassVar, Literal, TypeVar

from pydantic import Field, validator

from wg_utilities.clients._google import GoogleClient
from wg_utilities.clients.oauth_client import (
    BaseModelWithConfig,
    GenericModelWithConfig,
)
from wg_utilities.functions.json import JSONObj


class EntityKind(str, Enum):
    """Enum for the different kinds of entities that can be returned by the API."""

    COMMENT = "drive#comment"
    COMMENT_REPLY = "drive#commentReply"
    CHANGE = "drive#change"
    CHANNEL = "drive#channel"
    DIRECTORY = "drive#folder"
    DRIVE = "drive#drive"
    FILE = "drive#file"
    FILE_LIST = "drive#fileList"
    LABEL = "drive#label"
    PERMISSION = "drive#permission"
    REPLY = "drive#reply"
    REVISION = "drive#revision"
    TEAM_DRIVE = "drive#teamDrive"
    TEAM_DRIVE_LIST = "drive#teamDriveList"
    USER = "drive#user"


class EntityType(str, Enum):
    """Enum for the different entity types contained within a Drive."""

    DIRECTORY = "directory"
    FILE = "file"


class _ImageMediaMetadata(BaseModelWithConfig):
    width: int
    height: int
    rotation: int | None
    location: dict[str, float] = {}
    time: str | None
    camera_make: str | None = Field(alias="cameraMake")
    camera_model: str | None = Field(alias="cameraModel")
    exposure_time: float | None = Field(alias="exposureTime")
    aperture: float | None
    flash_used: bool | None = Field(alias="flashUsed")
    focal_length: float | None = Field(alias="focalLength")
    iso_speed: int | None = Field(alias="isoSpeed")
    metering_mode: str | None = Field(alias="meteringMode")
    sensor: str | None
    exposure_mode: str | None = Field(alias="exposureMode")
    color_space: str | None = Field(alias="colorSpace")
    white_balance: str | None = Field(alias="whiteBalance")
    exposure_bias: float | None = Field(alias="exposureBias")
    max_aperture_value: float | None = Field(alias="maxApertureValue")
    subject_distance: int | None = Field(alias="subjectDistance")
    lens: str | None


class _Label(BaseModelWithConfig):
    kind: EntityKind = Field(alias="kind", const=True, default=EntityKind.LABEL)
    id: str
    revision_id: str = Field(alias="revisionId")
    fields: dict[str, _LabelField]


class _LabelField(BaseModelWithConfig):
    kind: EntityKind = Field(alias="kind", const=True, default=EntityKind.USER)
    id: str
    value_type: str = Field(alias="valueType")
    date_str: list[date] = Field(alias="datestr", default_factory=list)
    integer: list[float]
    selection: list[str]
    text: list[str]
    user: list[_User]


class _PermissionDetails(BaseModelWithConfig):
    permission_type: str = Field(alias="permissionType")
    role: str
    inherited_from: str = Field(alias="inheritedFrom")
    inherited: bool


class _Permission(BaseModelWithConfig):
    kind: EntityKind = Field(alias="kind", const=True, default=EntityKind.PERMISSION)
    id: str
    type: str
    email_address: str | None = Field(alias="emailAddress")
    domain: str | None
    role: str
    view: str | None
    allow_file_discovery: bool | None = Field(alias="allowFileDiscovery")
    display_name: str | None = Field(alias="displayName")
    photo_link: str | None = Field(alias="photoLink")
    expiration_time: datetime | None = Field(alias="expirationTime")
    permission_details: _PermissionDetails | None = Field(alias="permissionDetails")
    deleted: bool | None
    pending_owner: bool | None = Field(alias="pendingOwner")


class _User(BaseModelWithConfig):
    kind: EntityKind = Field(alias="kind", const=True, default=EntityKind.USER)
    display_name: str = Field(alias="displayName")
    photo_link: str = Field(alias="photoLink")
    me: bool
    permission_id: str = Field(alias="permissionId")
    email_address: str = Field(alias="emailAddress")


class _VideoMediaMetadata(BaseModelWithConfig):
    width: int
    height: int
    duration_millis: float = Field(alias="durationMillis")


class _ContentHints(BaseModelWithConfig):
    indexable_text: str = Field(alias="indexableText")
    thumbnail: dict[str, bytes | str]


class _ContentRestriction(BaseModelWithConfig):
    read_only: bool = Field(alias="readOnly")
    reason: str
    restricting_user: _User = Field(alias="restrictingUser")
    restriction_time: datetime = Field(alias="restrictionTime")
    type: str


class _GoogleDriveEntity(GenericModelWithConfig):
    """Base class for Google Drive entities."""

    id: str
    name: str
    mime_type: str = Field(alias="mimeType")

    google_client: GoogleDriveClient = Field(exclude=True)

    @classmethod
    def from_json_response(
        cls: type[FJR],
        value: Mapping[str, Any],
        google_client: GoogleDriveClient,
        host_drive: Drive | None = None,
        parent: _CanHaveChildren | Drive | Directory | None = None,
        _block_describe_call: bool = False,
        _waive_validation: bool = False,
    ) -> FJR:
        """Create a new instance from a JSON response.

        Args:
            value (dict): The JSON response.
            google_client (GoogleDriveClient): The Google Drive client.
            host_drive (Drive): The Drive that this entity belongs to.
            parent (Directory, optional): The parent directory.

        Returns:
            _GoogleDriveEntity: The new instance.
        """

        value_data: dict[str, Any] = {
            "google_client": google_client,
            "parent_": parent,
            "host_drive_": host_drive,
            **value,
        }

        instance = cls.parse_obj(value_data)

        if not _waive_validation:
            instance._validate()  # pylint: disable=protected-access

        # pylint: disable=isinstance-second-argument-not-valid-type
        if isinstance(instance, File | Directory):
            if parent is not None:
                parent.add_child(instance)
            elif host_drive is not None and host_drive.id == instance.parents[0]:
                instance.parent_ = host_drive
                host_drive.add_child(instance)

        if (
            not _block_describe_call
            and google_client.item_metadata_retrieval == ItemMetadataRetrieval.ON_INIT
            and hasattr(instance, "describe")
        ):
            instance.describe()

        return instance

    def dict(
        self,
        *,
        include: Set[int | str] | Mapping[int | str, Any] | None = None,
        exclude: Set[int | str] | Mapping[int | str, Any] | None = None,
        by_alias: bool = True,
        skip_defaults: bool | None = None,
        exclude_unset: bool = True,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> dict[str, Any]:
        # pylint: disable=useless-parent-delegation
        """Override the standard `BaseModel.dict` method.

        Allows us to consistently return the dict with the same field names it came in
        with, and exclude any null values that have been added when parsing.

        Original documentation is here:
          - https://pydantic-docs.helpmanual.io/usage/exporting_models/#modeldict

        Overridden Parameters:
            by_alias: False -> True
            exclude_unset: False -> True
        """

        return super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

    def json(
        self,
        *,
        include: Set[int | str] | Mapping[int | str, Any] | None = None,
        exclude: Set[int | str] | Mapping[int | str, Any] | None = None,
        by_alias: bool = True,
        skip_defaults: bool | None = None,
        exclude_unset: bool = True,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        encoder: Callable[[Any], Any] | None = None,
        models_as_dict: bool = True,
        **dumps_kwargs: Any,
    ) -> str:
        # pylint: disable=useless-parent-delegation
        """Override the standard `BaseModel.json` method.

        Allows us to consistently return the dict with the same field names it came in
        with, and exclude any null values that have been added when parsing.

        Original documentation is here:
          - https://pydantic-docs.helpmanual.io/usage/exporting_models/#modeljson

        Overridden Parameters:
            by_alias: False -> True
            exclude_unset: False -> True
            encoder: None -> self._json_encoder
        """

        return super().json(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            encoder=encoder,
            models_as_dict=models_as_dict,
            **dumps_kwargs,
        )

    @property
    def host_drive(self) -> Drive:
        """The drive that this directory is hosted on.

        Returns:
            Drive: the drive that this directory is hosted on

        Raises:
            TypeError: if the entity is not hosted on a drive
        """

        if isinstance(self, Drive):
            return self

        # pylint: disable=isinstance-second-argument-not-valid-type
        if isinstance(self, File | Directory):
            return self.host_drive_

        raise TypeError(f"Cannot get host drive of {self.__class__.__name__}.")

    @property
    def path(self) -> str:
        """Path to this file, relative to the root directory.

        Returns:
            str: the path to this file in Google Drive
        """
        current_path = self.name
        parent_dir: _GoogleDriveEntity = self

        while hasattr(parent_dir, "parent") and (parent_dir := parent_dir.parent):
            current_path = "/".join([parent_dir.name, current_path])

        return "/" + current_path

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.id == other.id

    def __str__(self) -> str:
        """Return the file name."""
        return self.name


class _CanHaveChildren(_GoogleDriveEntity):
    """Mixin for entities that can have children."""

    _directories: list[Directory] = Field(exclude=True, default_factory=list)
    _files: list[File] = Field(exclude=True, default_factory=list)

    _files_loaded: bool = Field(exclude=True, default=False)
    _directories_loaded: bool = Field(exclude=True, default=False)

    def _add_directory(self, directory: Directory) -> None:
        """Add a child directory to this directory's children record.

        Args:
            directory (Directory): the directory to add

        Raises:
            ValueError: if the directory is already in the list
        """
        if not isinstance(directory, Directory):
            raise TypeError(
                f"Cannot add `{directory.__class__.__name__}` instance to "
                "`self.directories`."
            )

        if not isinstance(self._directories, list):
            self._set_private_attr("_directories", [directory])
        elif directory not in self._directories:
            self._directories.append(directory)

        if hasattr(self, "_all_directories"):
            if not isinstance(self._all_directories, list):
                self._set_private_attr("_all_directories", [directory])
            elif directory not in self._all_directories:
                self._all_directories.append(directory)

    def _add_file(self, file: File) -> None:
        """Add a file to this directory's files record.

        Args:
            file (File): the file to add

        Raises:
            TypeError: if the file is not a File
        """

        if type(file) is not File:  # pylint: disable=unidiomatic-typecheck
            # This isn't an `isinstance` check because we don't want to allow
            # subclasses of `File` to be added to the list. Yes, according to the
            # Liskov substitution principle, you should be able to process a Directory
            # as a File, but that would be illogical here.
            raise TypeError(
                f"Cannot add `{file.__class__.__name__}` instance to `self.files`."
            )

        if not isinstance(self._files, list):
            self._set_private_attr("_files", [file])
        elif file not in self._files:
            self._files.append(file)

        if hasattr(self, "_all_files"):
            if not isinstance(self._all_files, list):
                self._set_private_attr("_all_files", [file])
            elif file not in self._all_files:
                self._all_files.append(file)

    def add_child(self, child: File | Directory) -> None:
        """Add a child to this directory's children record."""

        if isinstance(child, Directory):
            self._add_directory(child)
        elif isinstance(child, File):
            self._add_file(child)
        else:
            raise TypeError(
                f"Cannot add `{child.__class__.__name__}` instance to {self.name}'s "
                "children."
            )

    def navigate(self, path: str) -> _CanHaveChildren | File:
        # pylint: disable=too-many-return-statements
        """Navigate to a directory within this directory.

        Args:
            path (str): The path to navigate to.

        Raises:
            ValueError: If the path is invalid.

        Returns:
            Directory: The directory at the end of the path.
        """

        if "//" in path:
            raise ValueError("Path cannot contain `//`.")

        if path.startswith("..") and not isinstance(self, Directory):
            raise ValueError("Cannot navigate to parent of Drive.")

        match path.split("/"):
            case ["."] | [".", ""] | [""]:  # Empty string could've come from e.g. "./"
                return self
            case [".."] | ["..", ""]:
                return self.parent  # type: ignore[attr-defined,no-any-return]
            case ["/"] | ["/", ""] | ["", ""] | ["~"] | ["~", ""]:  # / or ~
                return self.host_drive
            case [".", *rest]:  # ./<potential>/<values>
                return self.navigate("/".join(rest))
            case ["..", *rest]:  # ../<potential>/<values>
                return self.parent.navigate(  # type: ignore[attr-defined,no-any-return]
                    "/".join(rest)
                )
            case ["~", *rest]:  # ~/<potential>/<values>
                return self.host_drive.navigate("/".join(rest))
            case ["", drive_name, *rest]:  # /<drive_name>/<potential>/<values>
                # If the first value is an empty string then the first value of `path`
                # must be a slash, therefore the first part of the path must be the
                # (host) drive's name.
                if drive_name != self.host_drive.name:
                    raise ValueError(
                        f"Cannot navigate to Drive {drive_name!r} from "
                        f"`{self.host_drive.name}`."
                    )

                return self.host_drive.navigate("/".join(rest))
            case [directory_name, *rest]:  # <directory_name>/<potential>/<values>
                # Must be a directory if there are subsequent values in the path.

                for child in self.all_known_children:
                    if child.name == directory_name:
                        return child.navigate("/".join(rest))

                try:
                    file_fields = (
                        "*"
                        if self.google_client.item_metadata_retrieval
                        == ItemMetadataRetrieval.ON_INIT
                        else "id, name, parents, mimeType, kind"
                    )

                    item = self.google_client.get_items(
                        "/files",
                        list_key="files",
                        params={
                            "pageSize": "1",
                            "fields": f"files({file_fields})",
                            "q": f"'{self.id}' in parents and name = "
                            f"'{directory_name}'",
                        },
                    ).pop()
                except IndexError:
                    raise ValueError(f"Invalid path: {path!r}") from None

                if item["mimeType"] == Directory.MIME_TYPE:
                    directory = Directory.from_json_response(
                        item,
                        google_client=self.google_client,
                        parent=self,
                        host_drive=self.host_drive,
                        _block_describe_call=True,
                    )
                    self._add_directory(directory)
                    return directory.navigate("/".join(rest))

                file = File.from_json_response(
                    item,
                    google_client=self.google_client,
                    parent=self,
                    host_drive=self.host_drive,
                    _block_describe_call=True,
                )
                self._add_file(file)
                return file
            case _:  # pragma: no cover
                # I haven't found a way to trigger this but have kept it just in case
                raise ValueError(f"Unprocessable path: {path!r}")

    def reset_known_children(self) -> None:
        """Reset the list of known children."""
        self._set_private_attr("_directories", None)
        self._set_private_attr("_directories_loaded", False)
        self._set_private_attr("_files", None)
        self._set_private_attr("_files_loaded", False)

    def tree(self, local_only: bool = False, include_files: bool = False) -> str:
        """Emulate the Linux `tree` command output.

        This builds a directory tree in text form for quick visualisation. Not really
        intended for use in production, but useful for debugging.

        Args:
            local_only (bool, optional): Whether to only show files we already have
                local definitions for. Defaults to False.
            include_files (bool, optional): Whether to include files in the tree.
                Defaults to False.

        Returns:
            str: the full directory tree in text form
        """

        if not local_only:
            self.host_drive.map(
                map_type=EntityType.FILE if include_files else EntityType.DIRECTORY
            )

        output = self.name

        def build_sub_tree(
            parent_dir: _CanHaveChildren,
            level: int,
            block_pipes_at_levels: list[int] | None = None,
        ) -> None:
            """Build a subtree of a given directory.

            Args:
                parent_dir (Directory): the directory to create the subtree of
                level (int): the depth level of this directory
                block_pipes_at_levels (list): a list of levels to block further
                    pipes at
            """

            nonlocal output

            # Creating a deep copy means that when we go back up from the recursion,
            # the previous iteration still has the correct levels in the list
            block_pipes_at_levels = deepcopy(block_pipes_at_levels) or []

            for i, child_item in enumerate(sorted(parent_dir.all_known_children)):
                if include_files is False and not isinstance(child_item, Directory):
                    continue

                prefix = "\n"

                # build out the spaces and pipes on this line, in such a way to
                # maintain continuity from the previous line
                for j in range(level):
                    prefix += " " if j in block_pipes_at_levels else "│"
                    prefix += "    "

                # if this is the last child
                if i + 1 == len(parent_dir.all_known_children):
                    prefix += "└"
                    block_pipes_at_levels.append(level)
                else:
                    prefix += "├"

                if isinstance(child_item, Directory):
                    prefix += "─── "
                else:
                    prefix += "──> "

                output += prefix + child_item.name

                if isinstance(child_item, Directory):
                    build_sub_tree(child_item, level + 1, block_pipes_at_levels)

        build_sub_tree(self, 0)

        return output

    @property
    def all_known_children(self) -> list[Directory | File]:
        """Get all known children of this directory.

        No HTTP requests are made to get these children, so this may not be an
        exhaustive list.

        Returns:
            list[Directory | File]: The list of children.
        """
        if not isinstance(self._directories, list):
            self._set_private_attr("_directories", [])

        if not isinstance(self._files, list):
            self._set_private_attr("_files", [])

        return self._files + self._directories  # type: ignore[operator]

    @property
    def children(self) -> list[Directory | File]:
        """Get all immediate children of this Drive/Directory.

        Returns:
            list[Directory | File]: The list of children.
        """
        # TODO needs a check to avoid requesting every time
        self.reset_known_children()
        return self.files + self.directories  # type: ignore[operator]

    @property
    def directories(self) -> list[Directory]:
        """The directories contained within this directory.

        Returns:
            list: the directories contained within this directory
        """

        if self._directories_loaded is not True:
            # TODO replace these with a `file_fields` property
            file_fields = (
                "*"
                if self.google_client.item_metadata_retrieval
                == ItemMetadataRetrieval.ON_INIT
                else "id, name, parents, mimeType, kind"
            )

            # TODO: this needs to be changed to only get *new* folders - currently this
            #   will overwrite any known children, including all metadata ad further
            #   descendents
            self._set_private_attr(
                "_directories",
                sorted(
                    [
                        Directory.from_json_response(
                            directory,
                            google_client=self.google_client,
                            parent=self,
                            host_drive=self.host_drive,
                            _block_describe_call=True,
                        )
                        for directory in self.google_client.get_items(
                            "/files",
                            list_key="files",
                            params={
                                "pageSize": 1000,
                                "q": f"mimeType = '{Directory.MIME_TYPE}'"
                                f" and '{self.id}' in parents",
                                "fields": f"nextPageToken, files({file_fields})",
                            },
                        )
                    ]
                ),
            )

            self._set_private_attr("_directories_loaded", True)

        return self._directories

    @property
    def files(self) -> list[File]:
        """The files contained within this directory.

        Returns:
            list: the list of files contained within this directory
        """
        if self._files_loaded is not True:
            file_fields = (
                "*"
                if self.google_client.item_metadata_retrieval
                == ItemMetadataRetrieval.ON_INIT
                else "id, name, parents, mimeType, kind"
            )

            self._set_private_attr(
                "_files",
                [
                    File.from_json_response(
                        item,
                        google_client=self.google_client,
                        parent=self,
                        host_drive=self.host_drive,
                        _block_describe_call=True,
                    )
                    for item in self.google_client.get_items(
                        "/files",
                        list_key="files",
                        params={
                            "pageSize": 1000,
                            "q": f"mimeType != '{Directory.MIME_TYPE}' and"
                            f" '{self.id}' in parents",
                            "fields": f"nextPageToken, files({file_fields})",
                        },
                    )
                ],
            )
            self._set_private_attr("_files_loaded", True)

        return list(self._files)


class File(_GoogleDriveEntity):
    """A file object within Google Drive."""

    kind: EntityKind = Field(alias="kind", const=True, default=EntityKind.FILE)

    # Optional, can be retrieved with the `describe` method or by getting the attribute
    app_properties: dict[str, str] = {}
    capabilities: _DriveCapabilities | None
    content_hints: _ContentHints | None = Field(alias="contentHints")
    content_restrictions: list[_ContentRestriction] | None = Field(
        alias="contentRestrictions"
    )
    copy_requires_writer_permission: bool | None = Field(
        alias="copyRequiresWriterPermission"
    )
    created_time: datetime | None = Field(alias="createdTime")
    description: str | None
    drive_id: str | None = Field(alias="driveId")
    explicitly_trashed: bool | None = Field(alias="explicitlyTrashed")
    export_links: dict[str, str] = Field(alias="exportLinks", default_factory=dict)
    folder_color_rgb: str | None = Field(alias="folderColorRgb")
    file_extension: str | None = Field(alias="fileExtension")
    full_file_extension: str | None = Field(alias="fullFileExtension")
    has_augmented_permissions: bool | None = Field(alias="hasAugmentedPermissions")
    has_thumbnail: bool | None = Field(alias="hasThumbnail")
    head_revision_id: str | None = Field(alias="headRevisionId")
    icon_link: str | None = Field(alias="iconLink")
    image_media_metadata: _ImageMediaMetadata | None = Field(alias="imageMediaMetadata")
    is_app_authorized: bool | None = Field(alias="isAppAuthorized")
    label_info: dict[Literal["labels"], list[_Label]] = Field(
        alias="labelInfo", default_factory=dict
    )
    last_modifying_user: _User | None = Field(alias="lastModifyingUser")
    link_share_metadata: dict[
        Literal["securityUpdateEligible", "securityUpdateEnabled"], bool
    ] = Field(alias="linkShareMetadata", default_factory=dict)
    md5_checksum: str | None = Field(alias="md5Checksum")
    modified_by_me: bool | None = Field(alias="modifiedByMe")
    modified_by_me_time: datetime | None = Field(alias="modifiedByMeTime")
    modified_time: datetime | None = Field(alias="modifiedTime")
    original_filename: str | None = Field(alias="originalFilename")
    owned_by_me: bool | None = Field(alias="ownedByMe")
    owners: list[_User] = []
    parents: list[str]
    properties: dict[str, str] = {}
    permissions: list[_Permission] = []
    permission_ids: list[str] = Field(alias="permissionIds", default_factory=list)
    quota_bytes_used: float | None = Field(alias="quotaBytesUsed")
    resource_key: str | None = Field(alias="resourceKey")
    shared: bool | None
    sha1_checksum: str | None = Field(alias="sha1Checksum")
    sha256_checksum: str | None = Field(alias="sha256Checksum")
    shared_with_me_time: datetime | None = Field(alias="sharedWithMeTime")
    sharing_user: _User | None = Field(alias="sharingUser")
    shortcut_details: dict[
        Literal[
            "targetId",
            "targetMimeType",
            "targetResourceKey",
        ],
        str,
    ] = Field(alias="shortcutDetails", default_factory=dict)
    size: float | None
    spaces: list[str] = []
    starred: bool | None
    thumbnail_link: str | None = Field(alias="thumbnailLink")
    thumbnail_version: int | None = Field(alias="thumbnailVersion")
    trashed: bool | None
    trashed_time: datetime | None = Field(alias="trashedTime")
    trashing_user: _User | None = Field(alias="trashingUser")
    version: int | None
    video_media_metadata: _VideoMediaMetadata | None = Field(alias="videoMediaMetadata")
    viewed_by_me: bool | None = Field(alias="viewedByMe")
    viewed_by_me_time: datetime | None = Field(alias="viewedByMeTime")
    viewers_can_copy_content: bool | None = Field(alias="viewersCanCopyContent")
    web_content_link: str | None = Field(alias="webContentLink")
    web_view_link: str | None = Field(alias="webViewLink")
    writers_can_share: bool | None = Field(alias="writersCanShare")

    _description: dict[str, str | bool | float | int] = Field(
        exclude=True,
    )
    host_drive_: Drive = Field(exclude=True)
    parent_: Directory | Drive | None = Field(exclude=True)

    def __getattribute__(self, name: str) -> Any:
        """Override the default `__getattribute__` to allow for lazy metadata loading.

        Args:
            name (str): The name of the attribute to retrieve.

        Returns:
            Any: The value of the attribute.
        """

        # If the attribute isn't a field, just return the value
        if (
            (name.startswith("__") and name.endswith("__"))
            or name not in self.__fields__
            or self.__fields__[name].field_info.exclude is True
        ):
            return super().__getattribute__(name)

        if name not in self.__fields_set__ or not super().__getattribute__(name):
            # If IMR is enabled, load all metadata
            if (
                self.google_client.item_metadata_retrieval
                == ItemMetadataRetrieval.ON_FIRST_REQUEST
            ):
                self.describe()
                return super().__getattribute__(name)

            # Otherwise just get the single field
            google_key = self.__fields__[name].alias or name

            res = self.google_client.get_json_response(
                f"/files/{self.id}",
                params={"fields": google_key, "pageSize": None},
            )
            setattr(self, name, res.pop(google_key, None))

            # I can't just return the value of `res.pop(google_key, None)` here because
            # it needs to go through Pydantic's validators first

        return super().__getattribute__(name)

    @validator("mime_type")
    def _validate_mime_type(cls, mime_type: str) -> str:  # noqa: N805
        if mime_type == Directory.MIME_TYPE:
            raise ValueError("Use `Directory` class to create a directory.")

        return mime_type

    @validator("parents")
    def _validate_parents(cls, parents: list[str]) -> list[str]:  # noqa: N805
        if len(parents) != 1:
            raise ValueError(f"A {cls.__name__} must have exactly one parent.")

        return parents

    @validator("parent_")
    def _validate_parent_instance(
        cls, value: Directory | Drive | None, values: dict[str, Any]  # noqa: N805
    ) -> Directory | Drive | None:
        """Validate that the parent instance's ID matches the expected parent ID.

        Args:
            value (Directory, Drive): The parent instance.
            values (dict): The values of the other fields

        Returns:
            Directory, Drive: The parent instance.

        Raises:
            ValueError: If the parent instance's ID doesn't match the expected parent
                ID.
        """

        if value is None:
            return value

        if value.id != values["parents"][0]:
            raise ValueError(
                f"Parent ID mismatch: {value.id} != {values['parents'][0]}"
            )

        return value

    def describe(
        self, force_update: bool = False
    ) -> dict[str, str | bool | float | int]:
        """Describe the file by requesting all available fields from the Drive API.

        Args:
            force_update (bool): re-pull the description from Google Drive, even if we
             already have the description locally

        Returns:
            dict: the description JSON for this file

        Raises:
            ValueError: if an unexpected field is returned from the Google Drive API.
        """

        if (
            force_update
            or not hasattr(self, "_description")
            or not isinstance(self._description, dict)
        ):
            self._set_private_attr(
                "_description",
                self.google_client.get_json_response(
                    f"/files/{self.id}",
                    params={"fields": "*", "pageSize": None},
                ),
            )

            for key, value in self._description.items():
                google_key = sub("([A-Z])", r"_\1", key).lower()

                try:
                    setattr(self, google_key, value)
                except ValueError as exc:
                    raise ValueError(
                        f"Received unexpected field {key!r} with value {value!r}"
                        " from Google Drive API"
                    ) from exc

        return self._description

    @property
    def parent(self) -> Directory | Drive:
        """Get the parent directory of this file.

        Returns:
            Directory: the parent directory of this file
        """
        # pylint: disable=isinstance-second-argument-not-valid-type
        if self.parent_ is None and isinstance(self, File | Directory):
            if (parent_id := self.parents[0]) == self.host_drive.id:
                self.parent_ = self.host_drive
            else:
                self.parent_ = self.host_drive.get_directory_by_id(parent_id)

            self.parent_.add_child(self)

        return self.parent_

    def __gt__(self, other: File) -> bool:
        """Compare two files by name."""
        return self.name.lower() > other.name.lower()

    def __lt__(self, other: File) -> bool:
        """Compare two files by name."""
        return self.name.lower() < other.name.lower()

    def __repr__(self) -> str:
        """Return a string representation of the file."""
        return f"File(id={self.id!r}, name={self.name!r})"


class Directory(File, _CanHaveChildren):
    """A Google Drive directory - basically a File with extended functionality."""

    MIME_TYPE: ClassVar[
        Literal["application/vnd.google-apps.folder"]
    ] = "application/vnd.google-apps.folder"

    kind: EntityKind = Field(default=EntityKind.DIRECTORY, const=True)
    mime_type: Literal["application/vnd.google-apps.folder"] = Field(
        alias="mimeType", const=True, default=MIME_TYPE
    )

    host_drive_: Drive = Field(exclude=True)

    @validator("kind", always=True, pre=True)
    def _validate_kind(cls, value: str | None) -> str:  # noqa: N805
        """Set the kind to "drive#folder"."""

        # Directories are just a subtype of files, so `"drive#file"` is okay too
        if value not in (EntityKind.DIRECTORY, EntityKind.FILE):
            raise ValueError(f"Invalid kind for Directory: {value}")

        return "drive#folder"

    @validator("mime_type")
    def _validate_mime_type(cls, mime_type: str) -> str:  # noqa: N805
        """Just an override for the parent class's validator."""

        return mime_type

    def __repr__(self) -> str:
        """Return a string representation of the directory."""
        return f"Directory(id={self.id!r}, name={self.name!r})"


class _DriveCapabilities(BaseModelWithConfig):
    can_accept_ownership: bool | None = Field(alias="canAcceptOwnership")
    can_add_children: bool | None = Field(alias="canAddChildren")
    can_add_folder_from_another_drive: bool | None = Field(
        alias="canAddFolderFromAnotherDrive"
    )
    can_add_my_drive_parent: bool | None = Field(alias="canAddMyDriveParent")
    can_change_copy_requires_writer_permission: bool | None = Field(
        alias="canChangeCopyRequiresWriterPermission"
    )
    can_change_copy_requires_writer_permission_restriction: bool | None = Field(
        alias="canChangeCopyRequiresWriterPermissionRestriction"
    )
    can_change_domain_users_only_restriction: bool | None = Field(
        alias="canChangeDomainUsersOnlyRestriction"
    )
    can_change_drive_background: bool | None = Field(alias="canChangeDriveBackground")
    can_change_drive_members_only_restriction: bool | None = Field(
        alias="canChangeDriveMembersOnlyRestriction"
    )
    can_change_security_update_enabled: bool | None = Field(
        alias="canChangeSecurityUpdateEnabled"
    )
    can_change_viewers_can_copy_content: bool | None = Field(
        alias="canChangeViewersCanCopyContent"
    )
    can_comment: bool | None = Field(alias="canComment")
    can_copy: bool | None = Field(alias="canCopy")
    can_delete: bool | None = Field(alias="canDelete")
    can_delete_children: bool | None = Field(alias="canDeleteChildren")
    can_delete_drive: bool | None = Field(alias="canDeleteDrive")
    can_download: bool | None = Field(alias="canDownload")
    can_edit: bool | None = Field(alias="canEdit")
    can_list_children: bool | None = Field(alias="canListChildren")
    can_manage_members: bool | None = Field(alias="canManageMembers")
    can_modify_content: bool | None = Field(alias="canModifyContent")
    can_modify_content_restriction: bool | None = Field(
        alias="canModifyContentRestriction"
    )
    can_modify_labels: bool | None = Field(alias="canModifyLabels")
    can_move_children_out_of_drive: bool | None = Field(
        alias="canMoveChildrenOutOfDrive"
    )
    can_move_children_within_drive: bool | None = Field(
        alias="canMoveChildrenWithinDrive"
    )
    can_move_item_into_team_drive: bool | None = Field(alias="canMoveItemIntoTeamDrive")
    can_move_item_out_of_drive: bool | None = Field(alias="canMoveItemOutOfDrive")
    can_move_item_within_drive: bool | None = Field(alias="canMoveItemWithinDrive")
    can_read_labels: bool | None = Field(alias="canReadLabels")
    can_read_revisions: bool = Field(alias="canReadRevisions")
    can_read_drive: bool | None = Field(alias="canReadDrive")
    can_remove_children: bool | None = Field(alias="canRemoveChildren")
    can_remove_my_drive_parent: bool | None = Field(alias="canRemoveMyDriveParent")
    can_rename: bool | None = Field(alias="canRename")
    can_rename_drive: bool | None = Field(alias="canRenameDrive")
    can_reset_drive_restrictions: bool | None = Field(alias="canResetDriveRestrictions")
    can_share: bool | None = Field(alias="canShare")
    can_trash: bool | None = Field(alias="canTrash")
    can_trash_children: bool | None = Field(alias="canTrashChildren")
    can_untrash: bool | None = Field(alias="canUntrash")


class _DriveRestrictions(BaseModelWithConfig):
    admin_managed_restrictions: bool = Field(alias="adminManagedRestrictions")
    copy_requires_writer_permission: bool = Field(alias="copyRequiresWriterPermission")
    domain_users_only: bool = Field(alias="domainUsersOnly")
    drive_members_only: bool = Field(alias="driveMembersOnly")


class _DriveBackgroundImageFile(BaseModelWithConfig):
    id: str
    x_coordinate: float = Field(alias="xCoordinate")
    y_coordinate: float = Field(alias="yCoordinate")
    width: float


DriveSubEntity = TypeVar("DriveSubEntity", Directory, File)


class Drive(_CanHaveChildren):
    """A Google Drive: Drive - basically a Directory with extended functionality."""

    kind: EntityKind = Field(alias="kind", const=True, default=EntityKind.DRIVE)
    mime_type: Literal["application/vnd.google-apps.folder"] = Field(
        alias="mimeType", const=True, default=Directory.MIME_TYPE
    )

    # Optional, can be retrieved with the `describe` method or by getting the attribute
    background_image_file: _DriveBackgroundImageFile | None = Field(
        alias="backgroundImageFile"
    )
    background_image_link: str | None = Field(alias="backgroundImageLink")
    capabilities: _DriveCapabilities | None
    color_rgb: str | None = Field(alias="colorRgb")
    copy_requires_writer_permission: bool | None = Field(
        alias="copyRequiresWriterPermission"
    )
    created_time: datetime | None = Field(alias="createdTime")
    explicitly_trashed: bool | None = Field(alias="explicitlyTrashed")
    folder_color_rgb: str | None = Field(alias="folderColorRgb")
    has_thumbnail: bool | None = Field(alias="hasThumbnail")
    hidden: bool | None
    icon_link: str | None = Field(alias="iconLink")
    is_app_authorized: bool | None = Field(alias="isAppAuthorized")
    last_modifying_user: _User | None = Field(alias="lastModifyingUser")
    link_share_metadata: dict[
        Literal["securityUpdateEligible", "securityUpdateEnabled"], bool
    ] = Field(alias="linkShareMetadata", default_factory=dict)
    modified_by_me: bool | None = Field(alias="modifiedByMe")
    modified_by_me_time: datetime | None = Field(alias="modifiedByMeTime")
    modified_time: datetime | None = Field(alias="modifiedTime")
    org_unit_id: str | None = Field(alias="orgUnitId")
    owned_by_me: bool | None = Field(alias="ownedByMe")
    owners: list[_User] = []
    permissions: list[_Permission] = []
    permission_ids: list[str] = Field(alias="permissionIds", default_factory=list)
    quota_bytes_used: float | None = Field(alias="quotaBytesUsed")
    restrictions: _DriveRestrictions | None
    shared: bool | None
    spaces: list[str] = []
    starred: bool | None
    theme_id: str | None = Field(alias="themeId")
    thumbnail_version: int | None = Field(alias="thumbnailVersion")
    trashed: bool | None
    version: int | None
    viewed_by_me: bool | None = Field(alias="viewedByMe")
    viewers_can_copy_content: bool | None = Field(alias="viewersCanCopyContent")
    web_view_link: str | None = Field(alias="webViewLink")
    writers_can_share: bool | None = Field(alias="writersCanShare")

    parent_: None = Field(exclude=True, const=True, default=None)
    host_drive_: None = Field(exclude=True, const=True, default=None)

    _all_directories: list[Directory] = Field(exclude=True, default_factory=list)
    _directories_mapped: bool = Field(exclude=True, default=False)
    _all_files: list[File] = Field(exclude=True, default_factory=list)
    _files_mapped: bool = Field(exclude=True, default=False)

    @validator("kind", always=True, pre=True)
    def _validate_kind(cls, value: str | None) -> str:  # noqa: N805
        """Set the kind to "drive#drive"."""

        # Drives are just a subtype of files, so `"drive#file"` is okay too
        if value not in (EntityKind.DRIVE, EntityKind.FILE):
            raise ValueError(f"Invalid kind for Drive: {value}")

        return "drive#drive"

    def _get_entity_by_id(
        self, cls: type[DriveSubEntity], entity_id: str
    ) -> DriveSubEntity:
        """Get either a Directory or File by its ID.

        Args:
            cls (type): The class of the entity to get.
            entity_id (str): The ID of the entity to get.
        """
        file_fields = (
            "*"
            if self.google_client.item_metadata_retrieval
            == ItemMetadataRetrieval.ON_INIT
            else "id, name, parents, mimeType, kind"
        )

        return cls.from_json_response(
            self.google_client.get_json_response(
                f"/files/{entity_id}",
                params={
                    "fields": file_fields,
                    "pageSize": None,
                },
            ),
            google_client=self.google_client,
            host_drive=self,
            _block_describe_call=True,
        )

    def get_directory_by_id(self, directory_id: str) -> Directory:
        """Get a directory by its ID.

        Args:
            directory_id (str): the ID of the directory to get

        Returns:
            Directory: the directory with the given ID

        Raises:
            ResourceNotFoundError: if a directory with the given ID does not exist
        """
        if isinstance(self._all_directories, list):
            for directory in self._all_directories:
                if directory.id == directory_id:
                    return directory

        return self._get_entity_by_id(Directory, directory_id)

    def get_file_by_id(self, file_id: str) -> File:
        """Get a file by its ID.

        Args:
            file_id (str): the ID of the file to get

        Returns:
            File: the file with the given ID

        Raises:
            ResourceNotFoundError: if a file with the given ID does not exist
        """
        if isinstance(self._all_files, list):
            for file in self._all_files:
                if file.id == file_id:
                    return file

        return self._get_entity_by_id(File, file_id)

    def map(self, map_type: EntityType = EntityType.FILE) -> None:
        """Traverse the entire Drive to map its content.

        Args:
            map_type (EntityType, optional): the type of entity to map. Defaults to
                EntityType.FILE.
        """

        if (map_type == EntityType.DIRECTORY and self._directories_mapped is True) or (
            map_type == EntityType.FILE and self._files_mapped is True
        ):
            return

        # May as well get all fields in initial request if we're going to do it per
        # item anyway
        file_fields = (
            "*"
            if self.google_client.item_metadata_retrieval
            == ItemMetadataRetrieval.ON_INIT
            else "id, name, parents, mimeType, kind"
        )

        params = {
            "pageSize": 1000,
            "fields": f"nextPageToken, files({file_fields})",
        }

        if map_type == EntityType.DIRECTORY:
            params["q"] = f"mimeType = '{Directory.MIME_TYPE}'"

        all_items = self.google_client.get_items(
            "/files",
            list_key="files",
            params=params,
        )
        all_files = []
        all_directories = []
        all_items = [item for item in all_items if "parents" in item]

        known_descendent_ids = [child.id for child in self.all_known_descendents]

        def build_sub_structure(
            parent_dir: _CanHaveChildren,
        ) -> None:
            """Build the sub-structure a given directory recursively.

            Args:
                parent_dir (_CanHaveChildren): the parent directory to build the
                    sub-structure for
            """
            nonlocal all_items

            remaining_items = []

            to_be_mapped = []
            for item in all_items:
                try:
                    if parent_dir.id != item["parents"][0]:
                        remaining_items.append(item)
                        continue
                except LookupError:  # pragma: no cover
                    continue

                if item["id"] in known_descendent_ids:
                    if item["mimeType"] == Directory.MIME_TYPE:
                        to_be_mapped.append(self.get_directory_by_id(item["id"]))

                # Can't use `kind` here as it can be `drive#file` for directories
                elif item["mimeType"] == Directory.MIME_TYPE:
                    directory = Directory.from_json_response(
                        item,
                        google_client=self.google_client,
                        parent=parent_dir,
                        host_drive=self,
                        _block_describe_call=True,
                    )
                    parent_dir.add_child(directory)
                    all_directories.append(directory)
                    to_be_mapped.append(directory)
                else:
                    file = File.from_json_response(
                        item,
                        google_client=self.google_client,
                        parent=parent_dir,
                        host_drive=self,
                        _block_describe_call=True,
                    )
                    parent_dir.add_child(file)
                    all_files.append(file)

            all_items = remaining_items
            for directory in to_be_mapped:
                build_sub_structure(directory)

        build_sub_structure(self)

        self._set_private_attr(
            "_all_directories",
            all_directories,
        )
        self._set_private_attr(
            "_directories_mapped",
            True,
        )

        if map_type != EntityType.DIRECTORY:
            self._set_private_attr(
                "_all_files",
                all_files,
            )
            self._set_private_attr(
                "_files_mapped",
                True,
            )

    def search(
        self,
        term: str,
        entity_type: EntityType | None = None,
        max_results: int = 50,
        exact_match: bool = False,
        created_range: tuple[datetime, datetime] | None = None,
    ) -> list[File | Directory]:
        """Search for files and directories in the Drive.

        Args:
            term (str): the term to search for
            entity_type (EntityType | None, optional): the type of
                entity to search for. Defaults to None.
            max_results (int, optional): the maximum number of results to return.
                Defaults to 50.
            exact_match (bool, optional): whether to only return results that exactly
                match the search term. Defaults to False.
            created_range (tuple[datetime, datetime], optional): a tuple containing the
                start and end of the date range to search in. Defaults to None.

        Returns:
            list[File | Directory]: the files and directories that match the search
                term

        Raises:
            ValueError: if the given entity type is not supported
        """

        file_fields = (
            "*"
            if self.google_client.item_metadata_retrieval
            == ItemMetadataRetrieval.ON_INIT
            else "id, name, parents, mimeType, kind"
        )

        params = {
            "pageSize": 1 if exact_match else min(max_results, 1000),
            "fields": f"nextPageToken, files({file_fields})",
        }

        query_conditions = [
            f"name = '{term}'" if exact_match else f"name contains '{term}'",
        ]

        if entity_type == EntityType.DIRECTORY:
            query_conditions.append(f"mimeType = '{Directory.MIME_TYPE}'")
        elif entity_type == EntityType.FILE:
            query_conditions.append(f"mimeType != '{Directory.MIME_TYPE}'")
        elif entity_type is not None:
            raise ValueError(
                "`entity_type` must be either EntityType.FILE or EntityType.DIRECTORY,"
                " or None to search for both",
            )

        if created_range:
            query_conditions.append(f"createdTime > '{created_range[0].isoformat()}'")
            query_conditions.append(f"createdTime <= '{created_range[1].isoformat()}'")

        params["q"] = " and ".join(query_conditions)

        all_items = self.google_client.get_items(
            "/files",
            list_key="files",
            params=params,
        )

        return [
            (
                Directory if item["mimeType"] == Directory.MIME_TYPE else File
            ).from_json_response(
                item,
                host_drive=self,
                google_client=self.google_client,
                _block_describe_call=True,
            )
            for item in all_items
        ]

    @property
    def all_known_descendents(self) -> list[Directory | File]:
        """Get all known children of this directory.

        No HTTP requests are made to get these children, so this may not be an
        exhaustive list.

        Returns:
            list[Directory | File]: The list of children.
        """
        if not isinstance(self._all_directories, list):
            self._set_private_attr("_all_directories", [])

        if not isinstance(self._all_files, list):
            self._set_private_attr("_all_files", [])

        return self._all_files + self._all_directories  # type: ignore[operator]

    @property
    def all_directories(self) -> list[Directory]:
        """Get all directories in the Drive."""

        if self._directories_mapped is not True:
            self.map(map_type=EntityType.DIRECTORY)

        return self._all_directories

    @property
    def all_files(self) -> list[File]:
        """Get all files in the Drive."""

        if self._files_mapped is not True:
            self.map()

        return self._all_files

    def __repr__(self) -> str:
        """Return a string representation of the directory."""
        return f"Drive(id={self.id!r}, name={self.name!r}"


class ItemMetadataRetrieval(str, Enum):
    """The type of metadata retrieval to use for items.

    Attributes:
        ON_DEMAND (str): only retrieves single metadata items on demand. Best for
            reducing memory usage but makes most HTTP requests.
        ON_FIRST_REQUEST (str): retrieves all metadata items on the first request for
            _any_ metadata value. Nice middle ground between memory usage and HTTP
            requests.
        ON_INIT (str): retrieves metadata on instance initialisation. Increases memory
            usage, makes the fewest HTTP requests. If combined with a `Drive.map` call,
            it can be used to preload all metadata for the entire Drive.
    """

    ON_DEMAND = "on_demand"
    ON_FIRST_REQUEST = "on_first_request"
    ON_INIT = "on_init"


class GoogleDriveClient(GoogleClient[JSONObj]):
    """Custom client specifically for Google's Drive API.

    Args:
        scopes (list): a list of scopes the client can be given
        creds_cache_path (str): file path for where to cache credentials
    """

    BASE_URL = "https://www.googleapis.com/drive/v3"

    DEFAULT_SCOPE = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
        "https://www.googleapis.com/auth/drive.appdata",
        "https://www.googleapis.com/auth/drive.metadata",
        "https://www.googleapis.com/auth/drive.photos.readonly",
    ]

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        scopes: list[str] | None = None,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
        # pylint: disable=line-too-long
        item_metadata_retrieval: ItemMetadataRetrieval = ItemMetadataRetrieval.ON_FIRST_REQUEST,
    ):
        super().__init__(
            base_url=self.BASE_URL,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes or self.DEFAULT_SCOPE,
            log_requests=log_requests,
            creds_cache_path=creds_cache_path,
        )

        self._my_drive: Drive
        self.item_metadata_retrieval = item_metadata_retrieval

    @property
    def my_drive(self) -> Drive:
        """User's personal Drive.

        Returns:
            Drive: the user's root directory/main Drive
        """
        if not hasattr(self, "_my_drive"):
            self._my_drive = Drive.from_json_response(
                self.get_json_response(
                    "/files/root", params={"fields": "*", "pageSize": None}
                ),
                google_client=self,
            )

        return self._my_drive

    @property
    def shared_drives(self) -> list[Drive]:
        """Get a list of all shared drives.

        Returns:
            list: a list of Shared Drives the current user has access to
        """
        return [
            Drive.from_json_response(
                drive,
                google_client=self,
            )
            for drive in self.get_items(
                "/drives", list_key="drives", params={"fields": "*"}
            )
        ]


FJR = TypeVar("FJR", bound=_GoogleDriveEntity)

_GoogleDriveEntity.update_forward_refs()
File.update_forward_refs()
Directory.update_forward_refs()
Drive.update_forward_refs()
