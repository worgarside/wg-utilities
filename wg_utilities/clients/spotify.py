# pylint: disable=too-many-lines
"""Custom client for interacting with Spotify's Web API."""
from __future__ import annotations

from collections.abc import Callable, Collection, Iterator
from datetime import date, datetime, timedelta
from enum import Enum
from http import HTTPStatus
from json import JSONDecodeError, dumps
from logging import DEBUG, getLogger
from pathlib import Path
from re import sub
from typing import Any, Literal, TypedDict
from urllib.parse import urlencode

from pydantic import BaseModel, Extra
from requests import HTTPError, Response, delete, get, post, put
from spotipy import CacheFileHandler, SpotifyOAuth
from typing_extensions import NotRequired

from wg_utilities.functions import chunk_list

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


class AlbumType(Enum):
    """Enum for the different types of album Spotify supports."""

    SINGLE = "single"
    ALBUM = "album"
    COMPILATION = "compilation"


class Device(BaseModel, extra=Extra.allow):
    # pylint: disable=too-few-public-methods
    """Model for a Spotify device."""

    id: str
    is_active: bool
    is_private_session: bool
    is_restricted: bool
    name: str
    type: str
    volume_percent: int


class _SpotifyEntityInfo(TypedDict):
    href: str
    id: str
    uri: str
    external_urls: dict[Literal["spotify"], str]
    description: NotRequired[str]
    name: NotRequired[str]


class _AlbumTracksItemInfo(TypedDict):
    href: str
    items: list[_TrackInfo]
    limit: int
    next: str | None
    offset: int
    previous: str | None
    total: int


class _AlbumInfo(_SpotifyEntityInfo):
    album_type: Literal["album", "single", "compilation"]
    artists: list[_ArtistInfo]
    available_markets: list[str]
    images: list[dict[str, str | int]]
    release_date: str
    release_date_precision: Literal["year", "month", "day", None]
    restrictions: NotRequired[dict[str, str]]
    total_tracks: int
    tracks: NotRequired[_AlbumTracksItemInfo]
    type: Literal["album"]


class _ArtistInfo(_SpotifyEntityInfo):
    followers: NotRequired[dict[str, str | None | int]]
    genres: NotRequired[list[str]]
    images: NotRequired[list[dict[str, str | int]]]
    popularity: NotRequired[int]
    type: Literal["artist"]


class _PlaylistInfo(_SpotifyEntityInfo):
    collaborative: bool
    followers: dict[str, str | None | int]
    images: list[dict[str, str | int]]
    owner: _UserInfo
    public: bool
    snapshot_id: str
    tracks: list[_TrackInfo]
    type: Literal["playlist"]


class _TrackInfo(_SpotifyEntityInfo):
    album: _AlbumInfo
    artists: list[_ArtistInfo]
    available_markets: list[str]
    disc_number: int
    duration_ms: int
    explicit: bool
    external_ids: dict[str, str]
    is_local: bool
    is_playable: NotRequired[str]
    linked_from: NotRequired[_TrackInfo]
    popularity: int
    preview_url: str | None
    restrictions: NotRequired[str]
    track_number: int
    type: Literal["track"]


class _UserInfo(_SpotifyEntityInfo):
    display_name: str
    country: str
    email: str
    explicit_content: dict[str, bool]
    followers: dict[str, int | None]
    images: list[dict[str, str | None]]
    product: str
    type: str


class _TrackAudioFeaturesInfo(TypedDict):
    acousticness: float
    analysis_url: str
    danceability: float
    duration_ms: int
    energy: float
    id: str
    instrumentalness: float
    key: int
    liveness: float
    loudness: float
    mode: int
    speechiness: float
    tempo: float
    time_signature: int
    track_href: str
    type: Literal["audio_features"]
    uri: str
    valence: float


class _GetItemsFromUrlDataInfo(TypedDict):
    items: list[
        (
            _PlaylistInfo
            | _TrackInfo
            | _AlbumInfo
            | _ArtistInfo
            | list[dict[Literal["album"], _AlbumInfo]]
        )
    ]
    next: str | None
    total: int
    cursors: dict[Literal["after"], str] | None
    limit: int
    href: str


class SpotifyEntity:
    """Parent class for all Spotify entities (albums, artists, etc.).

    Args:
        json (dict): the JSON returned from the Spotify Web API which defines the
         entity
        spotify_client (SpotifyClient): a Spotify client, usually the one which
         retrieved this entity from the API
        metadata (dict): any extra metadata about this entity
    """

    json: _SpotifyEntityInfo

    def __init__(
        self,
        json: _SpotifyEntityInfo,
        spotify_client: SpotifyClient,
        metadata: dict[str, Any] | None = None,
    ):
        self.json = json
        self._spotify_client = spotify_client
        self.metadata = metadata or {}

    @property
    def pretty_json(self) -> str:
        """Return a pretty-printed version of the JSON for this entity.

        Returns:
            str: a "pretty" version of the JSON, used for debugging etc.
        """
        return dumps(self.json, indent=2, default=str)

    @property
    def description(self) -> str:
        """Description of the entity.

        Returns:
            str: the description of the entity
        """
        return self.json.get("description", "")

    @property
    def endpoint(self) -> str | None:
        """Endpoint of the entity.

        Returns:
            str: A link to the Web API endpoint providing full details of the entity
        """
        return self.json.get("href")

    @property
    def id(self) -> str:
        """ID of the entity.

        Returns:
            str: The base-62 identifier for the entity
        """
        return self.json["id"]

    @property
    def name(self) -> str:
        """Name of the entity.

        Returns:
            str: the name of the entity
        """
        return self.json.get("name", "")

    @property
    def uri(self) -> str:
        """Spotify URI for the entity.

        Returns:
            str: the Spotify URI of this entity
        """

        return self.json.get("uri", f"spotify:{type(self).__name__.lower()}:{self.id}")

    @property
    def url(self) -> str:
        """URL of the entity.

        Returns:
            str: the URL of this entity
        """
        return self.json.get("external_urls", {}).get(
            "spotify",
            f"https://open.spotify.com/{type(self).__name__.lower()}/{self.id}",
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SpotifyEntity):
            return NotImplemented
        return self.id == other.id

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SpotifyEntity):
            return NotImplemented
        return (self.name or self.id).lower() > (other.name or other.id).lower()

    def __hash__(self) -> int:
        return hash(repr(self))

    def __lt__(self, other: SpotifyEntity) -> bool:
        if not isinstance(other, SpotifyEntity):
            return NotImplemented
        return (self.name or self.id).lower() < (other.name or other.id).lower()

    def __repr__(self) -> str:
        return f'{type(self).__name__}(id="{self.id}", name="{self.name}")'

    def __str__(self) -> str:
        return self.name or f"{type(self).__name__} ({self.id})"


class User(SpotifyEntity):
    """A Spotify user, usually just the current user."""

    json: _UserInfo

    def __init__(
        self,
        json: _UserInfo,
        *,
        spotify_client: SpotifyClient,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(json=json, spotify_client=spotify_client, metadata=metadata)

        self._albums: list[Album]
        self._artists: list[Artist]
        self._playlists: list[Playlist]
        self._top_artists: tuple[Artist, ...]
        self._top_tracks: tuple[Track, ...]
        self._tracks: list[Track]

    def get_playlists_by_name(
        self, name: str, return_all: bool = False
    ) -> list[Playlist] | Playlist | None:
        """Gets Playlist instance(s) which have the given name.

        Args:
            name (str): the name of the target playlist(s)
            return_all (bool): playlist names aren't unique - but most people keep them
             unique within their own collection of playlists. This boolean can be used
             to return either a list of all matching playlists, or just the single
             found playlist

        Returns:
            Union([list, Playlist]): the matched playlist(s)
        """

        matched_playlists = filter(
            lambda p: p.name.lower() == name.lower(), self.playlists
        )

        # Return a list of all matches
        if return_all:
            return sorted(matched_playlists)

        try:
            return next(matched_playlists)
        except StopIteration:
            return None

    def get_recently_liked_tracks(
        self, track_limit: int = 100, *, day_limit: float | None = None
    ) -> list[Track]:
        """Gets a list of songs which were liked by the current user in the past N days.

        Args:
            track_limit (int): the number of tracks to return
            day_limit (float): the number of days (N) to go back in time for

        Returns:
            list: a list of Track instances
        """

        kwargs: dict[str, int | Callable[[Any], bool]] = {"hard_limit": track_limit}

        if isinstance(day_limit, (float, int)):

            def _limit_func(item: dict[str, Any]) -> bool:
                return bool(
                    datetime.strptime(
                        item["added_at"], self._spotify_client.DATETIME_FORMAT
                    )
                    < (
                        datetime.utcnow()
                        - timedelta(days=day_limit)  # type: ignore[arg-type]
                    )
                )

            kwargs["limit_func"] = _limit_func

        return [
            Track(
                item["track"],  # type: ignore[call-overload,typeddict-item]
                spotify_client=self._spotify_client,
                metadata={
                    "saved_at": datetime.strptime(
                        item["added_at"],  # type: ignore[call-overload,typeddict-item]
                        self._spotify_client.DATETIME_FORMAT,
                    )
                },
            )
            for item in self._spotify_client.get_items_from_url(
                "/me/tracks", **kwargs  # type: ignore[arg-type]
            )
        ]

    def save(self, entity: Album | Artist | Playlist | Track) -> None:
        """Save an entity to the user's library.

        Args:
            entity (Album|Artist|Playlist|Track): the entity to save

        Raises:
            TypeError: if the entity is not of a supported type
        """

        if isinstance(entity, Album):
            url = f"{self._spotify_client.BASE_URL}/me/albums"
            params = {"ids": entity.id}
        elif isinstance(entity, Artist):
            url = f"{self._spotify_client.BASE_URL}/me/following"
            params = {"type": "artist", "ids": entity.id}
        elif isinstance(entity, Playlist):
            url = f"{self._spotify_client.BASE_URL}/playlists/{entity.id}/followers"
            params = {"ids": self.id}
        elif isinstance(entity, Track):
            url = f"{self._spotify_client.BASE_URL}/me/tracks"
            params = {"ids": entity.id}
        else:
            raise TypeError(
                f"Cannot save entity of type `{type(entity).__name__}`. "
                f"Must be one of: Album, Artist, Playlist, Track"
            )

        res = put(
            url,
            params=params,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._spotify_client.access_token}",
                "Host": "api.spotify.com",
            },
        )
        res.raise_for_status()

    def unsave(self, entity: Album | Artist | Playlist | Track) -> None:
        """Remove an entity from the user's library.

        Args:
            entity (Album|Artist|Playlist|Track): the entity to remove

        Raises:
            TypeError: if the entity is not of a supported type
        """

        if isinstance(entity, Album):
            url = f"{self._spotify_client.BASE_URL}/me/albums"
            params = {"ids": entity.id}
        elif isinstance(entity, Artist):
            url = f"{self._spotify_client.BASE_URL}/me/following"
            params = {"type": "artist", "ids": entity.id}
        elif isinstance(entity, Playlist):
            url = f"{self._spotify_client.BASE_URL}/playlists/{entity.id}/followers"
            params = {"ids": self.id}
        elif isinstance(entity, Track):
            url = f"{self._spotify_client.BASE_URL}/me/tracks"
            params = {"ids": entity.id}
        else:
            raise TypeError(
                f"Cannot unsave entity of type `{type(entity).__name__}`. "
                f"Must be one of: Album, Artist, Playlist, Track"
            )

        res = delete(
            url,
            params=params,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._spotify_client.access_token}",
                "Host": "api.spotify.com",
            },
        )
        if res.status_code != HTTPStatus.BAD_REQUEST:
            res.raise_for_status()

    @property
    def albums(self) -> list[Album]:
        """List of albums in the user's library.

        Returns:
            list: a list of albums owned by the current user
        """

        if not hasattr(self, "_albums"):
            self._albums = [
                Album(
                    item["album"],  # type: ignore[call-overload,typeddict-item]
                    spotify_client=self._spotify_client,
                )
                for item in self._spotify_client.get_items_from_url("/me/albums")
            ]

        return self._albums

    @property
    def artists(self) -> list[Artist]:
        """List of artists in the user's library.

        Returns:
            list: a list of artists owned by the current user
        """

        if not hasattr(self, "_artists"):
            self._artists = [
                Artist(
                    artist_json,  # type: ignore[arg-type]
                    spotify_client=self._spotify_client,
                )
                for artist_json in self._spotify_client.get_items_from_url(
                    "/me/following",
                    params={
                        "type": "artist",
                    },
                    top_level_key="artists",
                )
            ]

        return self._artists

    @property
    def current_track(self) -> Track | None:
        """Gets the currently playing track for the given user.

        Returns:
            Track: the track currently being listened to
        """

        res = self._spotify_client.get_json_response("/me/player/currently-playing")

        if item := res.get("item"):
            return Track(
                item, spotify_client=self._spotify_client  # type: ignore[arg-type]
            )

        return None

    @property
    def current_playlist(self) -> Playlist | None:
        """Gets the current playlist for the given user.

        Returns:
            Playlist: the playlist currently being listened to
        """

        res = self._spotify_client.get_json_response("/me/player/currently-playing")

        if (context := res.get("context", {})).get(  # type: ignore[attr-defined]
            "type"
        ) == "playlist":
            return self._spotify_client.get_playlist_by_id(
                context["uri"].split(":")[-1]  # type: ignore[index]
            )

        return None

    @property
    def devices(self) -> list[Device]:
        """Devices that the user currently has access to.

        Returns:
            list[Device]: a list of devices available to the user
        """
        return [
            Device.parse_obj(device_json)
            for device_json in self._spotify_client.get_items_from_url(
                "/me/player/devices", list_key="devices"
            )
        ]

    @property
    def name(self) -> str:
        """Display name of the user.

        Returns:
            str: the display name of the User
        """

        return self.json["display_name"]

    @property
    def playlists(self) -> list[Playlist]:
        """Playlists owned by the current user.

        Returns:
            list: a list of playlists owned by the current user
        """

        if not hasattr(self, "_playlists"):
            item: _PlaylistInfo
            self._playlists = [
                Playlist(
                    item, spotify_client=self._spotify_client  # type: ignore[arg-type]
                )
                for item in self._spotify_client.get_items_from_url("/me/playlists")
                if item["owner"]["id"]  # type: ignore[call-overload,typeddict-item]
                == self.id
            ]

        return self._playlists

    @property
    def top_artists(self) -> tuple[Artist, ...]:
        """Top artists for the user.

        Returns:
            tuple[Artist, ...]: the top artists for the user
        """

        if not hasattr(self, "_top_artists"):
            self._top_artists = tuple(
                Artist(
                    artist_json,  # type: ignore[arg-type]
                    spotify_client=self._spotify_client,
                )
                for artist_json in self._spotify_client.get_items_from_url(
                    "/me/top/artists", params={"time_range": "short_term"}
                )
            )

        return self._top_artists

    @property
    def top_tracks(self) -> tuple[Track, ...]:
        """The top tracks for the user.

        Returns:
            tuple[Track]: the top tracks for the user
        """
        if not hasattr(self, "_top_tracks"):
            self._top_tracks = tuple(
                Track(
                    track_json,  # type: ignore[arg-type]
                    spotify_client=self._spotify_client,
                )
                for track_json in self._spotify_client.get_items_from_url(
                    "/me/top/tracks", params={"time_range": "short_term"}
                )
            )

        return self._top_tracks

    @property
    def tracks(self) -> list[Track]:
        """Liked Songs.

        Returns:
            list: a list of tracks owned by the current user
        """

        if not hasattr(self, "_tracks"):
            self._tracks = [
                Track(
                    item["track"],  # type: ignore[call-overload,typeddict-item]
                    spotify_client=self._spotify_client,
                )
                for item in self._spotify_client.get_items_from_url("/me/tracks")
            ]

        return self._tracks

    def reset_properties(
        self,
        property_names: list[
            Literal[
                "albums",
                "artists",
                "playlists",
                "top_artists",
                "top_tracks",
                "tracks",
            ]
        ]
        | None = None,
    ) -> None:
        """Resets all list properties."""

        property_names = property_names or [
            "albums",
            "artists",
            "playlists",
            "top_artists",
            "top_tracks",
            "tracks",
        ]

        for prop_name in property_names:
            if hasattr(self, attr_name := f"_{prop_name}"):
                delattr(self, attr_name)


class Track(SpotifyEntity):
    """A track on Spotify."""

    json: _TrackInfo

    def __init__(
        self,
        json: _TrackInfo,
        *,
        spotify_client: SpotifyClient,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(json=json, spotify_client=spotify_client, metadata=metadata)
        self._artists: list[Artist] | None = None
        self._audio_features: _TrackAudioFeaturesInfo

    @property
    def album(self) -> Album:
        """Track's parent album.

        Returns:
            Album: the album which this track is from
        """

        return Album(self.json["album"], spotify_client=self._spotify_client)

    @property
    def artists(self) -> list[Artist]:
        """Artists who contributed to the track.

        Returns:
            list(Artist): a list of the artists who contributed to this track
        """

        if self._artists is None:
            self._artists = [
                Artist(item, spotify_client=self._spotify_client)
                for item in self.json.get("artists", [])
            ]

        return self._artists

    @property
    def audio_features(self) -> _TrackAudioFeaturesInfo:
        """Audio features of the track.

        Returns:
            dict: the JSON response from the Spotify /audio-features endpoint

        Raises:
            HTTPError: if `get_json_response` throws a HTTPError for a non-200/404
                response
        """
        if not hasattr(self, "_audio_features"):
            try:
                self._audio_features = (
                    self._spotify_client.get_json_response(  # type: ignore[assignment]
                        f"/audio-features/{self.id}"
                    )
                )
            except HTTPError as exc:
                if exc.response.status_code == HTTPStatus.NOT_FOUND:
                    self._audio_features = {}  # type: ignore[typeddict-item]
                else:
                    raise

        return self._audio_features

    @property
    def is_local(self) -> bool:
        """Whether the track is a local file.

        Returns:
            bool: whether the track is a local file
        """
        return self.json["is_local"]

    @property
    def release_date(self) -> date | str | None:
        """Album release date.

        Returns:
            date: the date the track's album was first released
        """
        return self.album.release_date

    @property
    def tempo(self) -> float | None:
        """Tempo of the track in BPM.

        Returns:
            float: the tempo of the track, in BPM
        """
        return self.audio_features.get("tempo")


class Artist(SpotifyEntity):
    """An artist on Spotify."""

    json: _ArtistInfo

    def __init__(self, json: _ArtistInfo, *, spotify_client: SpotifyClient):
        super().__init__(json=json, spotify_client=spotify_client)
        self._albums: list[Album]

    @property
    def albums(self) -> list[Album]:
        """Albums by this artist.

        Returns:
            list: A list of albums this artist has contributed to
        """
        if not hasattr(self, "_albums"):
            self._albums = [
                Album(
                    item, spotify_client=self._spotify_client  # type: ignore[arg-type]
                )
                for item in self._spotify_client.get_items_from_url(
                    f"/artists/{self.id}/albums"
                )
            ]

        return self._albums


class Album(SpotifyEntity):
    """An album on Spotify."""

    json: _AlbumInfo

    def __init__(self, json: _AlbumInfo, *, spotify_client: SpotifyClient):
        super().__init__(json, spotify_client)
        self._artists: list[Artist]
        self._tracks: list[Track]

    @property
    def artists(self) -> list[Artist]:
        """Featured artists in Album.

        Returns:
            list(Artist): a list of the artists who contributed to this track
        """

        if not hasattr(self, "_artists"):
            self._artists = [
                Artist(item, spotify_client=self._spotify_client)
                for item in self.json.get("artists", [])
            ]

        return self._artists

    @property
    def release_date(self) -> date | str | None:
        """Initial release date.

        Returns:
            date: the date the album was first released
        """
        if (
            release_date_str := self.json.get("release_date")
        ) is not None and self.release_date_precision:
            dttm_format = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}[
                self.release_date_precision
            ]

            return datetime.strptime(release_date_str, dttm_format).date()

        return release_date_str

    @property
    def release_date_precision(self) -> Literal["year", "month", "day", None]:
        """Release date precision.

        Returns:
            str: the precision with which release_date value is known
        """
        return self.json.get("release_date_precision")

    @property
    def tracks(self) -> list[Track]:
        """List of tracks on the album.

        Returns:
            list: a list of tracks on this album
        """

        if not hasattr(self, "_tracks"):
            self._tracks = [
                Track(item, spotify_client=self._spotify_client)
                for item in self.json.get("tracks", {}).get("items", [])
            ]

            # May as well get the items in the album description already, then can get
            # the rest if we need to
            if next_url := self.json.get("tracks", {}).get("next"):
                self._tracks.extend(
                    Track(
                        # FIXME I don't think this works?? it needs to be item["track"]
                        item,  # type: ignore[arg-type]
                        spotify_client=self._spotify_client,
                    )
                    for item in self._spotify_client.get_items_from_url(next_url)
                )

        return self._tracks

    @property
    def type(self) -> AlbumType:
        """Album type.

        Returns:
            AlbumType: the type of album this is
        """

        return AlbumType[self.json.get("album_type", "").upper()]


class Playlist(SpotifyEntity):
    """A Spotify playlist."""

    json: _PlaylistInfo

    def __init__(
        self,
        json: _PlaylistInfo,
        *,
        spotify_client: SpotifyClient,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(json=json, spotify_client=spotify_client, metadata=metadata)
        self._tracks: list[Track]

    @property
    def is_collaborative(self) -> bool:
        """Whether the playlist is collaborative.

        Returns:
            bool: whether the playlist is collaborative
        """
        return self.json["collaborative"]

    @property
    def is_public(self) -> bool:
        """Whether the playlist is public.

        Returns:
            bool: whether the playlist is public
        """
        return self.json["public"]

    @property
    def owner(self) -> User:
        """Playlist owner.

        Returns:
            User: the Spotify user who owns this playlist
        """

        return User(self.json["owner"], spotify_client=self._spotify_client)

    @property
    def tracks(self) -> list[Track]:
        """Tracks in the playlist.

        Returns:
            list: a list of tracks in this playlist
        """

        if not hasattr(self, "_tracks"):
            self._tracks = [
                Track(
                    item["track"],  # type: ignore[call-overload,typeddict-item]
                    spotify_client=self._spotify_client,
                )
                for item in self._spotify_client.get_items_from_url(
                    f"/playlists/{self.id}/tracks"
                )
                if "track" in item.keys()  # type: ignore[union-attr]
            ]

        return self._tracks

    def __contains__(self, track: Track) -> bool:
        return track in self.tracks

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Playlist):
            return NotImplemented

        if self == other:
            return False

        return (self.name.lower(), self.id.lower()) > (
            other.name.lower(),
            other.id.lower(),
        )

    def __iter__(self) -> Iterator[Track]:
        return iter(self.tracks)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Playlist):
            return NotImplemented

        if self == other:
            return False

        return (self.name.lower(), self.id.lower()) < (
            other.name.lower(),
            other.id.lower(),
        )


class SpotifyClient:
    """Custom client for interacting with Spotify's Web API.

    For authentication purposes either an already-instantiated OAuth manager or the
    relevant credentials must be provided

    Args:
        client_id (str): the application's client ID
        client_secret (str): the application's client secret
        redirect_uri (str): the redirect URI for the applications
        scope (list): either a list of scopes or comma separated string of scopes.
        oauth_manager (SpotifyOAuth): an already-instantiated OAuth manager which
         provides authentication for all API interactions
        log_requests (bool): flag for choosing if to log all requests made
        creds_cache_path (str): path at which to save cached credentials
    """

    BASE_URL = "https://api.spotify.com/v1"
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    ALL_SCOPES = [
        "ugc-image-upload",
        "user-read-recently-played",
        "user-top-read",
        "user-read-playback-position",
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "app-remote-control",
        "streaming",
        "playlist-modify-public",
        "playlist-modify-private",
        "playlist-read-private",
        "playlist-read-collaborative",
        "user-follow-modify",
        "user-follow-read",
        "user-library-modify",
        "user-library-read",
        "user-read-email",
        "user-read-private",
    ]

    SEARCH_TYPES = (
        "album",
        "artist",
        "playlist",
        "track",
        # "show",
        # "episode",
    )

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str = "http://localhost:8080",
        scope: str | list[str] | None = None,
        oauth_manager: SpotifyOAuth | None = None,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
    ):
        self.oauth_manager = oauth_manager or SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            cache_handler=CacheFileHandler(cache_path=creds_cache_path),
        )
        self.log_requests = log_requests

        self._current_user: User

    def _get(
        self,
        url: str,
        params: None | dict[str, str | float | int | bool | dict[str, Any]] = None,
    ) -> Response:
        """Wrapper for GET requests which covers authentication, URL parsing, etc. etc.

        Args:
            url (str): the URL path to the endpoint (not necessarily including the
             base URL)
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            Response: the response from the HTTP request
        """

        if url.startswith("/"):
            url = f"{self.BASE_URL}{url}"

        if self.log_requests:
            LOGGER.debug("GET %s with params %s", url, dumps(params or {}, default=str))

        res = get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
                "Host": "api.spotify.com",
            },
            params=params or {},
        )

        res.raise_for_status()

        return res

    def _post(
        self,
        url: str,
        *,
        json: None
        | (dict[str, str | int | float | bool | list[str] | dict[Any, Any]]) = None,
    ) -> Response:
        """Wrapper for POST requests which covers authentication, URL parsing, etc. etc.

        Args:
            url (str): the URL path to the endpoint (not necessarily including the
             base URL)
            json (dict): the data to be passed in the HTTP request

        Returns:
            Response: the response from the HTTP request
        """

        if url.startswith("/"):
            url = f"{self.BASE_URL}{url}"

        if self.log_requests:
            LOGGER.debug("POST %s with data %s", url, dumps(json or {}, default=str))

        res = post(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            json=json or {},
        )

        res.raise_for_status()

        return res

    def get_items_from_url(
        self,
        url: str,
        params: None | (dict[str, str | int | float | bool | dict[str, Any]]) = None,
        *,
        hard_limit: int = 1000000,
        limit_func: Callable[[dict[str, Any]], bool] | None = None,
        top_level_key: str | None = None,
        list_key: str = "items",
    ) -> list[
        (
            _PlaylistInfo
            | _TrackInfo
            | _AlbumInfo
            | _ArtistInfo
            | list[
                dict[
                    str,
                    _AlbumInfo
                    | _ArtistInfo
                    | _PlaylistInfo
                    | _TrackInfo
                    | _UserInfo
                    | object,
                ]
            ]
        )
    ]:
        """Retrieve a list of items from a given URL, including pagination.

        Args:
            url (str): the API endpoint which we're listing
            params (dict): any params to pass with the API request
            hard_limit (int): a hard limit to apply to the number of items returned (as
                opposed to the "soft" limit of 50 imposed by the API)
            limit_func (Callable): a function which is used to evaluate each item in
                turn: if it returns False, the item is added to the output list; if it
                returns True then the iteration stops and the list is returned as-is
            top_level_key (str): an optional key to use when the items in the response
                are nested 1 level deeper than normal
            list_key (str): the key in the response which contains the list of items

        Returns:
            list: a list of dicts representing the Spotify items
        """

        params = params or {}
        if "limit=" not in url:
            params["limit"] = min(50, hard_limit)

        items: list[
            (
                _PlaylistInfo
                | _TrackInfo
                | _AlbumInfo
                | _ArtistInfo
                | list[dict[str, object]]
            )
        ] = []

        if params:
            url += ("?" if "?" not in url else "&") + urlencode(params)

        data: _GetItemsFromUrlDataInfo = {"next": url}  # type: ignore[typeddict-item]

        while (next_url := data.get("next")) and len(items) < hard_limit:
            # Ensure we don't bother getting more items than we need
            limit = min(50, hard_limit - len(items))
            next_url = sub(r"(?<=limit=)(\d{1,2})(?=&?)", str(limit), next_url)

            data = self.get_json_response(next_url)  # type: ignore[assignment]
            data = (
                data.get(top_level_key, {})  # type: ignore[assignment]
                if top_level_key
                else data
            )

            if limit_func is None:
                items.extend(data.get(list_key, []))  # type: ignore[arg-type]
            else:
                for item in data.get(list_key, []):  # type: ignore[attr-defined]
                    if limit_func(item):
                        return items

                    items.append(item)

        return items

    def get_json_response(
        self,
        url: str,
        params: None | (dict[str, str | int | float | bool | dict[str, Any]]) = None,
        #     pylint: disable=line-too-long
    ) -> _AlbumInfo | _ArtistInfo | _PlaylistInfo | _TrackInfo | _UserInfo | _GetItemsFromUrlDataInfo | dict[
        str, _AlbumInfo | _ArtistInfo | _PlaylistInfo | _TrackInfo | _UserInfo | object
    ]:
        """Gets a simple JSON object from a URL.

        Args:
            url (str): the API endpoint to GET
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            dict: the JSON from the response
        """
        try:
            res = self._get(url, params=params)
            if res.status_code == HTTPStatus.NO_CONTENT:
                return {}

            return res.json()  # type: ignore[no-any-return]
        except JSONDecodeError:
            return {}

    def search(
        self,
        search_term: str,
        *,
        entity_types: Collection[Literal["album", "artist", "playlist", "track"]] = (),
        get_best_match_only: bool = False,
    ) -> Artist | Playlist | Track | Album | None | dict[
        Literal["albums", "artists", "playlists", "tracks"],
        list[Album | Artist | Playlist | Track],
    ]:
        """Search Spotify for a given search term.

        Args:
            search_term (str): the term to use as the base of the search
            entity_types (str): the types of entity to search for. Must be one of
             SpotifyClient.SEARCH_TYPES
            get_best_match_only (bool): return a single entity from the top of the
             list, rather than all matches

        Returns:
            Artist | Playlist | Track | Album: a single entity if the best match flag
             is set
            dict: a dict of entities, by type

        Raises:
            ValueError: if multiple entity types have been requested but the best match
             flag is true
            ValueError: if one of entity_types is an invalid value
        """

        entity_types = entity_types or self.SEARCH_TYPES  # type: ignore[assignment]

        if get_best_match_only is True and len(entity_types) != 1:
            raise ValueError(
                "Exactly one entity type must be requested if `get_best_match_only`"
                " is True"
            )

        entity_type: Literal["artist", "playlist", "track", "album"]
        for entity_type in entity_types:
            if entity_type not in self.SEARCH_TYPES:
                raise ValueError(
                    f"""Unexpected value for entity type: '{entity_type}'. Must be"""
                    f""" one of '{"', '".join(self.SEARCH_TYPES)}'"""
                )

        res = self.get_json_response(
            "/search",
            params={
                "query": search_term,
                "type": ",".join(entity_types),
                "limit": 1 if get_best_match_only else 50,
            },
        )

        entity_instances: dict[
            Literal["albums", "artists", "playlists", "tracks"],
            list[Album | Artist | Playlist | Track],
        ] = {}

        res_entity_type: Literal["albums", "artists", "playlists", "tracks"]
        for res_entity_type, entities_json in res.items():  # type: ignore[assignment]

            instance_class: type[Album | Artist | Playlist | Track] = {
                "albums": Album,
                "artists": Artist,
                "playlists": Playlist,
                "tracks": Track,
            }[res_entity_type]

            if get_best_match_only:
                try:
                    # Take the entity off the top of the list
                    return instance_class(
                        entities_json.get("items", [])[0], spotify_client=self
                    )
                except IndexError:
                    return None

            entity_instances.setdefault(res_entity_type, []).extend(
                [
                    instance_class(entity_json, spotify_client=self)
                    for entity_json in entities_json.get(  # type: ignore[attr-defined]
                        "items", []
                    )
                ]
            )

            # Each entity type has its own type-specific next URL
            if (
                next_url := entities_json.get("next")  # type: ignore[attr-defined]
            ) is not None:
                entity_instances[res_entity_type].extend(
                    [
                        instance_class(
                            item, spotify_client=self  # type: ignore[arg-type]
                        )
                        for item in self.get_items_from_url(
                            next_url, top_level_key=res_entity_type
                        )
                    ]
                )

        return entity_instances

    @property
    def access_token(self) -> str:
        """Access token for the Spotify API.

        Returns:
            str: the web API access token
        """
        return str(self.oauth_manager.get_access_token(as_dict=False))

    @property
    def current_user(self) -> User:
        """Gets the current user's info.

        Returns:
            User: an instance of the current Spotify user
        """
        if not hasattr(self, "_current_user"):
            self._current_user = User(
                self.get_json_response(f"{self.BASE_URL}/me"),  # type: ignore[arg-type]
                spotify_client=self,
            )

        return self._current_user

    def add_tracks_to_playlist(
        self,
        tracks: list[Track],
        playlist: Playlist,
        *,
        log_responses: bool = False,
        force_add: bool = False,
        update_instance_tracklist: bool = True,
    ) -> None:
        """Add one or more tracks to a playlist.

        Args:
            tracks (list): a list of Track instances to be added to the given playlist
            playlist (Playlist): the playlist being updated
            log_responses (bool): log each individual response
            force_add (bool): flag for adding the track even if it's in the playlist
             already
            update_instance_tracklist (bool): appends the track to the Playlist's
             tracklist. Can be slow if it's a big playlist as it might have to get
             the tracklist first
        """

        tracks = [
            track
            for track in tracks
            if not track.is_local and (force_add or track not in playlist)
        ]

        for chunk in chunk_list(tracks, 100):
            res = self._post(
                f"/playlists/{playlist.id}/tracks",
                json={"uris": [t.uri for t in chunk]},
            )

            if log_responses:
                LOGGER.info(dumps(res.json()))

        if update_instance_tracklist:
            playlist.tracks.extend(tracks)

    def create_playlist(
        self,
        *,
        name: str,
        description: str = "",
        public: bool = False,
        collaborative: bool = False,
    ) -> Playlist:
        """Create a new playlist under the current user's account.

        Args:
            name (str): the name of the new playlist
            description (str): the description of the new playlist
            public (bool): determines if the playlist is publicly accessible
            collaborative (bool): allows other people to add tracks when True

        Returns:
            Playlist: an instance of the Playlist class containing the new playlist's
             metadata
        """
        res = self._post(
            f"/users/{self.current_user.id}/playlists",
            json={
                "name": name,
                "description": description,
                "public": public,
                "collaborative": collaborative,
            },
        )

        return Playlist(res.json(), spotify_client=self)

    def get_album_by_id(self, id_: str) -> Album:
        """Get an album from Spotify based on the ID.

        Args:
            id_(str): the Spotify ID which is used to find the album

        Returns:
            Album: an instantiated Album, from the API's response
        """

        return Album(
            self.get_json_response(f"/albums/{id_}"),  # type: ignore[arg-type]
            spotify_client=self,
        )

    def get_artist_by_id(self, id_: str) -> Artist:
        """Get an artist from Spotify based on the ID.

        Args:
            id_(str): the Spotify ID which is used to find the artist

        Returns:
            Artist: an instantiated Artist, from the API's response
        """

        return Artist(
            self.get_json_response(f"/artists/{id_}"),  # type: ignore[arg-type]
            spotify_client=self,
        )

    def get_playlist_by_id(self, id_: str) -> Playlist:
        """Get a playlist from Spotify based on the ID.

        Args:
            id_(str): the Spotify ID which is used to find the playlist

        Returns:
            Playlist: an instantiated Playlist, from the API's response
        """

        if hasattr(self, "_current_user") and hasattr(self.current_user, "_playlists"):
            for plist in self.current_user.playlists:
                if plist.id == id_:
                    return plist

        return Playlist(
            self.get_json_response(f"/playlists/{id_}"),  # type: ignore[arg-type]
            spotify_client=self,
        )

    def get_track_by_id(self, id_: str) -> Track:
        """Get a track from Spotify based on the ID.

        Args:
            id_(str): the Spotify ID which is used to find the track

        Returns:
            Track: an instantiated Track, from the API's response
        """

        return Track(
            self.get_json_response(f"/tracks/{id_}"),  # type: ignore[arg-type]
            spotify_client=self,
        )
