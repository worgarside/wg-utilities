# pylint: disable=too-few-public-methods
"""Custom client for interacting with Google's Photos API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum, auto
from logging import DEBUG, getLogger
from os import getenv
from pathlib import Path
from typing import Any, Literal, TypeAlias, TypedDict, TypeVar

from pydantic import Field
from requests import get, post

from wg_utilities.clients._google import GoogleClient
from wg_utilities.clients.oauth_client import (
    BaseModelWithConfig,
    GenericModelWithConfig,
)
from wg_utilities.functions import force_mkdir, user_data_dir
from wg_utilities.loggers import add_stream_handler

LOCAL_MEDIA_DIRECTORY = Path(
    getenv("LOCAL_MEDIA_DIRECTORY", user_data_dir(file_name="media_downloads"))
)


LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


class _SharedAlbumOptionsInfo(TypedDict):
    isCollaborative: bool  # noqa: N815
    isCommentable: bool  # noqa: N815


class _ShareInfoInfo(TypedDict):
    isJoinable: bool  # noqa: N815
    isJoined: bool  # noqa: N815
    isOwned: bool  # noqa: N815
    shareableUrl: str  # noqa: N815
    sharedAlbumOptions: _SharedAlbumOptionsInfo  # noqa: N815
    shareToken: str  # noqa: N815


class _MediaItemMetadataPhoto(BaseModelWithConfig):
    camera_make: str | None = Field(alias="cameraMake")
    camera_model: str | None = Field(alias="cameraModel")
    focal_length: float | None = Field(alias="focalLength")
    aperture_f_number: float | None = Field(alias="apertureFNumber")
    iso_equivalent: int | None = Field(alias="isoEquivalent")
    exposure_time: str | None = Field(alias="exposureTime")


class _MediaItemMetadataVideo(BaseModelWithConfig):
    camera_make: str | None = Field(alias="cameraMake")
    camera_model: str | None = Field(alias="cameraModel")
    status: Literal["READY"] | None
    fps: float | None


class _MediaItemMetadata(BaseModelWithConfig):
    creation_time: datetime = Field(alias="creationTime")
    height: int
    width: int
    photo: _MediaItemMetadataPhoto | None
    video: _MediaItemMetadataVideo | None


class MediaType(Enum):
    """Enum for all potential media types."""

    IMAGE = auto()
    VIDEO = auto()
    UNKNOWN = auto()


FJR = TypeVar("FJR", bound="GooglePhotosEntity")


class GooglePhotosEntity(GenericModelWithConfig):
    """Base class for Google Photos} entities."""

    id: str
    product_url: str = Field(alias="productUrl")

    google_client: GooglePhotosClient

    @classmethod
    def from_json_response(
        cls: type[FJR],
        value: GooglePhotosEntityJson,
        *,
        google_client: GooglePhotosClient,
    ) -> FJR:
        """Creates a Calendar/Event from a JSON response."""

        value_data: dict[str, Any] = {
            "google_client": google_client,
            **value,
        }

        return cls.parse_obj(value_data)


class AlbumJson(TypedDict):
    """JSON representation of an Album."""

    id: str
    productUrl: str  # noqa: N815

    coverPhotoBaseUrl: str  # noqa: N815
    coverPhotoMediaItemId: str  # noqa: N815
    isWriteable: bool | None  # noqa: N815
    mediaItemsCount: int  # noqa: N815
    shareInfo: _ShareInfoInfo | None  # noqa: N815
    title: str


class Album(GooglePhotosEntity):
    """Class for Google Photos albums and their metadata/content."""

    cover_photo_base_url: str = Field(alias="coverPhotoBaseUrl")
    cover_photo_media_item_id: str = Field(alias="coverPhotoMediaItemId")
    is_writeable: bool | None = Field(alias="isWriteable")
    media_items_count: int = Field(alias="mediaItemsCount")
    share_info: _ShareInfoInfo | None = Field(alias="shareInfo")
    title: str

    _media_items: list[MediaItem]

    @property
    def media_items(self) -> list[MediaItem]:
        # noinspection GrazieInspection
        """Lists all media items in the album.

        Returns:
            list: a list of MediaItem instances, representing the contents of the album
        """

        if not hasattr(self, "_media_items"):
            self._set_private_attr(
                "_media_items",
                [
                    MediaItem.from_json_response(item, google_client=self.google_client)
                    for item in self.google_client.get_items(
                        "/mediaItems:search",
                        method=post,
                        list_key="mediaItems",
                        params={"albumId": self.id},
                    )
                ],
            )

        return self._media_items


class MediaItemJson(TypedDict):
    """JSON representation of a Media Item (photo or video)."""

    id: str
    productUrl: str  # noqa: N815

    baseUrl: str  # noqa: N815
    contributorInfo: dict[str, str] | None  # noqa: N815
    description: str | None
    filename: str
    mediaMetadata: _MediaItemMetadata  # noqa: N815
    mimeType: str  # noqa: N815


class MediaItem(GooglePhotosEntity):
    """Class for representing a MediaItem and its metadata/content."""

    base_url: str = Field(alias="baseUrl")
    contributor_info: dict[str, str] | None = Field(alias="contributorInfo")
    description: str | None
    filename: str
    media_metadata: _MediaItemMetadata = Field(alias="mediaMetadata")
    mime_type: str = Field(alias="mimeType")

    def download(
        self,
        width_override: int | None = None,
        height_override: int | None = None,
        force_download: bool = False,
    ) -> Path:
        """Download the media item to local storage.

        Notes:
            The width/height overrides do not apply to videos.

        Args:
            width_override (int): the width override to use when downloading the file
            height_override (int): the height override to use when downloading the file
            force_download (bool): flag for forcing a download, even if it exists
             locally already

        Returns:
             str: the path to the downloaded file (self.local_path)
        """
        if not self.local_path.is_file() or force_download:
            width = width_override or self.width
            height = height_override or self.height

            param_str = {
                MediaType.IMAGE: f"=w{width}-h{height}",
                MediaType.VIDEO: "=dv",
            }.get(self.media_type, "")

            force_mkdir(self.local_path, path_is_file=True).write_bytes(
                get(f"{self.base_url}{param_str}").content
            )

        return self.local_path

    @property
    def bytes(self) -> bytes:
        """MediaItem binary content.

        Opens the local copy of the file (downloading it first if necessary) and
        reads the binary content of it

        Returns:
            bytes: the binary content of the file
        """
        if not self.local_path.is_file():
            self.download()

        return self.local_path.read_bytes()

    @property
    def creation_datetime(self) -> datetime:
        """The datetime when the media item was created."""
        return self.media_metadata.creation_time

    @property
    def local_path(self) -> Path:
        """The path which the is/would be stored at locally.

        Returns:
            Path: where the file is/will be stored
        """

        return (
            LOCAL_MEDIA_DIRECTORY
            / self.creation_datetime.strftime("%Y/%m/%d")
            / self.filename
        )

    @property
    def height(self) -> int:
        """MediaItem height.

        Returns:
            int: the media item's height
        """
        return self.media_metadata.height

    @property
    def width(self) -> int:
        """MediaItem width.

        Returns:
            int: the media item's width
        """
        return self.media_metadata.width

    @property
    def media_type(self) -> MediaType:
        """Determines the media item's file type from the JSON.

        Returns:
            MediaType: the media type (image, video, etc.) for this item
        """

        if "image" in self.mime_type:
            return MediaType.IMAGE

        if "video" in self.mime_type:
            return MediaType.VIDEO

        return MediaType.UNKNOWN


GooglePhotosEntityJson: TypeAlias = AlbumJson | MediaItemJson


class GooglePhotosClient(GoogleClient[GooglePhotosEntityJson]):
    """Custom client for interacting with the Google Photos API.

    See Also:
        GoogleClient: the base Google client, used for authentication and common
         functions
    """

    BASE_URL = "https://photoslibrary.googleapis.com/v1"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        scopes: list[str] | None = None,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
    ):
        super().__init__(
            base_url=self.BASE_URL,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
            log_requests=log_requests,
            creds_cache_path=creds_cache_path,
        )

        self._albums: list[Album]

    def get_album_by_id(self, album_id: str) -> Album:
        """Get an album by its ID.

        Args:
            album_id (str): the ID of the album to fetch

        Returns:
            Album: the album with the given ID
        """

        if hasattr(self, "_albums"):
            for album in self._albums:
                if album.id == album_id:
                    return album

        return Album.from_json_response(
            self.get_json_response(f"/albums/{album_id}"),
            google_client=self,
        )

    def get_album_by_name(self, album_name: str) -> Album:
        """Gets an album definition from the Google API based on the album name.

        Args:
            album_name (str): the name of the album to find

        Returns:
            Album: an Album instance, with all metadata etc.

        Raises:
            FileNotFoundError: if the client can't find an album with the correct name
        """

        LOGGER.info("Getting metadata for album `%s`", album_name)
        for album in self.albums:
            if album.title == album_name:
                return album

        raise FileNotFoundError(f"Unable to find album with name {album_name}")

    @property
    def albums(self) -> list[Album]:
        """Lists all albums in the active Google account.

        Returns:
            list: a list of Album instances
        """

        if not hasattr(self, "_albums"):
            self._albums = [
                Album.from_json_response(item, google_client=self)
                for item in self.get_items(
                    f"{self.BASE_URL}/albums",
                    list_key="albums",
                )
            ]

        return self._albums


Album.update_forward_refs()
MediaItem.update_forward_refs()
