"""Custom client for interacting with Google's Photos API"""
from __future__ import annotations

from datetime import datetime
from enum import Enum, auto
from json import dumps
from logging import Logger
from os import getenv
from os.path import isfile, join
from typing import Iterable, TypedDict, cast

from requests import get

from wg_utilities.clients._google import GoogleClient, _GoogleEntityInfo
from wg_utilities.functions import force_mkdir, user_data_dir

LOCAL_MEDIA_DIRECTORY = getenv(
    "LOCAL_MEDIA_DIRECTORY", user_data_dir(file_name="media_downloads")
)


class _SharedAlbumOptionsInfo(TypedDict):
    isCollaborative: bool
    isCommentable: bool


class _ShareInfoInfo(TypedDict):
    isJoinable: bool
    isJoined: bool
    isOwned: bool
    shareableUrl: str
    sharedAlbumOptions: _SharedAlbumOptionsInfo
    shareToken: str


class _AlbumInfo(_GoogleEntityInfo):
    coverPhotoBaseUrl: str
    coverPhotoMediaItemId: str
    id: str
    isWriteable: bool
    mediaItemsCount: str
    productUrl: str
    shareInfo: _ShareInfoInfo
    title: str


class _MediaItemMetadataInfo(TypedDict):
    creationTime: str
    height: str
    width: str


class _MediaItemInfo(_GoogleEntityInfo):
    baseUrl: str
    contributorInfo: dict[str, str]
    description: str
    filename: str
    id: str
    mediaMetadata: _MediaItemMetadataInfo
    mimeType: str
    productUrl: str


class MediaType(Enum):
    """Enum for all potential media types"""

    IMAGE = auto()
    VIDEO = auto()
    UNKNOWN = auto()


class Album:
    """Class for Google Photos albums and their metadata/content

    Args:
        json (dict): the JSON which is returned from the Google Photos API when
         describing the album
        google_client (GooglePhotosClient): an active Google client which can be used to
         list media items

    """

    def __init__(self, json: _AlbumInfo, google_client: GooglePhotosClient):
        self.json = json
        self._media_items: list[MediaItem] | None = None

        self.google_client = google_client

    @property
    def media_items(self) -> list[MediaItem]:
        # noinspection GrazieInspection
        """Lists all media items in the album

        Returns:
            list: a list of MediaItem instances, representing the contents of the album
        """

        if not self._media_items:
            self._media_items = self.google_client.get_album_contents(self.id)

        return self._media_items

    @property
    def title(self) -> str | None:
        """
        Returns:
            str: the title of the album
        """
        return self.json.get("title")

    @property
    def id(self) -> str:
        """
        Returns:
            str: the ID of the album
        """
        return self.json["id"]

    @property
    def media_items_count(self) -> int:
        """
        Returns:
            int: the number of media items within the album
        """
        return int(self.json.get("mediaItemsCount", "-1"))

    def __str__(self) -> str:
        return f"{self.title}: {self.id}"


class MediaItem:
    """Class for representing a MediaItem and its metadata/content

    Args:
        json (dict): the JSON returned from the Google Photos API, which describes
        this media item
    """

    def __init__(self, json: _MediaItemInfo):
        self.json: _MediaItemInfo = json

        try:
            self.creation_datetime = datetime.strptime(
                json["mediaMetadata"]["creationTime"],
                "%Y-%m-%dT%H:%M:%S.%fZ",
            )
        except ValueError:
            self.creation_datetime = datetime.strptime(
                json["mediaMetadata"]["creationTime"], "%Y-%m-%dT%H:%M:%SZ"
            )

        self.local_path = join(
            LOCAL_MEDIA_DIRECTORY,
            self.creation_datetime.strftime("%Y/%m/%d"),
            json["filename"],
        )

    def download(
        self,
        width_override: int | None = None,
        height_override: int | None = None,
        force_download: bool = False,
    ) -> str:
        """Download the media item to local storage. The width/height overrides do
        not apply to videos

        Args:
            width_override (int): the width override to use when downloading the file
            height_override (int): the height override to use when downloading the file
            force_download (bool): flag for forcing a download, even if it exists
             locally already

         Returns:
             str: the path to the downloaded file (self.local_path)
        """
        if not self.stored_locally or force_download:
            width = width_override or self.width
            height = height_override or self.height

            # LOGGER.debug("Downloading %s (%sx%s)", self.filename, width, height)

            param_str = {
                MediaType.IMAGE: f"=w{width}-h{height}",
                MediaType.VIDEO: "=dv",
            }.get(self.media_type, "")

            with open(force_mkdir(self.local_path, path_is_file=True), "wb") as fout:
                fout.write(get(f"{self.json['baseUrl']}{param_str}").content)

        return self.local_path

    @property
    def bytes(self) -> bytes:
        """Opens the local copy of the file (downloading it first if necessary) and
        reads the binary content of it

        Returns:
            bytes: the binary content of the file
        """
        if not self.stored_locally:
            self.download()

        with open(self.local_path, "rb") as fin:
            bytes_content = fin.read()

        return bytes_content

    @property
    def stored_locally(self) -> bool:
        """
        Returns:
            bool: flag for if the file exists locally
        """
        return isfile(self.local_path)

    @property
    def filename(self) -> str | None:
        """
        Returns:
            str: the media item's file name
        """
        return self.json.get("filename")

    @property
    def height(self) -> int:
        """
        Returns:
            int: the media item's height
        """
        return int(self.json.get("mediaMetadata", {}).get("height", "-1"))

    @property
    def width(self) -> int:
        """
        Returns:
            int: the media item's width
        """
        return int(self.json.get("mediaMetadata", {}).get("width", "-1"))

    @property
    def media_type(self) -> MediaType:
        """Determines the media item's file type from the JSON

        Returns:
            MediaType: the media type (image, video, etc.) for this item
        """

        if "image" in (mime_type := self.json.get("mimeType", "")):
            return MediaType.IMAGE

        if "video" in mime_type:
            return MediaType.VIDEO

        return MediaType.UNKNOWN

    def __str__(self) -> str:
        return dumps(self.json, indent=4, default=str)


class GooglePhotosClient(GoogleClient):
    """Custom client for interacting with the Google Photos API

    See Also:
        GoogleClient: the base Google client, used for authentication and common
         functions
    """

    BASE_URL = "https://photoslibrary.googleapis.com/v1"

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
            project,
            scopes,
            client_id_json_path,
            creds_cache_path,
            access_token_expiry_threshold,
            logger,
        )

        self._albums: list[Album] | None = None

    def get_album_contents(self, album_id: str) -> list[MediaItem]:
        # noinspection GrazieInspection
        """Gets the contents of a given album in Google Photos

        Args:
            album_id (str): the ID of the album which we want the contents of

        Returns:
            list: a list of MediaItem instances, representing each item in the album
        """

        return [
            MediaItem(item)
            for item in cast(
                Iterable[_MediaItemInfo],
                self._list_items(
                    self.session.post,
                    f"{self.BASE_URL}/mediaItems:search",
                    "mediaItems",
                    params={"albumId": album_id},
                ),
            )
        ]

    def get_album_from_name(self, album_name: str) -> Album:
        """Gets an album definition from the Google API based on the album name

        Args:
            album_name (str): the name of the album to find

        Returns:
            Album: an Album instance, with all metadata etc.

        Raises:
            FileNotFoundError: if the client can't find an album with the correct name
        """

        self.logger.info("Getting metadata for album `%s`", album_name)
        for album in self.albums:
            if album.title == album_name:
                return album

        raise FileNotFoundError(f"Unable to find album with name {album_name}")

    @property
    def albums(self) -> list[Album]:
        """Lists all albums in the active Google account

        Returns:
            list: a list of Album instances
        """

        if not self._albums:
            self._albums = [
                Album(item, self)
                for item in cast(
                    Iterable[_AlbumInfo],
                    self._list_items(
                        self.session.get,
                        f"{self.BASE_URL}/albums",
                        "albums",
                    ),
                )
            ]

        return self._albums
