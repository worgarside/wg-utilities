"""Custom client for interacting with Google's Photos API"""

from datetime import datetime
from enum import Enum, auto
from json import dumps
from os import getenv
from os.path import join, isfile

from requests import get

from wg_utilities.clients._generic import GoogleClient
from wg_utilities.functions import user_data_dir, force_mkdir

LOCAL_MEDIA_DIRECTORY = getenv(
    "LOCAL_MEDIA_DIRECTORY", user_data_dir(file_name="media_downloads")
)


class MediaType(Enum):
    """Enum for all potential media types"""

    IMAGE = auto()
    VIDEO = auto()


class Album:
    """Class for Google Photos albums and their metadata/content

    Args:
        json (dict): the JSON which is returned from the Google Photos API when
         describing the album
        google_client (GooglePhotosClient): an active Google client which can be used to
         list media items

    """

    def __init__(self, json, google_client=None):
        self.json = json
        self._media_items = None

        self.google_client = google_client

    @property
    def media_items(self):
        # noinspection GrazieInspection
        """Lists all media items in the album

        Returns:
            list: a list of MediaItem instances, representing the contents of the album
        """

        if not self._media_items:
            self._media_items = self.google_client.get_album_contents(self.id)

        return self._media_items

    @property
    def title(self):
        """
        Returns:
            str: the title of the album
        """
        return self.json.get("title")

    @property
    def id(self):
        """
        Returns:
            str: the ID of the album
        """
        return self.json.get("id")

    @property
    def media_items_count(self):
        """
        Returns:
            int: the number of media items within the album
        """
        return int(self.json.get("mediaItemsCount", "-1"))

    def __str__(self):
        return f"{self.title}: {self.id}"


class MediaItem:
    """Class for representing a MediaItem and its metadata/content

    Args:
        json (dict): the JSON returned from the Google Photos API, which describes
        this media item
    """

    def __init__(self, json):
        self.json = json

        try:
            self.creation_datetime = datetime.strptime(
                json.get("mediaMetadata", {}).get("creationTime"),
                "%Y-%m-%dT%H:%M:%S.%fZ",
            )
        except ValueError:
            self.creation_datetime = datetime.strptime(
                json.get("mediaMetadata", {}).get("creationTime"), "%Y-%m-%dT%H:%M:%SZ"
            )

        self.local_path = join(
            LOCAL_MEDIA_DIRECTORY,
            self.creation_datetime.strftime("%Y/%m/%d"),
            json["filename"],
        )

    def download(self, width_override=None, height_override=None, force_download=False):
        """Download the media item to local storage. The width/height overrides do
        not apply to videos

        Args:
            width_override (int): the width override to use when downloading the file
            height_override (int): the height override to use when downloading the file
            force_download (bool): flag for forcing a download, even if it exists
             locally already
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

    @property
    def bytes(self):
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
    def stored_locally(self):
        """
        Returns:
            bool: flag for if the file exists locally
        """
        return isfile(self.local_path)

    @property
    def filename(self):
        """
        Returns:
            str: the media item's file name
        """
        return self.json.get("filename")

    @property
    def height(self):
        """
        Returns:
            int: the media item's height
        """
        return int(self.json.get("mediaMetadata", {}).get("height", "-1"))

    @property
    def width(self):
        """
        Returns:
            int: the media item's width
        """
        return int(self.json.get("mediaMetadata", {}).get("width", "-1"))

    @property
    def media_type(self):
        """Determines the media item's file type from the JSON

        Returns:
            MediaType: the media type (image, video, etc.) for this item
        """
        mime_type = self.json.get("mimeType", "")

        return {
            "image" in mime_type: MediaType.IMAGE,
            "video" in mime_type: MediaType.VIDEO,
        }.get(True)

    def __str__(self):
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
        project,
        scopes=None,
        client_id_json_path=None,
        creds_cache_path=None,
        access_token_expiry_threshold=60,
        logger=None,
    ):
        super().__init__(
            project,
            scopes,
            client_id_json_path,
            creds_cache_path,
            access_token_expiry_threshold,
            logger,
        )

        self._albums = None

    def get_album_contents(self, album_id):
        # noinspection GrazieInspection
        """Gets the contents of a given album in Google Photos

        Args:
            album_id (str): the ID of the album which we want the contents of

        Returns:
            list: a list of MediaItem instances, representing each item in the album
        """

        return [
            MediaItem(item)
            for item in self._list_items(
                self.session.post,
                f"{self.BASE_URL}/mediaItems:search",
                "mediaItems",
                params={"albumId": album_id},
            )
        ]

    def get_album_from_name(self, album_name):
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
    def albums(self):
        """Lists all albums in the active Google account

        Returns:
            list: a list of Album instances
        """

        if not self._albums:
            self._albums = [
                Album(res, self)
                for res in self._list_items(
                    self.session.get,
                    f"{self.BASE_URL}/albums",
                    "albums",
                )
            ]

        return self._albums
