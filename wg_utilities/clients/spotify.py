"""Custom client for interacting with Spotify's Web API"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import Enum
from json import JSONDecodeError, dumps
from logging import DEBUG, getLogger
from re import sub
from typing import Any, Callable, Collection, Literal, TypedDict

from requests import Response, get, post
from spotipy import CacheFileHandler, SpotifyOAuth

from wg_utilities.functions import chunk_list

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


class AlbumType(Enum):
    """Enum for the different types of album Spotify supports"""

    SINGLE = "single"
    ALBUM = "album"
    COMPILATION = "compilation"


class _SpotifyEntityInfo(TypedDict):
    description: str
    href: str
    id: str
    name: str
    uri: str
    external_urls: dict[Literal["spotify"], str]


class _AlbumTracksItemInfo(TypedDict):
    href: str
    items: list[_TrackInfo]  # type: ignore
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
    restrictions: dict[str, str]
    total_tracks: int
    tracks: _AlbumTracksItemInfo
    type: Literal["album"]


class _ArtistInfo(_SpotifyEntityInfo):
    followers: dict[str, str | None | int]
    genres: list[str]
    images: list[dict[str, str | int]]
    popularity: int
    type: Literal["artist"]


class _PlaylistInfo(_SpotifyEntityInfo):
    collaborative: bool
    followers: dict[str, str | None | int]
    images: list[dict[str, str | int]]
    owner: _UserInfo
    public: bool
    snapshot_id: str
    tracks: list[_TrackInfo]  # type: ignore
    type: Literal["playlist"]


class _TrackInfo(_SpotifyEntityInfo):
    album: _AlbumInfo
    artists: list[_ArtistInfo]


class _UserInfo(_SpotifyEntityInfo):
    display_name: str


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


class SpotifyEntity:
    """Parent class for all Spotify entities (albums, artists, etc.)

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
        """
        Returns:
            str: a "pretty" version of the JSON, used for debugging etc.
        """
        return dumps(self.json, indent=4, default=str)

    @property
    def description(self) -> str | None:
        """
        Returns:
            str: the description of the entity
        """
        return self.json.get("description")

    @property
    def endpoint(self) -> str | None:
        """
        Returns:
            str: A link to the Web API endpoint providing full details of the entity
        """
        return self.json.get("href")

    @property
    def id(self) -> str | None:
        """
        Returns:
            str: The base-62 identifier for the entity
        """
        return self.json.get("id")

    @property
    def name(self) -> str:
        """
        Returns:
            str: the name of the entity
        """
        return self.json["name"]

    @property
    def uri(self) -> str:
        """
        Returns:
            str: the Spotify URI of this entity
        """

        return self.json.get("uri", f"spotify:{type(self).__name__.lower()}:{self.id}")

    @property
    def url(self) -> str:
        """
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
        return self.name.lower() > other.name.lower()

    def __hash__(self) -> int:
        return hash(repr(self))

    def __lt__(self, other: SpotifyEntity) -> bool:
        return self.name.lower() < other.name.lower()

    def __repr__(self) -> str:
        return f'{type(self).__name__}(id="{self.id}")'

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"


class User(SpotifyEntity):
    """A Spotify user, usually just the current user"""

    json: _UserInfo

    def __init__(
        self,
        json: _UserInfo,
        spotify_client: SpotifyClient,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(json=json, spotify_client=spotify_client, metadata=metadata)

    @property
    def name(self) -> str:
        """
        Returns:
            str: the display name of the User
        """

        return self.json["display_name"]

    @property
    def current_playlist(self) -> Playlist | None:
        """Gets the current playlist for the given user

        Returns:
            Playlist: the playlist currently being listened to
        """

        res = self._spotify_client.get_json_response("/me/player/currently-playing")

        if (context := res.get("context", {})).get("type") == "playlist":
            return self._spotify_client.get_playlist_by_id(
                context["uri"].split(":")[-1]
            )

        return None

    @property
    def current_track(self) -> Track | None:
        """Gets the currently playing track for the given user

        Returns:
            Track: the track currently being listened to
        """

        res = self._spotify_client.get_json_response("/me/player/currently-playing")

        if res.get("is_playing", False):
            return Track(res["item"], spotify_client=self._spotify_client)

        return None


class Track(SpotifyEntity):
    """A track on Spotify"""

    json: _TrackInfo

    def __init__(
        self,
        json: _TrackInfo,
        spotify_client: SpotifyClient,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(json=json, spotify_client=spotify_client, metadata=metadata)
        self._artists: list[Artist] | None = None
        self._audio_features: _TrackAudioFeaturesInfo

    @property
    def album(self) -> Album:
        """
        Returns:
            Album: the album which this track is from
        """

        return Album(self.json["album"], self._spotify_client)

    @property
    def artists(self) -> list[Artist]:
        """
        Returns:
            list(Artist): a list of the artists who contributed to this track
        """

        if self._artists is None:
            self._artists = [
                Artist(item, self._spotify_client)
                for item in self.json.get("artists", [])
            ]

        return self._artists

    @property
    def audio_features(self) -> _TrackAudioFeaturesInfo:
        """
        Returns:
            dict: the JSON response from the Spotify /audio-features endpoint
        """
        if not hasattr(self, "_audio_features"):
            # pylint: disable=line-too-long
            self._audio_features = self._spotify_client.get_json_response(  # type: ignore[assignment]
                f"/audio-features/{self.id}"
            )

        return self._audio_features

    @property
    def release_date(self) -> date | str | None:
        """
        Returns:
            date: the date the track's album was first released
        """
        return self.album.release_date

    @property
    def tempo(self) -> float | None:
        """
        Returns:
            float: the tempo of the track, in BPM
        """
        return self.audio_features.get("tempo")


class Artist(SpotifyEntity):
    """An artist on Spotify"""

    json: _ArtistInfo

    def __init__(self, json: _ArtistInfo, spotify_client: SpotifyClient):
        super().__init__(json=json, spotify_client=spotify_client)
        self._albums: list[Album] | None = None

    @property
    def albums(self) -> list[Album]:
        """
        Returns:
            list: A list of albums this artist has contributed to
        """
        if not self._albums:
            self._albums = [
                Album(item, self._spotify_client)  # type: ignore[arg-type]
                for item in self._spotify_client.get_items_from_url(
                    f"/artists/{self.id}/albums"
                )
            ]

        return self._albums


class Album(SpotifyEntity):
    """An album on Spotify"""

    json: _AlbumInfo

    def __init__(self, json: _AlbumInfo, spotify_client: SpotifyClient):
        super().__init__(json, spotify_client)
        self._artists: list[Artist]
        self._tracks: list[Track]

    @property
    def artists(self) -> list[Artist]:
        """
        Returns:
            list(Artist): a list of the artists who contributed to this track
        """

        if not hasattr(self, "_artists"):
            self._artists = [
                Artist(item, self._spotify_client)
                for item in self.json.get("artists", [])
            ]

        return self._artists

    @property
    def release_date(self) -> date | str | None:
        """
        Returns:
            date: the date the album was first released
        """
        if (release_date_str := self.json.get("release_date")) is not None:
            for _format in ("%Y-%m-%d", "%Y-%m", "%Y"):
                try:
                    return datetime.strptime(release_date_str, _format).date()
                except ValueError:
                    pass

        return release_date_str

    @property
    def release_date_precision(self) -> Literal["year", "month", "day", None]:
        """
        Returns:
            str: the precision with which release_date value is known
        """
        return self.json.get("release_date_precision")

    @property
    def tracks(self) -> list[Track]:
        """
        Returns:
            list: a list of tracks on this album
        """

        if not hasattr(self, "_tracks"):
            self._tracks = [
                Track(item, self._spotify_client)
                for item in self.json.get("tracks", {}).get("items", [])
            ]

            # May as well get the items in the album description already, then can get
            # the rest if we need to
            if next_url := self.json.get("tracks", {}).get("next"):
                self._tracks.extend(
                    Track(item, self._spotify_client)  # type: ignore[arg-type]
                    for item in self._spotify_client.get_items_from_url(next_url)
                )

        return self._tracks

    @property
    def type(self) -> AlbumType:
        """
        Returns:
            AlbumType: the type of album this is
        """

        return AlbumType[self.json.get("album_type", "").upper()]


class Playlist(SpotifyEntity):
    """A Spotify playlist"""

    json: _PlaylistInfo

    def __init__(
        self,
        json: _PlaylistInfo,
        spotify_client: SpotifyClient,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(json=json, spotify_client=spotify_client, metadata=metadata)
        self._tracks: list[Track]

    @property
    def tracks(self) -> list[Track]:
        """
        Returns:
            list: a list of tracks in this playlist
        """

        if not hasattr(self, "_tracks"):
            self._tracks = [
                Track(
                    item.get("track", {}),  # type: ignore[arg-type,union-attr]
                    self._spotify_client,
                )
                for item in self._spotify_client.get_items_from_url(
                    f"/playlists/{self.id}/tracks"
                )
            ]

        return self._tracks

    @property
    def owner(self) -> User:
        """
        Returns:
            User: the Spotify user who owns this playlist
        """

        return User(self.json["owner"], self._spotify_client)

    def __contains__(self, track: Track) -> bool:
        return track in self.tracks

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Playlist):
            return NotImplemented

        if self.name.lower() == other.name.lower():
            if self.owner.id == self._spotify_client.current_user.id:
                return False

            if other.owner.id == self._spotify_client.current_user.id:
                return True

        return self.name.lower() > other.name.lower()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Playlist):
            return NotImplemented

        if self.name.lower() == other.name.lower():

            if self.owner.id == self._spotify_client.current_user.id:
                return True

            if other.owner.id == self._spotify_client.current_user.id:
                return False

        return self.name.lower() < other.name.lower()

    def __str__(self) -> str:
        return f"{self.name} ({self.id}) - owned by {self.owner}"


class SpotifyClient:
    """Custom client for interacting with Spotify's Web API. For authentication
    purposes either an already-instantiated OAuth manager or the relevant credentials
    must be provided

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
        creds_cache_path: str | None = None,
    ):
        self.oauth_manager = oauth_manager or SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            cache_handler=CacheFileHandler(cache_path=creds_cache_path),
        )
        self.log_requests = log_requests
        self.api_call_count = 0

        self._current_user: User

        self._albums: list[Album]
        self._playlists: list[Playlist]
        self._tracks: list[Track]

    def _get(
        self,
        url: str,
        params: None | (dict[str, str | float | int | bool | dict[str, Any]]) = None,
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

        self.api_call_count += 1

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

        self.api_call_count += 1

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
    ) -> list[
        (
            _PlaylistInfo
            | _TrackInfo
            | _AlbumInfo
            | list[dict[Literal["album"], _AlbumInfo]]
        )
    ]:
        """Retrieve a list of items from a given URL, including pagination

        Args:
            url (str): the API endpoint which we're listing
            params (dict): any params to pass with the API request
            hard_limit (int): a hard limit to apply to the number of items returned (as
             opposed to the "soft" limit of 50 imposed by the API)
            limit_func (Callable): a function which is used to evaluate each item in
             turn: if it returns False, the item is added to the output list; if it
             returns True then the iteration stops and the list is returned as-is

        Returns:
            list: a list of dicts representing the Spotify items
        """

        params = params or {}
        params["limit"] = min(50, hard_limit)

        items: list[
            (
                _PlaylistInfo
                | _TrackInfo
                | _AlbumInfo
                | list[dict[Literal["album"], _AlbumInfo]]
            )
        ] = []
        res = Response()
        # pylint: disable=protected-access
        res._content = dumps({"next": url}).encode()

        while (next_url := res.json().get("next")) and len(items) < hard_limit:
            params["limit"] = min(50, hard_limit - len(items))
            # remove hardcoded limit from next URL in favour of JSON param version
            next_url = sub(r"limit=\d{1,2}&?", "", next_url).rstrip("?&")

            res = self._get(next_url, params=params)
            if limit_func is None:
                items.extend(res.json().get("items", []))
            else:
                for item in res.json().get("items", []):
                    if limit_func(item):
                        return items

                    items.append(item)

        return items

    def get_json_response(
        self,
        url: str,
        params: None | (dict[str, str | int | float | bool | dict[str, Any]]) = None,
    ) -> dict[str, Any]:
        """Gets a simple JSON object from a URL

        Args:
            url (str): the API endpoint to GET
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            dict: the JSON from the response
        """
        try:
            return self._get(url, params=params).json()  # type: ignore
        except JSONDecodeError:
            return {}

    def search(
        self,
        search_term: str,
        entity_types: Collection[Literal["album", "artist", "playlist", "track"]] = (),
        get_best_match_only: bool = False,
    ) -> Artist | Playlist | Track | Album | None | dict[
        Literal["album", "artist", "playlist", "track"],
        list[Album | Artist | Playlist | Track],
    ]:
        """Search Spotify for a given search term

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
                "q": search_term,
                "type": ",".join(entity_types),
                "limit": 50,
            },
        )

        entity_instances: dict[
            Literal["album", "artist", "playlist", "track"],
            list[Album | Artist | Playlist | Track],
        ] = {}

        for entity_type, entities_json in res.items():  # type: ignore[assignment]

            instance_class: type[Album | Artist | Playlist | Track] = {
                "albums": Album,
                "artists": Artist,
                "playlists": Playlist,
                "tracks": Track,
            }[entity_type]

            if get_best_match_only:
                try:
                    # Take the entity off the top of the list
                    return instance_class(
                        entities_json.get("items", [])[0], spotify_client=self
                    )
                except IndexError:
                    return None

            entity_instances.setdefault(entity_type, []).extend(
                [
                    instance_class(entity_json, spotify_client=self)
                    for entity_json in entities_json.get("items", [])
                ]
            )

            # Each entity type has its own type-specific next URL
            if (next_url := entities_json.get("next")) is not None:
                entity_instances[entity_type].extend(
                    [
                        instance_class(
                            item, spotify_client=self  # type: ignore[arg-type]
                        )
                        for item in self.get_items_from_url(next_url)
                    ]
                )

        return entity_instances

    @property
    def access_token(self) -> str:
        """
        Returns:
            str: the web API access token
        """
        return str(self.oauth_manager.get_access_token(as_dict=False))

    @property
    def albums(self) -> list[Album]:
        """
        Returns:
            list: a list of albums owned by the current user
        """

        if not hasattr(self, "_albums"):
            self._albums = [
                Album(item["album"], self)  # type: ignore
                for item in self.get_items_from_url("/me/albums")
            ]

        return self._albums

    @property
    def playlists(self) -> list[Playlist]:
        """
        Returns:
            list: a list of playlists owned by the current user
        """

        if not hasattr(self, "_playlists"):
            self._playlists = [
                Playlist(item, self)  # type: ignore[arg-type]
                for item in self.get_items_from_url("/me/playlists")
            ]

        return self._playlists

    @property
    def tracks(self) -> list[Track]:
        """
        Returns:
            list: a list of tracks owned by the current user
        """

        if not hasattr(self, "_tracks"):
            self._tracks = [
                Track(item["track"], self)  # type: ignore
                for item in self.get_items_from_url("/me/tracks")
            ]

        return self._tracks

    @property
    def current_user(self) -> User:
        """Gets the current user's info

        Returns:
            User: an instance of the current Spotify user
        """
        if not hasattr(self, "_current_user"):
            self._current_user = User(self._get(f"{self.BASE_URL}/me").json(), self)

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
        """Add one or more tracks to a playlist

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

        if not force_add:
            tracks = [track for track in tracks if track not in playlist]

        for chunk in chunk_list(tracks, 100):
            res = self._post(
                f"/playlists/{playlist.id}/tracks",
                json={"uris": [t.uri for t in chunk]},
            )

            res.raise_for_status()

            if log_responses:
                LOGGER.debug(dumps(res.json()))

        if update_instance_tracklist:
            playlist.tracks.extend(tracks)

    def create_playlist(
        self,
        name: str,
        description: str = "",
        public: bool = False,
        collaborative: bool = False,
    ) -> Playlist:
        """Create a new playlist under the current user's account

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
            {
                "name": name,
                "description": description,
                "public": public,
                "collaborative": collaborative,
            },
        )

        return Playlist(res.json(), self)

    def get_playlists_by_name(
        self, name: str, return_all: bool = False
    ) -> list[Playlist] | Playlist | None:
        """Gets Playlist instance(s) which have the given name

        Args:
            name (str): the name of the target playlist(s)
            return_all (bool): playlist names aren't unique - but most people keep them
             unique within their own collection of playlists. This boolean can be used
             to return either a list of all matching playlists, or just the single
             found playlist

        Returns:
            Union([list, Playlist]): the matched playlist(s)
        """

        matched_playlists = sorted(filter(lambda p: p.name == name, self.playlists))

        # Return a list of all matches
        if return_all:
            return matched_playlists

        try:
            return matched_playlists[0]
        except IndexError:
            pass

        return None

    def get_album_by_id(self, id_: str) -> Album:
        """Get an album from Spotify based on the ID

        Args:
            id_(str): the Spotify ID which is used to find the album

        Returns:
            Album: an instantiated Album, from the API's response
        """

        return Album(self._get(f"/albums/{id_}").json(), self)

    def get_artist_by_id(self, id_: str) -> Artist:
        """Get an artist from Spotify based on the ID

        Args:
            id_(str): the Spotify ID which is used to find the artist

        Returns:
            Artist: an instantiated Artist, from the API's response
        """

        return Artist(self._get(f"/artists/{id_}").json(), self)

    def get_playlist_by_id(self, id_: str) -> Playlist:
        """Get a playlist from Spotify based on the ID

        Args:
            id_(str): the Spotify ID which is used to find the playlist

        Returns:
            Playlist: an instantiated Playlist, from the API's response
        """

        if hasattr(self, "_playlists"):
            for plist in self.playlists:
                if plist.id == id_:
                    return plist

        return Playlist(self._get(f"/playlists/{id_}").json(), self)

    def get_track_by_id(self, id_: str) -> Track:
        """Get a track from Spotify based on the ID

        Args:
            id_(str): the Spotify ID which is used to find the track

        Returns:
            Track: an instantiated Track, from the API's response
        """

        return Track(self._get(f"/tracks/{id_}").json(), self)

    def get_recently_liked_tracks(
        self, track_limit: int = 100, *, day_limit: float | None = None
    ) -> list[Track]:
        """Gets a list of songs which were liked by the current user in the past N days

        Args:
            track_limit (int): the number of tracks to return
            day_limit (float): the number of days (N) to go back in time for

        Returns:
            list: a list of Track instances
        """

        kwargs: dict[str, int | Callable[[Any], bool]] = {"hard_limit": track_limit}

        if isinstance(day_limit, (float, int)):
            kwargs["limit_func"] = lambda item: bool(
                datetime.strptime(item["added_at"], self.DATETIME_FORMAT)
                # pylint: disable=line-too-long
                < (datetime.utcnow() - timedelta(days=day_limit))  # type: ignore[arg-type]
            )

        return [
            # pylint: disable=line-too-long
            Track(item["track"], self, metadata={"liked_at": item["added_at"]})  # type: ignore
            for item in self.get_items_from_url("/me/tracks", **kwargs)  # type: ignore
        ]

    def reset_properties(self) -> None:
        """Resets all list properties"""
        try:
            del self._current_user
        except AttributeError as exc:
            print(str(exc))

        try:
            del self._albums
        except AttributeError as exc:
            print(repr(exc))

        try:
            del self._playlists
        except AttributeError:
            pass

        try:
            del self._tracks
        except AttributeError:
            pass
