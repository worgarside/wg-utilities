"""Custom client for interacting with Spotify's Web API."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from http import HTTPStatus
from json import dumps
from logging import DEBUG, getLogger
from re import sub
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Literal,
    Self,
    TypeAlias,
    TypeVar,
    cast,
    overload,
)
from urllib.parse import urlencode

from pydantic import Field, ValidationInfo, field_validator, model_validator
from requests import HTTPError, delete, put
from typing_extensions import NotRequired, TypedDict

from wg_utilities.clients._spotify_types import (
    AlbumSummaryJson,
    AnyPaginatedResponse,
    ArtistSummaryJson,
    DeviceJson,
    Followers,
    Image,
    PaginatedResponseAlbums,
    PaginatedResponseArtists,
    PaginatedResponsePlaylists,
    PaginatedResponsePlaylistTracks,
    PaginatedResponseTracks,
    PlaylistFullJsonTracks,
    PlaylistSummaryJson,
    PlaylistSummaryJsonTracks,
    SavedItem,
    SearchResponse,
    SpotifyBaseEntityJson,
    SpotifyEntityJson,
    TrackAudioFeaturesJson,
    TrackFullJson,
    UserSummaryJson,
)
from wg_utilities.clients.oauth_client import BaseModelWithConfig, OAuthClient
from wg_utilities.functions import chunk_list

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


class ParsedSearchResponse(TypedDict):
    """The return type of `SpotifyClient.search`."""

    albums: NotRequired[list[Album]]
    artists: NotRequired[list[Artist]]
    playlists: NotRequired[list[Playlist]]
    tracks: NotRequired[list[Track]]


class AlbumType(StrEnum):
    """Enum for the different types of album Spotify supports."""

    SINGLE = "single"
    ALBUM = "album"
    COMPILATION = "compilation"


class Device(BaseModelWithConfig):
    """Model for a Spotify device."""

    id: str
    is_active: bool
    is_private_session: bool
    is_restricted: bool
    name: str
    type: str
    volume_percent: int


class TrackAudioFeatures(BaseModelWithConfig):
    """Audio feature information for a single track."""

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


SJ = TypeVar("SJ", bound=SpotifyBaseEntityJson)


class SpotifyClient(OAuthClient[SpotifyEntityJson]):
    """Custom client for interacting with Spotify's Web API.

    For authentication purposes either an already-instantiated OAuth manager or the
    relevant credentials must be provided

    Args:
        client_id (str): the application's client ID
        client_secret (str): the application's client secret
        log_requests (bool): flag for choosing if to log all requests made
        creds_cache_path (str): path at which to save cached credentials
    """

    AUTH_LINK_BASE = "https://accounts.spotify.com/authorize"
    ACCESS_TOKEN_ENDPOINT = "https://accounts.spotify.com/api/token"  # noqa: S105
    BASE_URL = "https://api.spotify.com/v1"

    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    DEFAULT_SCOPES: ClassVar[list[str]] = [
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

    SEARCH_TYPES: tuple[Literal["album", "artist", "playlist", "track"], ...] = (
        "album",
        "artist",
        "playlist",
        "track",
        # "show",
        # "episode",
    )

    _current_user: User

    def add_tracks_to_playlist(
        self,
        tracks: Iterable[Track],
        playlist: Playlist,
        *,
        log_responses: bool = False,
        force_add: bool = False,
        update_instance_tracklist: bool = True,
    ) -> list[Track]:
        """Add one or more tracks to a playlist.

        If `force_add` is False, a check is made against the Playlist's tracklist to
        ensure that the track isn't already in the playlist. This can be slow if it's
        a (new) big playlist.

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

        tracks_to_add = [
            track
            for track in tracks
            if not track.is_local and (force_add or track not in playlist)
        ]

        for chunk in chunk_list(tracks_to_add, 100):
            res = self._post(
                f"/playlists/{playlist.id}/tracks",
                json={"uris": [t.uri for t in chunk]},
            )

            if log_responses:
                LOGGER.info(dumps(res.json()))

        if update_instance_tracklist:
            playlist.tracks.extend(tracks_to_add)

        return tracks_to_add

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

        return Playlist.from_json_response(res.json(), spotify_client=self)

    def get_album_by_id(self, id_: str) -> Album:
        """Get an album from Spotify based on the ID.

        Args:
            id_ (str): the Spotify ID which is used to find the album

        Returns:
            Album: an instantiated Album, from the API's response
        """

        return Album.from_json_response(
            self.get_json_response(f"/albums/{id_}"),
            spotify_client=self,
        )

    def get_artist_by_id(self, id_: str) -> Artist:
        """Get an artist from Spotify based on the ID.

        Args:
            id_ (str): the Spotify ID which is used to find the artist

        Returns:
            Artist: an instantiated Artist, from the API's response
        """

        return Artist.from_json_response(
            self.get_json_response(f"/artists/{id_}"),
            spotify_client=self,
        )

    def get_items(
        self,
        url: str,
        *,
        params: None | dict[str, str | int | float | bool | dict[str, Any]] = None,
        hard_limit: int = 1000000,
        limit_func: (
            Callable[
                [dict[str, Any] | SpotifyEntityJson],
                bool,
            ]
            | None
        ) = None,
        top_level_key: (
            Literal[
                "albums",
                "artists",
                "audiobooks",
                "episodes",
                "playlists",
                "shows",
                "tracks",
            ]
            | None
        ) = None,
        list_key: Literal["items", "devices"] = "items",
    ) -> list[SpotifyEntityJson]:
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
            list_key (Literal["devices", "items"]): the key in the response which
                contains the list of items

        Returns:
            list: a list of dicts representing the Spotify items
        """

        params = params or {}
        if "limit=" not in url:
            params["limit"] = min(50, hard_limit)

        items: list[SpotifyEntityJson] = []

        if params:
            url += ("?" if "?" not in url else "&") + urlencode(params)

        page: AnyPaginatedResponse = {
            "href": "",
            "items": [],
            "limit": 0,
            "next": url,
            "offset": 0,
            "total": 0,
        }

        while (next_url := page.get("next")) and len(items) < hard_limit:
            # Ensure we don't bother getting more items than we need
            limit = min(50, hard_limit - len(items))
            next_url = sub(r"(?<=limit=)(\d{1,2})(?=&?)", str(limit), next_url)

            res: SearchResponse | AnyPaginatedResponse = self.get_json_response(next_url)  # type: ignore[assignment]
            page = (
                cast(SearchResponse, res)[top_level_key]
                if top_level_key
                else cast(AnyPaginatedResponse, res)
            )

            page_items: (
                list[AlbumSummaryJson]
                | list[DeviceJson]
                | list[ArtistSummaryJson]
                | list[PlaylistSummaryJson]
                | list[TrackFullJson]
            ) = page.get(list_key, [])
            if limit_func is None:
                items.extend(page_items)
            else:
                # Initialise `limit_reached` to False, and then it will be set to
                # True on the first matching item. This will then cause the loop to
                # skip subsequent items - not as good as a `break` but still kind of
                # elegant imho!
                limit_reached = False
                items.extend(
                    [
                        item
                        for item in page_items
                        if (not (limit_reached := (limit_reached or limit_func(item))))
                    ],
                )
                if limit_reached:
                    return items

        return items

    def get_playlist_by_id(self, id_: str) -> Playlist:
        """Get a playlist from Spotify based on the ID.

        Args:
            id_ (str): the Spotify ID which is used to find the playlist

        Returns:
            Playlist: an instantiated Playlist, from the API's response
        """

        if hasattr(self, "_current_user") and hasattr(self.current_user, "_playlists"):
            for playlist in self.current_user.playlists:
                if playlist.id == id_:
                    return playlist

        return Playlist.from_json_response(
            self.get_json_response(f"/playlists/{id_}"),
            spotify_client=self,
        )

    def get_track_by_id(self, id_: str) -> Track:
        """Get a track from Spotify based on the ID.

        Args:
            id_ (str): the Spotify ID which is used to find the track

        Returns:
            Track: an instantiated Track, from the API's response
        """

        return Track.from_json_response(
            self.get_json_response(f"/tracks/{id_}"),
            spotify_client=self,
        )

    @overload
    def search(
        self,
        search_term: str,
        *,
        entity_types: Sequence[Literal["album", "artist", "playlist", "track"]] = (),
        get_best_match_only: Literal[True],
    ) -> Artist | Playlist | Track | Album | None:
        ...

    @overload
    def search(
        self,
        search_term: str,
        *,
        entity_types: Sequence[Literal["album", "artist", "playlist", "track"]] = (),
        get_best_match_only: Literal[False] = False,
    ) -> ParsedSearchResponse:
        ...

    def search(
        self,
        search_term: str,
        *,
        entity_types: Sequence[Literal["album", "artist", "playlist", "track"]] = (),
        get_best_match_only: bool = False,
    ) -> Artist | Playlist | Track | Album | None | ParsedSearchResponse:
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

        entity_types = entity_types or self.SEARCH_TYPES

        if get_best_match_only is True and len(entity_types) != 1:
            raise ValueError(
                "Exactly one entity type must be requested if `get_best_match_only`"
                " is True",
            )

        entity_type: Literal["artist", "playlist", "track", "album"]
        for entity_type in entity_types:
            if entity_type not in self.SEARCH_TYPES:
                raise ValueError(
                    f"Unexpected value for entity type: '{entity_type}'. Must be"
                    f" one of {self.SEARCH_TYPES!r}",
                )

        res: SearchResponse = self.get_json_response(  # type: ignore[assignment]
            "/search",
            params={
                "query": search_term,
                "type": ",".join(entity_types),
                "limit": 1 if get_best_match_only else 50,
            },
        )

        entity_instances: ParsedSearchResponse = {}

        res_entity_type: Literal["albums", "artists", "playlists", "tracks"]
        entities_json: (
            PaginatedResponseAlbums
            | PaginatedResponseArtists
            | PaginatedResponsePlaylists
            | PaginatedResponseTracks
        )
        for res_entity_type, entities_json in res.items():  # type: ignore[assignment]
            instance_class: (
                type[Album] | type[Artist] | type[Playlist] | type[Track]
            ) = {  # type: ignore[assignment]
                "albums": Album,
                "artists": Artist,
                "playlists": Playlist,
                "tracks": Track,
            }[res_entity_type]

            if get_best_match_only:
                try:
                    # Take the entity off the top of the list
                    return instance_class.from_json_response(
                        entities_json["items"][0],
                        spotify_client=self,
                    )
                except LookupError:
                    return None

            entity_instances.setdefault(res_entity_type, []).extend(
                [
                    instance_class.from_json_response(entity_json, spotify_client=self)  # type: ignore[misc]
                    for entity_json in entities_json.get("items", [])
                ],
            )

            # Each entity type has its own type-specific next URL
            if (next_url := entities_json.get("next")) is not None:
                entity_instances[res_entity_type].extend(
                    [
                        instance_class.from_json_response(  # type: ignore[misc]
                            item,
                            spotify_client=self,
                        )
                        for item in self.get_items(
                            next_url,
                            top_level_key=res_entity_type,
                        )
                    ],
                )

        return entity_instances

    @property
    def current_user(self) -> User:
        """Get the current user's info.

        Returns:
            User: an instance of the current Spotify user
        """
        if not hasattr(self, "_current_user"):
            self._current_user = User.from_json_response(
                self.get_json_response("/me"),
                spotify_client=self,
            )

        return self._current_user


class SpotifyEntity(BaseModelWithConfig, Generic[SJ]):
    """Base model for Spotify entities."""

    description: str = ""
    external_urls: dict[Literal["spotify"], str]
    href: str
    id: str
    name: str = ""
    uri: str

    metadata: dict[str, Any] = Field(default_factory=dict)
    spotify_client: SpotifyClient = Field(exclude=True)

    summary_json: SJ = Field(default_factory=dict, frozen=True, exclude=True)  # type: ignore[assignment]
    sj_type: ClassVar[TypeAlias] = SpotifyBaseEntityJson

    @model_validator(mode="before")
    @classmethod
    def _set_summary_json(cls, values: dict[str, Any]) -> Any:
        values["summary_json"] = {
            k: v for k, v in values.items() if k in cls.sj_type.__annotations__
        }

        # Playlists are a unique case, because the SummaryJson and the FullJson both
        # share the key "tracks", which means that if FullJson is passed into this,
        # it needs to be converted down to SummaryJson. PlaylistFullJson is verified
        # by checking for an offset value.
        if cls.sj_type.__name__ == "PlaylistSummaryJson" and "offset" in values[
            "summary_json"
        ].get("tracks", ()):
            values["summary_json"]["tracks"] = {
                "href": values["summary_json"]["tracks"]["href"],
                "total": values["summary_json"]["tracks"]["total"],
            }

        return values

    @classmethod
    def from_json_response(
        cls,
        value: SpotifyEntityJson,
        spotify_client: SpotifyClient,
        additional_fields: dict[str, Any] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Self:
        """Parse a JSON response from the API into the given entity type model.

        Args:
            value (dict[str, object]): the JSON response from the API
            spotify_client (SpotifyClient): the client to use for future API calls
            additional_fields (dict[str, object] | None): additional fields to add to
                the model
            metadata (dict[str, object] | None): additional metadata to add to the model

        Returns:
            SpotifyEntity: the model for the given entity type
        """

        value_data: dict[str, object] = {
            "spotify_client": spotify_client,
            **(additional_fields or {}),
            **value,
        }

        if metadata:
            value_data["metadata"] = metadata

        return cls.model_validate(value_data)

    @property
    def url(self) -> str:
        """URL of the entity.

        Returns:
            str: the URL of this entity
        """
        return self.external_urls.get(
            "spotify",
            f"https://open.spotify.com/{type(self).__name__.lower()}/{self.id}",
        )

    def __eq__(self, other: object) -> bool:
        """Check if two entities are equal."""
        if not isinstance(other, SpotifyEntity):
            return NotImplemented
        return self.uri == other.uri

    def __gt__(self, other: object) -> bool:
        """Check if this entity is greater than another."""
        if not isinstance(other, SpotifyEntity):
            return NotImplemented
        return (self.name or self.id).lower() > (other.name or other.id).lower()

    def __hash__(self) -> int:
        """Get the hash of this entity."""
        return hash(repr(self))

    def __lt__(self, other: SpotifyEntity[SJ]) -> bool:
        """Check if this entity is less than another."""
        if not isinstance(other, SpotifyEntity):
            return NotImplemented
        return (self.name or self.id).lower() < (other.name or other.id).lower()

    def __repr__(self) -> str:
        """Get a string representation of this entity."""
        return f'{type(self).__name__}(id="{self.id}", name="{self.name}")'

    def __str__(self) -> str:
        """Get the string representation of this entity."""
        return self.name or f"{type(self).__name__} ({self.id})"


# Avoids mypy naming conflicts with `Album.type` and `type[...]`
SpotifyEntityJsonType = type[SpotifyEntityJson]


class Album(SpotifyEntity[AlbumSummaryJson]):
    """An album on Spotify."""

    album_group: Literal["album", "single", "compilation", "appears_on"] | None = None
    album_type_str: Literal[
        "single",
        "album",
        "compilation",
        "SINGLE",
        "ALBUM",
        "COMPILATION",
    ] = Field(alias="album_type")
    artists_json: list[ArtistSummaryJson] = Field(alias="artists")
    available_markets: list[str]
    copyrights: list[dict[str, str]] | None = None
    external_ids: dict[str, str] | None = None
    genres: list[str] | None = None
    images: list[Image]
    is_playable: bool | None = None
    label: str | None = None
    popularity: int | None = None
    release_date_precision: Literal["year", "month", "day"] | None = None
    release_date: date
    restrictions: dict[str, str] | None = None
    total_tracks: int
    tracks_json: PaginatedResponseTracks = Field(alias="tracks", default_factory=dict)  # type: ignore[assignment]
    type: Literal["album"]

    _artists: list[Artist]
    _tracks: list[Track]

    sj_type: ClassVar[SpotifyEntityJsonType] = AlbumSummaryJson

    @field_validator("release_date", mode="before")
    @classmethod
    def validate_release_date(cls, value: str | date, info: ValidationInfo) -> date:
        """Convert the release date string to a date object."""

        if isinstance(value, date):
            return value

        rdp = (info.data.get("release_date_precision") or "day").lower()

        exception = ValueError(
            f"Incompatible release_date and release_date_precision values: {value!r}"
            f" and {rdp!r} respectively.",
        )

        match value.split("-"):
            case y, m, d:
                if rdp != "day":
                    raise exception
                return date(int(y), int(m), int(d))
            case y, m:
                if rdp != "month":
                    raise exception
                return date(int(y), int(m), 1)
            case (y,):
                if rdp != "year":
                    raise exception
                return date(int(y), 1, 1)
            case _:
                raise exception

    @property
    def album_type(self) -> AlbumType:
        """Convert the album type string to an enum value."""

        return AlbumType(self.album_type_str.lower())

    @property
    def artists(self) -> list[Artist]:
        """Return a list of artists who contributed to the track.

        Returns:
            list(Artist): a list of the artists who contributed to this track
        """

        if not hasattr(self, "_artists"):
            artists = [
                Artist.from_json_response(
                    item,
                    spotify_client=self.spotify_client,
                )
                for item in self.artists_json
            ]

            self._artists = artists

        return self._artists

    @property
    def tracks(self) -> list[Track]:
        """List of tracks on the album.

        Returns:
            list: a list of tracks on this album
        """

        if not hasattr(self, "_tracks"):
            if self.tracks_json:
                # Initialise the list with data from the album JSON...
                tracks = [
                    Track.from_json_response(
                        item,
                        spotify_client=self.spotify_client,
                        additional_fields={"album": self.summary_json},
                    )
                    for item in self.tracks_json["items"]
                ]

                # ...then add the rest of the tracks from the API if necessary.
                if next_url := self.tracks_json.get("next"):
                    tracks.extend(
                        [
                            Track.from_json_response(
                                item,
                                spotify_client=self.spotify_client,
                                additional_fields={"album": self.summary_json},
                            )
                            for item in self.spotify_client.get_items(next_url)
                        ],
                    )
            else:
                tracks = [
                    Track.from_json_response(
                        item,
                        spotify_client=self.spotify_client,
                        additional_fields={"album": self.summary_json},
                    )
                    for item in self.spotify_client.get_items(f"/albums/{self.id}/tracks")
                ]

            self._tracks = tracks

        return self._tracks


class Artist(SpotifyEntity[ArtistSummaryJson]):
    """An artist on Spotify."""

    followers: Followers | None = None
    genres: list[str] | None = None
    images: list[Image] | None = None
    popularity: int | None = None
    type: Literal["artist"]

    _albums: list[Album]

    sj_type: ClassVar[SpotifyEntityJsonType] = ArtistSummaryJson

    @property
    def albums(self) -> list[Album]:
        """Return a list of albums by this artist.

        Returns:
            list: A list of albums this artist has contributed to
        """
        if not hasattr(self, "_albums"):
            albums = [
                Album.from_json_response(item, spotify_client=self.spotify_client)
                for item in self.spotify_client.get_items(f"/artists/{self.id}/albums")
            ]

            self._albums = albums

        return self._albums


class Track(SpotifyEntity[TrackFullJson]):
    """A track on Spotify."""

    album_json: AlbumSummaryJson = Field(alias="album")
    artists_json: list[ArtistSummaryJson] = Field(alias="artists")
    audio_features_json: TrackAudioFeaturesJson | None = Field(
        None,
        alias="audio_features",
    )
    available_markets: list[str]
    disc_number: int
    duration_ms: int
    episode: bool | None = None
    explicit: bool
    external_ids: dict[str, str] | None = None
    is_local: bool
    is_playable: bool | None = None
    linked_from: TrackFullJson | None = None
    popularity: int | None = None
    preview_url: str | None = None
    restrictions: str | None = None
    track: bool | None = None
    track_number: int
    type: Literal["track"]

    _artists: list[Artist]
    _album: Album
    _audio_features: TrackAudioFeatures | None

    sj_type: ClassVar[SpotifyEntityJsonType] = TrackFullJson

    @property
    def album(self) -> Album:
        """Track's parent album.

        Returns:
            Album: the album which this track is from
        """

        if not hasattr(self, "_album"):
            self._album = Album.from_json_response(
                self.album_json,
                spotify_client=self.spotify_client,
            )

        return self._album

    @property
    def artist(self) -> Artist:
        """Track's parent artist.

        Returns:
            Artist: the main artist which this track is from
        """

        return self.artists[0]

    @property
    def artists(self) -> list[Artist]:
        """Return a list of artists who contributed to the track.

        Returns:
            list(Artist): a list of the artists who contributed to this track
        """

        if not hasattr(self, "_artists"):
            artists = [
                Artist.from_json_response(
                    item,
                    spotify_client=self.spotify_client,
                )
                for item in self.artists_json
            ]

            self._artists = artists

        return self._artists

    @property
    def audio_features(self) -> TrackAudioFeatures | None:
        """Audio features of the track.

        Returns:
            dict: the JSON response from the Spotify /audio-features endpoint

        Raises:
            HTTPError: if `get_json_response` throws a HTTPError for a non-200/404
                response
        """
        if not hasattr(self, "_audio_features"):
            try:
                audio_features = self.spotify_client.get_json_response(
                    f"/audio-features/{self.id}",
                )
            except HTTPError as exc:
                if (
                    exc.response is not None
                    and exc.response.status_code == HTTPStatus.NOT_FOUND
                ):
                    return None
                raise

            self._audio_features = TrackAudioFeatures(**audio_features)

        return self._audio_features

    @property
    def release_date(self) -> date:
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
        try:
            return self.audio_features.tempo  # type: ignore[union-attr]
        except AttributeError:
            return None


class Playlist(SpotifyEntity[PlaylistSummaryJson]):
    """A Spotify playlist."""

    collaborative: bool
    followers: Followers | None = None
    images: list[Image]
    owner_json: UserSummaryJson = Field(alias="owner")
    primary_color: str | None = None
    # TODO: the `None` cases here can be handled by defaulting `public` to
    #  `self.owner.id == <user ID>`
    public: bool | None = None
    snapshot_id: str
    tracks_json: PaginatedResponsePlaylistTracks | PlaylistSummaryJsonTracks = Field(
        alias="tracks",
    )
    type: Literal["playlist"]

    _tracks: list[Track]
    _owner: User

    sj_type: ClassVar[SpotifyEntityJsonType] = PlaylistSummaryJson
    _live_snapshot_id_timestamp: datetime
    _live_snapshot_id: str

    @field_validator("tracks_json", mode="before")
    @classmethod
    def remove_local_tracks(
        cls,
        tracks_json: PaginatedResponsePlaylistTracks,
    ) -> PaginatedResponsePlaylistTracks:
        """Remove local tracks from the playlist's tracklist."""

        if "items" in tracks_json:
            tracks_json["items"] = [
                item for item in tracks_json["items"] if not item["is_local"]
            ]

        return tracks_json

    @property
    def live_snapshot_id(self) -> str:
        """The live snapshot ID of the playlist.

        The value is cached for a minute before being refreshed.

        Returns:
            str: the live snapshot ID of the playlist
        """
        if (
            not hasattr(self, "_live_snapshot_id_timestamp")
            or not hasattr(self, "_live_snapshot_id")
            or datetime.now(UTC) - self._live_snapshot_id_timestamp > timedelta(minutes=1)
        ):
            self._live_snapshot_id = self.spotify_client.get_json_response(
                f"/playlists/{self.id}",
                params={"fields": "snapshot_id"},
            )[
                "snapshot_id"  # type: ignore[typeddict-item]
            ]

            self._live_snapshot_id_timestamp = datetime.now(UTC)

        return self._live_snapshot_id

    @property
    def owner(self) -> User:
        """Playlist owner.

        Returns:
            User: the Spotify user who owns this playlist
        """

        if not hasattr(self, "_owner"):
            self._owner = User.from_json_response(
                self.owner_json,
                spotify_client=self.spotify_client,
            )

        return self._owner

    @property
    def tracks(self) -> list[Track]:
        """Return a list of tracks in the playlist.

        Returns:
            list: a list of tracks in this playlist
        """

        if not hasattr(self, "_tracks") or self.updates_available:
            tracks = [
                Track.from_json_response(
                    item["track"],
                    spotify_client=self.spotify_client,
                )
                for item in cast(
                    list[PlaylistFullJsonTracks],
                    self.spotify_client.get_items(f"/playlists/{self.id}/tracks"),
                )
                if item.get("track") is not None and item["is_local"] is False
            ]

            self._tracks = tracks

            if hasattr(self, "_live_snapshot_id"):
                self.snapshot_id = self._live_snapshot_id
            else:
                self._live_snapshot_id = self.snapshot_id

        return self._tracks

    @property
    def updates_available(self) -> bool:
        """Check if the playlist has updates available.

        Returns:
            bool: whether the playlist has updates available
        """
        return self.live_snapshot_id != self.snapshot_id

    def __contains__(self, track: Track) -> bool:
        """Check if a track is in the playlist."""
        return track in self.tracks

    def __gt__(self, other: object) -> bool:
        """Compare two playlists by name and ID."""
        if not isinstance(other, Playlist):
            return NotImplemented

        if self == other:
            return False

        return (self.name.lower(), self.id.lower()) > (
            other.name.lower(),
            other.id.lower(),
        )

    def __iter__(self) -> Iterator[Track]:  # type: ignore[override]
        """Iterate over the tracks in the playlist."""
        return iter(self.tracks)

    def __lt__(self, other: object) -> bool:
        """Compare two playlists by name and ID."""
        if not isinstance(other, Playlist):
            return NotImplemented

        if self == other:
            return False

        return (self.name.lower(), self.id.lower()) < (
            other.name.lower(),
            other.id.lower(),
        )


class User(SpotifyEntity[UserSummaryJson]):
    """A Spotify user, usually just the current user."""

    PLAYLIST_REFRESH_INTERVAL: ClassVar[timedelta] = timedelta(minutes=10)

    display_name: str
    country: str | None = None
    email: str | None = None
    explicit_content: dict[str, bool] | None = None
    followers: Followers | None = None
    images: list[Image] | None = None
    product: str | None = None
    type: Literal["user"]

    _albums: list[Album]
    _artists: list[Artist]
    _playlists: list[Playlist]
    _top_artists: tuple[Artist, ...]
    _top_tracks: tuple[Track, ...]
    _tracks: list[Track]

    _playlist_refresh_time: datetime

    sj_type: ClassVar[SpotifyEntityJsonType] = UserSummaryJson

    @field_validator("display_name", mode="before")
    @classmethod
    def set_user_name_value(cls, value: str, info: ValidationInfo) -> str:
        """Set the user's `name` field to the display name if it is not set.

        Args:
            value (str): the display name
            info (ValidationInfo): Object for extra validation information/data.

        Returns:
            str: the display name
        """

        if not info.data.get("name"):
            info.data["name"] = value

        return value

    @overload
    def get_playlists_by_name(
        self,
        name: str,
        *,
        return_all: Literal[False] = False,
    ) -> Playlist | None:
        ...

    @overload
    def get_playlists_by_name(
        self,
        name: str,
        *,
        return_all: Literal[True],
    ) -> list[Playlist]:
        ...

    def get_playlists_by_name(
        self,
        name: str,
        *,
        return_all: bool = False,
    ) -> list[Playlist] | Playlist | None:
        """Get Playlist instance(s) which have the given name.

        Args:
            name (str): the name of the target playlist(s)
            return_all (bool): playlist names aren't unique - but most people keep them
                unique within their own Sequence of playlists. This boolean can be used
                to return either a list of all matching playlists, or just the single
                found playlist

        Returns:
            Union([list, Playlist]): the matched playlist(s)
        """

        matched_playlists = filter(
            lambda p: p.name.lower() == name.lower(),
            self.playlists,
        )

        # Return a list of all matches
        if return_all:
            return sorted(matched_playlists)

        try:
            return next(matched_playlists)
        except StopIteration:
            return None

    def get_recently_liked_tracks(
        self,
        track_limit: int = 100,
        *,
        day_limit: float = 0.0,
    ) -> list[Track]:
        """Get a list of songs which were liked by the current user in the past N days.

        Args:
            track_limit (int): the number of tracks to return
            day_limit (float): the number of days (N) to go back in time for

        Returns:
            list: a list of Track instances
        """

        if not day_limit:
            limit_func: (
                Callable[
                    [SpotifyEntityJson | dict[str, Any]],
                    bool,
                ]
                | None
            ) = None

        else:

            def limit_func(item: dict[str, Any]) -> bool:  # type: ignore[misc]
                return bool(
                    datetime.strptime(
                        item["added_at"],
                        self.spotify_client.DATETIME_FORMAT,
                    ).replace(tzinfo=UTC)
                    < (datetime.now(UTC) - timedelta(days=day_limit)),
                )

        return [
            Track.from_json_response(
                item["track"],
                spotify_client=self.spotify_client,
                metadata={
                    "saved_at": datetime.strptime(
                        item["added_at"],
                        self.spotify_client.DATETIME_FORMAT,
                    ).replace(tzinfo=UTC),
                },
            )
            for item in cast(
                list[SavedItem],
                self.spotify_client.get_items(
                    "/me/tracks",
                    hard_limit=track_limit,
                    limit_func=limit_func,
                ),
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
            url = f"{self.spotify_client.BASE_URL}/me/albums"
            params = {"ids": entity.id}
        elif isinstance(entity, Artist):
            url = f"{self.spotify_client.BASE_URL}/me/following"
            params = {"type": "artist", "ids": entity.id}
        elif isinstance(entity, Playlist):
            url = f"{self.spotify_client.BASE_URL}/playlists/{entity.id}/followers"
            params = {"ids": self.id}
        elif isinstance(entity, Track):
            url = f"{self.spotify_client.BASE_URL}/me/tracks"
            params = {"ids": entity.id}
        else:
            raise TypeError(
                f"Cannot save entity of type `{type(entity).__name__}`. "
                f"Must be one of: Album, Artist, Playlist, Track",
            )

        res = put(
            url,
            params=params,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.spotify_client.access_token}",
                "Host": "api.spotify.com",
            },
            timeout=10,
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
            url = f"{self.spotify_client.BASE_URL}/me/albums"
            params = {"ids": entity.id}
        elif isinstance(entity, Artist):
            url = f"{self.spotify_client.BASE_URL}/me/following"
            params = {"type": "artist", "ids": entity.id}
        elif isinstance(entity, Playlist):
            url = f"{self.spotify_client.BASE_URL}/playlists/{entity.id}/followers"
            params = {"ids": self.id}
        elif isinstance(entity, Track):
            url = f"{self.spotify_client.BASE_URL}/me/tracks"
            params = {"ids": entity.id}
        else:
            raise TypeError(
                f"Cannot unsave entity of type `{type(entity).__name__}`. "
                f"Must be one of: Album, Artist, Playlist, Track",
            )

        res = delete(
            url,
            params=params,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.spotify_client.access_token}",
                "Host": "api.spotify.com",
            },
            timeout=10,
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
            albums = [
                Album.from_json_response(
                    item["album"],
                    spotify_client=self.spotify_client,
                )
                for item in cast(
                    list[SavedItem],
                    self.spotify_client.get_items("/me/albums"),
                )
            ]

            self._albums = albums

        return self._albums

    @property
    def artists(self) -> list[Artist]:
        """List of artists in the user's library.

        Returns:
            list: a list of artists owned by the current user
        """

        if not hasattr(self, "_artists"):
            artists = [
                Artist.from_json_response(
                    artist_json,
                    spotify_client=self.spotify_client,
                )
                for artist_json in self.spotify_client.get_items(
                    "/me/following",
                    params={
                        "type": "artist",
                    },
                    top_level_key="artists",
                )
            ]

            self._artists = artists

        return self._artists

    @property
    def current_track(self) -> Track | None:
        """Get the currently playing track for the given user.

        Returns:
            Track: the track currently being listened to
        """

        res = cast(
            SavedItem,
            self.spotify_client.get_json_response("/me/player/currently-playing"),
        )

        if item := res.get("item"):
            return Track.from_json_response(item, spotify_client=self.spotify_client)

        return None

    @property
    def current_playlist(self) -> Playlist | None:
        """Get the current playlist for the given user.

        Returns:
            Playlist: the playlist currently being listened to
        """

        res = self.spotify_client.get_json_response("/me/player/currently-playing")

        if (context := res.get("context", {})).get(  # type: ignore[attr-defined]
            "type",
        ) == "playlist":
            playlist: Playlist = self.spotify_client.get_playlist_by_id(
                context["uri"].split(":")[-1],  # type: ignore[index]
            )
            return playlist
        return None

    @property
    def devices(self) -> list[Device]:
        """Return a list of devices that the user currently has access to.

        Returns:
            list[Device]: a list of devices available to the user
        """
        return [
            Device.model_validate(device_json)
            for device_json in self.spotify_client.get_items(
                "/me/player/devices",
                list_key="devices",
            )
        ]

    @property
    def playlists(self) -> list[Playlist]:
        """Return a list of playlists owned by the current user.

        If self.PLAYLIST_REFRESH_INTERVAL has elapsed, a new call to the API will be
        made to refresh the list of playlists. Only new playlists will be added to the
        list, preserving previous instances.

        Returns:
            list: a list of playlists owned by the current user
        """

        if (
            hasattr(self, "_playlist_refresh_time")
            and (datetime.now(UTC) - self._playlist_refresh_time)
            < self.PLAYLIST_REFRESH_INTERVAL
        ):
            return self._playlists

        self._playlist_refresh_time = datetime.now(UTC)

        all_playlist_json = cast(
            list[PlaylistSummaryJson],
            self.spotify_client.get_items("/me/playlists"),
        )

        if not hasattr(self, "_playlists"):
            playlists = [
                Playlist.from_json_response(item, spotify_client=self.spotify_client)
                for item in all_playlist_json
                if item["owner"]["id"] == self.id
            ]

            self._playlists = playlists
        else:
            existing_ids = (p.id for p in self._playlists)
            new_playlists = [
                Playlist.from_json_response(item, spotify_client=self.spotify_client)
                for item in all_playlist_json
                if item["owner"]["id"] == self.id and item["id"] not in existing_ids
            ]

            self._playlists.extend(new_playlists)

        return self._playlists

    @property
    def top_artists(self) -> tuple[Artist, ...]:
        """Top artists for the user.

        Returns:
            tuple[Artist, ...]: the top artists for the user
        """

        if not hasattr(self, "_top_artists"):
            top_artists = tuple(
                Artist.from_json_response(
                    artist_json,
                    spotify_client=self.spotify_client,
                )
                for artist_json in self.spotify_client.get_items(
                    "/me/top/artists",
                    params={"time_range": "short_term"},
                )
            )
            self._top_artists = top_artists

        return self._top_artists

    @property
    def top_tracks(self) -> tuple[Track, ...]:
        """The top tracks for the user.

        Returns:
            tuple[Track]: the top tracks for the user
        """
        if not hasattr(self, "_top_tracks"):
            top_tracks = tuple(
                Track.from_json_response(
                    track_json,
                    spotify_client=self.spotify_client,
                )
                for track_json in self.spotify_client.get_items(
                    "/me/top/tracks",
                    params={"time_range": "short_term"},
                )
            )

            self._top_tracks = top_tracks

        return self._top_tracks

    @property
    def tracks(self) -> list[Track]:
        """Liked Songs.

        Returns:
            list: a list of tracks owned by the current user
        """

        if not hasattr(self, "_tracks"):
            tracks = [
                Track.from_json_response(
                    item["track"],
                    spotify_client=self.spotify_client,
                    metadata={
                        "saved_at": datetime.strptime(
                            item["added_at"],
                            self.spotify_client.DATETIME_FORMAT,
                        ).replace(tzinfo=UTC),
                    },
                )
                for item in cast(
                    list[SavedItem],
                    self.spotify_client.get_items("/me/tracks"),
                )
            ]

            self._tracks = tracks

        return self._tracks

    def reset_properties(
        self,
        property_names: (
            Iterable[
                Literal[
                    "albums",
                    "artists",
                    "playlists",
                    "top_artists",
                    "top_tracks",
                    "tracks",
                ]
            ]
            | None
        ) = None,
    ) -> None:
        """Reset all list properties."""

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

        if "playlists" in property_names:
            delattr(self, "_playlist_refresh_time")


SpotifyEntity.model_rebuild()
Album.model_rebuild()
Artist.model_rebuild()
Track.model_rebuild()
