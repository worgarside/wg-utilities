"""TypedDicts for Spotify API responses.

This module might be overkill and can likely be implemented in a better way, idk! I'm
not sure if there's anything functional that is done with these types, but they
are used for type hinting and to make the code more readable.
"""

from __future__ import annotations

from logging import DEBUG, getLogger
from typing import TYPE_CHECKING, Literal, TypeAlias, final

from typing_extensions import NotRequired, TypedDict

if TYPE_CHECKING:
    from datetime import date

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)

# <editor-fold desc="Simple/'Helper' Objects">


class ExternalUrls(TypedDict):
    """An `external_urls` object in for a Spotify entity."""

    spotify: str


class Followers(TypedDict):
    """The count of followers for a Spotify entity."""

    href: None  # Not implemented yet
    total: int


class Image(TypedDict):
    """An object for the Spotify entity's image."""

    url: str
    height: int | None
    width: int | None


# Generic Objects


class SpotifyBaseEntityJson(TypedDict):
    """The base JSON object for a Spotify entity."""

    external_urls: ExternalUrls
    href: str
    id: str
    uri: str


class SpotifyNamedEntityJson(SpotifyBaseEntityJson):
    """The base JSON object for a Spotify entity with a name."""

    name: str


# </editor-fold>
# <editor-fold desc="Album Objects">


class AlbumSummaryJson(SpotifyNamedEntityJson, total=False):
    """Type info for Spotify albums in tracks.

    See Also:
        TrackFullJson
    """

    album_group: Literal["album", "single", "compilation", "appears_on"]
    album_type: Literal[
        "single",
        "album",
        "compilation",
        "SINGLE",
        "ALBUM",
        "COMPILATION",
    ]
    artists: list[ArtistSummaryJson]
    available_markets: list[str]
    images: list[Image]
    is_playable: bool | None
    release_date: str | date
    release_date_precision: str
    total_tracks: int
    restrictions: NotRequired[dict[str, str]]
    type: Literal["album"]


class AlbumFullJson(AlbumSummaryJson):
    """Response from `/albums/{id}`."""

    copyrights: list[dict[str, str]]
    external_ids: dict[str, str]
    genres: list[str]
    label: str
    popularity: int
    tracks: PaginatedResponseTracks


# </editor-fold>
# <editor-fold desc="Artist Objects">


class ArtistSummaryJson(SpotifyNamedEntityJson):
    """Type info for Spotify artists in albums.

    See Also:
        ArtistFullJson
    """

    type: Literal["artist"]


class ArtistFullJson(ArtistSummaryJson):
    """Response from `/artists/{id}`."""

    followers: Followers
    genres: list[str]
    images: list[Image]
    popularity: int


# </editor-fold>
# <editor-fold desc="Devices">


class DeviceJson(TypedDict):
    """Type info for Spotify devices."""

    id: str
    is_active: bool
    is_private_session: bool
    is_restricted: bool
    name: str
    type: str
    volume_percent: int


# </editor-fold>
# <editor-fold desc="Playlist Objects">


class PlaylistSummaryJsonTracks(TypedDict):
    """Type info for the `tracks` field of `PlaylistSummaryJson`."""

    href: str
    total: int


class _PlaylistBaseJson(SpotifyNamedEntityJson):
    collaborative: bool
    description: str
    images: list[Image]
    owner: UserSummaryJson
    primary_color: None  # Not implemented yet
    public: bool | None
    snapshot_id: str
    type: Literal["playlist"]


class PlaylistFullJsonTracks(TypedDict):
    """Type info for the `tracks` field of `PlaylistFullJson`."""

    added_at: str
    added_by: UserSummaryJson
    is_local: Literal[False]
    primary_color: None  # Not implemented yet
    track: TrackFullJson
    video_thumbnail: NotRequired[_TrackVideoThumbnail]


class PlaylistSummaryJson(_PlaylistBaseJson):
    """Type info for Spotify playlists in pages.

    See Also:
        PlaylistFullJson
    """

    tracks: PlaylistSummaryJsonTracks


class PlaylistFullJson(_PlaylistBaseJson):
    """Response from `/playlists/{id}`."""

    followers: Followers
    tracks: PaginatedResponsePlaylistTracks


# </editor-fold>
# <editor-fold desc="Track Objects">


class _LinkedFromInTrack(TypedDict):
    """Type info for Spotify linked_from in tracks.

    See Also:
        TrackFullJson
    """

    album: NotRequired[AlbumSummaryJson]
    artists: NotRequired[list[ArtistSummaryJson]]


class _TrackVideoThumbnail(TypedDict, total=False):
    """Type info for Spotify video_thumbnail in tracks.

    See Also:
        TrackFullJson
    """

    url: str | None
    height: NotRequired[int]
    width: NotRequired[int]


class TrackFullJson(SpotifyNamedEntityJson, total=False):
    """Response from `/tracks/{id}`."""

    album: AlbumSummaryJson
    artists: list[ArtistSummaryJson]
    available_markets: list[str]
    disc_number: int
    duration_ms: int
    episode: NotRequired[bool]
    explicit: bool
    external_ids: NotRequired[dict[str, str]]
    is_local: Literal[False]
    is_playable: NotRequired[bool]
    linked_from: NotRequired[_LinkedFromInTrack]
    popularity: int
    preview_url: str | None
    restrictions: NotRequired[
        dict[Literal["reason"], Literal["explicit", "market", "product"]]
    ]
    track: NotRequired[bool]
    track_number: int
    type: Literal["track"]


class TrackAudioFeaturesJson(TypedDict):
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


# </editor-fold>
# <editor-fold desc="User Objects">


class UserSummaryJson(SpotifyBaseEntityJson, total=False):
    """Type info for Spotify users in playlists.

    See Also:
        PlaylistFullJson
    """

    display_name: NotRequired[str | None]
    type: Literal["user"]


class UserFullJson(UserSummaryJson):
    """Response from `/me`."""

    country: str
    email: str
    explicit_content: dict[str, bool]
    images: list[Image]
    product: str


# </editor-fold>
# <editor-fold desc="Paginated Responses">


class _PaginatedResponseBase(TypedDict, total=False):
    """Typing info for paginated responses from Spotify."""

    devices: NotRequired[list[DeviceJson]]
    href: str
    limit: int
    next: str | None
    offset: int
    previous: str | None
    total: int


class PaginatedResponsePlaylistTracks(_PaginatedResponseBase):
    """Type info for the `tracks` field of `PlaylistFullJson`."""

    items: list[PlaylistFullJsonTracks]


class PaginatedResponseAlbums(_PaginatedResponseBase):
    """TypedDict for paginated responses containing albums."""

    items: list[AlbumSummaryJson]


class PaginatedResponseArtists(_PaginatedResponseBase):
    """TypedDict for paginated responses containing artists."""

    items: list[ArtistSummaryJson]


class PaginatedResponseDevices(_PaginatedResponseBase):
    """TypedDict for paginated responses containing devices.

    This is only really needed to satisfy mypy, otherwise the base class could be used.
    """

    items: NotRequired[
        list[AlbumSummaryJson]
        | list[ArtistSummaryJson]
        | list[PlaylistSummaryJson]
        | list[TrackFullJson]
    ]


class PaginatedResponsePlaylists(_PaginatedResponseBase):
    """TypedDict for paginated responses containing playlists."""

    items: list[PlaylistSummaryJson]


class PaginatedResponseTracks(_PaginatedResponseBase, total=False):
    """TypedDict for paginated responses containing tracks."""

    items: NotRequired[list[TrackFullJson]]


class PaginatedResponseGeneral(_PaginatedResponseBase):
    """TypedDict for paginated responses which I haven't implemented yet."""

    items: (
        list[AlbumSummaryJson]
        | list[ArtistSummaryJson]
        | list[DeviceJson]
        | list[PlaylistSummaryJson]
        | list[TrackFullJson]
    )


AnyPaginatedResponse: TypeAlias = (
    PaginatedResponseAlbums
    | PaginatedResponseArtists
    | PaginatedResponseDevices
    | PaginatedResponseGeneral
    | PaginatedResponsePlaylists
    | PaginatedResponseTracks
)


class SavedItem(TypedDict, total=False):
    """Type info for Spotify saved items."""

    added_at: str
    album: NotRequired[AlbumFullJson]
    track: NotRequired[TrackFullJson]
    item: NotRequired[TrackFullJson]


class PaginatedResponseMyItems(_PaginatedResponseBase):
    """TypedDict for paginated responses containing saved items."""

    items: list[SavedItem]


# </editor-fold>


@final
class SearchResponse(TypedDict):
    """Typing info for search responses from Spotify."""

    albums: PaginatedResponseAlbums
    artists: PaginatedResponseArtists
    audiobooks: PaginatedResponseGeneral
    episodes: PaginatedResponseGeneral
    playlists: PaginatedResponsePlaylists
    shows: PaginatedResponseGeneral
    tracks: PaginatedResponseTracks


SpotifyEntityJson: TypeAlias = (
    AlbumSummaryJson
    | ArtistSummaryJson
    | ArtistFullJson
    | DeviceJson
    | PlaylistSummaryJson
    | TrackFullJson
    | UserSummaryJson
    | UserFullJson
)
