# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.spotify.SpotifyClient`."""
from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from json import dumps, loads
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl

from pytest import LogCaptureFixture, mark, raises
from requests import HTTPError
from requests_mock import Mocker

from conftest import (
    FLAT_FILES_DIR,
    assert_mock_requests_request_history,
    read_json_file,
)
from wg_utilities.clients import SpotifyClient
from wg_utilities.clients._spotify_types import SpotifyBaseEntityJson
from wg_utilities.clients.spotify import (
    Album,
    Artist,
    ParsedSearchResponse,
    Playlist,
    SpotifyEntity,
    Track,
    User,
)


def test_instantiation() -> None:
    """Test instantiation of the Spotify client."""
    client = SpotifyClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        log_requests=True,
    )
    assert client.log_requests is True


@mark.parametrize(  # type: ignore[misc]
    "file_path",
    [
        path_object
        for path_object in (FLAT_FILES_DIR / "json" / "spotify").rglob("*")
        if path_object.is_file() and path_object.suffix == ".json"
    ],
)
def test_get_method_with_sample_responses(
    spotify_client: SpotifyClient,
    file_path: Path,
    caplog: LogCaptureFixture,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test the `_get` method processes a request and its response correctly."""

    endpoint = (
        f"/{file_path.relative_to(FLAT_FILES_DIR / 'json' / 'spotify').with_suffix('')}"
    )
    if "=" in endpoint:
        endpoint, query_string = endpoint.rsplit("/", 1)
        params = dict(parse_qsl(query_string))

        # This is for the assertion below
        query_string = "?" + query_string
    else:
        query_string = ""
        params = None

    assert endpoint.startswith("/")

    res = spotify_client._get(
        url=endpoint,
        params=params,  # type: ignore[arg-type]
    )

    assert res.status_code == HTTPStatus.OK
    assert res.reason == HTTPStatus.OK.phrase

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": SpotifyClient.BASE_URL + endpoint + query_string,
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            }
        ],
    )

    assert res.json() == loads(file_path.read_text())

    assert (
        caplog.records[0].message
        == f"GET {SpotifyClient.BASE_URL + endpoint} with params {dumps(params or {})}"
    )


@mark.parametrize(  # type: ignore[misc]
    "file_path",
    [
        path_object
        for path_object in (FLAT_FILES_DIR / "json" / "spotify").rglob("*")
        if path_object.is_file() and path_object.suffix == ".json"
    ],
)
def test_get_method_without_leading_slash(
    spotify_client: SpotifyClient,
    file_path: Path,
    caplog: LogCaptureFixture,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test the `_get` method processes a request and its response correctly."""

    endpoint = (
        f"/{file_path.relative_to(FLAT_FILES_DIR / 'json' / 'spotify').with_suffix('')}"
    )
    if "=" in endpoint:
        endpoint, query_string = endpoint.rsplit("/", 1)
        params = dict(parse_qsl(query_string))

        # This is for the assertion below
        query_string = "?" + query_string
    else:
        query_string = ""
        params = None

    endpoint = SpotifyClient.BASE_URL + endpoint

    assert not endpoint.startswith("/")

    res = spotify_client._get(
        url=endpoint,
        params=params,  # type: ignore[arg-type]
    )

    assert res.status_code == HTTPStatus.OK
    assert res.reason == HTTPStatus.OK.phrase

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": endpoint + query_string,
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            }
        ],
    )

    assert res.json() == loads(file_path.read_text())

    assert (
        caplog.records[0].message == f"GET {endpoint} with params {dumps(params or {})}"
    )


@mark.parametrize("http_status", HTTPStatus)  # type: ignore[misc]
def test_get_method_with_exception(
    spotify_client: SpotifyClient, mock_requests: Mocker, http_status: HTTPStatus
) -> None:
    """Test that when a non-2XX code is returned, an exception is raised."""
    mock_requests.get(
        "https://www.example.com",
        status_code=http_status,
        reason=http_status.phrase,
        text="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod"
        " tempor incididunt ut labore et dolore magna aliqua.",
    )

    if str(http_status.value).startswith("4"):
        with raises(HTTPError) as exc_info:
            spotify_client._get("https://www.example.com")

        assert (
            str(exc_info.value)
            == f"{http_status.value} Client Error: {http_status.phrase} for url:"
            f" https://www.example.com/"
        )
    elif str(http_status.value).startswith("5"):
        with raises(HTTPError) as exc_info:
            spotify_client._get("https://www.example.com")

        assert (
            str(exc_info.value)
            == f"{http_status.value} Server Error: {http_status.phrase} for url:"
            f" https://www.example.com/"
        )
    else:
        res = spotify_client._get("https://www.example.com")
        assert res.status_code == http_status
        assert res.reason == http_status.phrase
        assert (
            res.text
            == "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod"
            " tempor incididunt ut labore et dolore magna aliqua."
        )


# def test_post_method(spotify_client: SpotifyClient, mock_requests: Mocker) -> None:
#     """Test that `_post` forms the request correct, returns the correct response."""


def test_get_items_from_url_no_pagination(
    spotify_client: SpotifyClient, spotify_artist: Artist, mock_requests: Mocker
) -> None:
    """Test that the `get_items_from_url` method processes a single page correctly."""

    items = spotify_client.get_items_from_url(
        url="https://api.spotify.com/v1/artists/1ma3pjzpirayypnrkp3suf/albums",
    )
    assert len(mock_requests.request_history) == 1

    assert items == [album.summary_json for album in spotify_artist.albums]


def test_get_items_from_url_with_pagination(
    spotify_client: SpotifyClient, spotify_playlist: Playlist, mock_requests: Mocker
) -> None:
    """Test that the `get_items_from_url` method processes multiple pages correctly."""

    items = spotify_client.get_items_from_url(
        url="https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks",
    )
    # Not testing all request details as it's covered by
    # `tests.unit.clients.spotify.test__playlist.test_tracks_property`
    assert len(mock_requests.request_history) == 11

    assert [
        Track.from_json_response(
            item["track"],  # type: ignore[arg-type,typeddict-item]
            spotify_client=spotify_client,
        )
        for item in items
        if item.get("is_local", False) is False
    ] == spotify_playlist.tracks
    assert len(items) == 518


def test_get_items_from_url_handles_params_correctly(
    spotify_client: SpotifyClient, mock_requests: Mocker, live_jwt_token: str
) -> None:
    """Test that the `params` dict are turned into a query string correctly."""

    mock_requests.get(
        "https://api.spotify.com/v1/foo?key=value&query=string&limit=50",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
    )

    spotify_client.get_items_from_url(
        "/foo", params={"key": "value", "query": "string"}
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "https://api.spotify.com/v1/foo?key=value&query=string&limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            }
        ],
    )


def test_get_items_from_url_hard_limit(
    spotify_client: SpotifyClient, mock_requests: Mocker, live_jwt_token: str
) -> None:
    """Test the `hard_limit` argument works correctly."""

    items = spotify_client.get_items_from_url(
        url="https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks",
        hard_limit=75,
    )

    assert len(mock_requests.request_history) == 2

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            # pylint: disable=line-too-long
            {
                "url": "https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks?limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
            {
                "url": "https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks?offset=50&limit=25",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
        ],
    )

    assert len(items) == 75


def test_get_items_from_url_limit_func(
    spotify_client: SpotifyClient, mock_requests: Mocker, live_jwt_token: str
) -> None:
    """Test that a limit function can be passed to `get_items_from_url`."""

    items = spotify_client.get_items_from_url(
        url="https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks",
        limit_func=lambda item: datetime.strptime(
            item["added_at"],  # type: ignore[typeddict-item]
            spotify_client.DATETIME_FORMAT,
        )
        >= datetime(2020, 1, 1),
    )

    tracks = [
        Track.from_json_response(
            item["track"],  # type: ignore[arg-type,typeddict-item]
            spotify_client=spotify_client,
            metadata={
                "added_at_datetime": datetime.strptime(
                    item["added_at"],  # type: ignore[typeddict-item]
                    spotify_client.DATETIME_FORMAT,
                )
            },
        )
        for item in items
        if item["is_local"] is False  # type: ignore[typeddict-item]
    ]

    assert not any(
        track.metadata["added_at_datetime"] > datetime(2019, 12, 31) for track in tracks
    )

    assert len(mock_requests.request_history) == 6
    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            # pylint: disable=line-too-long
            {
                "url": "https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks?limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
            {
                "url": "https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks?offset=50&limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
            {
                "url": "https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks?offset=100&limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
            {
                "url": "https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks?offset=150&limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
            {
                "url": "https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks?offset=200&limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
            {
                "url": "https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks?offset=250&limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
        ],
    )

    # I just checked this number manually and added it, it's not a very useful test...
    assert len(items) == 256

    # Check this doesn't override the hard limit
    assert (
        len(
            spotify_client.get_items_from_url(
                # pylint: disable=line-too-long
                url="https://api.spotify.com/v1/playlists/2lmx8fu0seq7ea5kcmlnpx/tracks",
                limit_func=lambda item: datetime.strptime(
                    item["added_at"],  # type: ignore[typeddict-item]
                    spotify_client.DATETIME_FORMAT,
                )
                >= datetime(2020, 1, 1),
                hard_limit=75,
            )
        )
        == 75
    )


def test_get_items_from_url_different_list_key(spotify_client: SpotifyClient) -> None:
    """Tests items under a different key are correctly extracted."""

    items = spotify_client.get_items_from_url(
        "/me/player/devices",
    )

    assert not items

    devices = spotify_client.get_items_from_url(
        "/me/player/devices", list_key="devices"
    )

    assert len(devices) == 2


def test_get_items_from_url_with_top_level_key(spotify_client: SpotifyClient) -> None:
    """Tests items under a top level key *and* and list key are correctly extracted."""

    items = spotify_client.get_items_from_url(
        "/me/following",
        params={
            "type": "artist",
        },
    )

    assert not items

    artists = spotify_client.get_items_from_url(
        "/me/following",
        params={
            "type": "artist",
        },
        top_level_key="artists",
    )

    assert len(artists) == 112


def test_get_json_response_returns_json(
    spotify_client: SpotifyClient, mock_requests: Mocker
) -> None:
    """Test that the JSON content of the response is returned as a dict."""

    assert isinstance(spotify_client.get_json_response("/me"), dict)

    # Test when no (valid) JSON is returned
    # This is a valid case, as non-200 responses are raised by the `_get` method
    mock_requests.get(
        "https://api.spotify.com/v1/foo",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        text="",
    )
    mock_requests.get(
        "https://api.spotify.com/v1/bar",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        text="text",
    )

    assert (
        spotify_client.get_json_response("/foo")
        == {}  # type: ignore[comparison-overlap]
    )
    assert (
        spotify_client.get_json_response("/bar")
        == {}  # type: ignore[comparison-overlap]
    )

    # Test a 204 No Content response
    mock_requests.get(
        "https://api.spotify.com/v1/baz",
        status_code=HTTPStatus.NO_CONTENT,
        reason=HTTPStatus.NO_CONTENT.phrase,
    )

    assert (
        spotify_client.get_json_response("/baz")  # type: ignore[comparison-overlap]
        == {}
    )


@mark.parametrize(  # type: ignore[misc]
    [
        "search_term",
        "entity_type",
        "entity_type_str",
        "expected_url",
        "expected_return_value_file_path",
    ],
    [
        (
            "Mirrors",
            Album,
            "album",
            "https://api.spotify.com/v1/search?query=mirrors&type=album&limit=1",
            "albums/7FvnTARvgjUyWnUT0flUN7.json",
        ),
        # pylint: disable=line-too-long
        (
            "Ross from Friends",
            Artist,
            "artist",
            "https://api.spotify.com/v1/search?query=ross+from+friends&type=artist&limit=1",
            "artists/1Ma3pJzPIrAyYPNRkp3SUF.json",
        ),
        (
            "Chill Electronica",
            Playlist,
            "playlist",
            "https://api.spotify.com/v1/search?query=Chill+Electronica&type=playlist&limit=1",
            "playlists/2lmx8fu0seq7ea5kcmlnpx.json",
        ),
        (
            "Past Life Tame Impala",
            Track,
            "track",
            "https://api.spotify.com/v1/search?query=past+life+tame+impala&type=track&limit=1",
            "tracks/4a9fw33myr8lhxboluhbff.json",
        ),
    ],
)
def test_search_method_get_best_match_only(
    spotify_client: SpotifyClient,
    mock_requests: Mocker,
    search_term: str,
    entity_type: type[SpotifyEntity[SpotifyBaseEntityJson]],
    entity_type_str: Literal["album", "artist", "playlist", "track"],
    expected_url: str,
    expected_return_value_file_path: str,
    live_jwt_token: str,
) -> None:
    """Test the `search` method processes the request and response correctly."""

    search_result = spotify_client.search(
        search_term, entity_types=[entity_type_str], get_best_match_only=True
    )

    assert search_result == entity_type.from_json_response(
        read_json_file(expected_return_value_file_path, host_name="spotify"),
        spotify_client=spotify_client,
    )

    assert len(mock_requests.request_history) == 1
    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": expected_url,
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            }
        ],
    )


def test_search_method_get_best_match_only_multiple_entity_types_throws_error(
    spotify_client: SpotifyClient, mock_requests: Mocker
) -> None:
    """Test the `search` method returns `None` when no results are found."""

    with raises(ValueError) as exc_info:
        spotify_client.search(
            "Mirrors",
            entity_types=["album", "artist"],
            get_best_match_only=True,
        )

    assert (
        str(exc_info.value)
        == "Exactly one entity type must be requested if `get_best_match_only` is True"
    )

    # Check that the error isn't raised when `get_best_match_only` is False
    mock_requests.get(
        "https://api.spotify.com/v1/search?query=mirrors&type=album%2cartist&limit=50",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
    )

    spotify_client.search(
        "Mirrors",
        entity_types=["album", "artist"],
        get_best_match_only=False,
    )


def test_search_method_invalid_entity_type(spotify_client: SpotifyClient) -> None:
    """Test that an exception is thrown when an invalid entity type is requested."""

    with raises(ValueError) as exc_info:
        spotify_client.search(
            "Mirrors", entity_types=["album", "foo"]  # type: ignore[list-item]
        )

    assert str(exc_info.value) == (
        "Unexpected value for entity type: 'foo'. Must be one of ('album', 'artist', "
        "'playlist', 'track')"
    )


def test_search_method_with_pagination(
    spotify_client: SpotifyClient, mock_requests: Mocker, live_jwt_token: str
) -> None:
    """Test that when >50 results are returned, they paginate correctly."""

    # An uncommon search, so I don't have to manually reduce the number of files
    results: ParsedSearchResponse = spotify_client.search(
        "uncommon search", entity_types=["track"], get_best_match_only=False
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            # pylint: disable=line-too-long
            {
                "url": "https://api.spotify.com/v1/search?query=uncommon+search&type=track&limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
            {
                "url": "https://api.spotify.com/v1/search?query=uncommon+search&type=track&offset=50&limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
            {
                "url": "https://api.spotify.com/v1/search?query=uncommon+search&type=track&offset=100&limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
            {
                "url": "https://api.spotify.com/v1/search?query=uncommon+search&type=track&offset=150&limit=50",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            },
        ],
    )

    assert isinstance(results, dict)
    assert list(results.keys()) == ["tracks"]
    assert isinstance(results["tracks"], list)
    assert all(isinstance(track, Track) for track in results["tracks"])
    assert len(results["tracks"]) == 105


def test_search_no_results(spotify_client: SpotifyClient) -> None:
    """Test that when no results are returned, an empty dict is returned."""

    assert (
        spotify_client.search(
            # pylint: disable=line-too-long
            "S6aoG9N@zsyeCr@3m@WhtgB$2LL%XYIA6r0yWmt0ZECc1MoRx%zCB$BW6lKTZHaMe6XBMQiiyenkPt!jpnLvoV4sUq35X9u7!uA",
            entity_types=["track"],
            get_best_match_only=True,
        )
        is None
    )

    assert spotify_client.search(
        # pylint: disable=line-too-long
        "S6aoG9N@zsyeCr@3m@WhtgB$2LL%XYIA6r0yWmt0ZECc1MoRx%zCB$BW6lKTZHaMe6XBMQiiyenkPt!jpnLvoV4sUq35X9u7!uA",
        entity_types=["track"],
        get_best_match_only=False,
    ) == {
        "tracks": [],
    }


def test_access_token_property(
    spotify_client: SpotifyClient, live_jwt_token: str
) -> None:
    """Test that the `access_token` leverages the SpotifyOAuth instance."""

    assert spotify_client.access_token == live_jwt_token


def test_current_user_property(
    spotify_client: SpotifyClient,
    mock_requests: Mocker,
    spotify_user: User,
    live_jwt_token: str,
) -> None:
    """Test that the `current_user` property returns the correct data."""

    assert not hasattr(spotify_client, "_current_user")
    assert spotify_client.current_user == spotify_user
    assert hasattr(spotify_client, "_current_user")

    assert len(mock_requests.request_history) == 1
    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "https://api.spotify.com/v1/me",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            }
        ],
    )


@mark.parametrize("update_instance_tracklist", [True, False])  # type: ignore[misc]
def test_add_tracks_to_playlist(
    spotify_client: SpotifyClient,
    spotify_playlist: Playlist,
    mock_requests: Mocker,
    caplog: LogCaptureFixture,
    update_instance_tracklist: bool,
    live_jwt_token: str,
) -> None:
    """Test `add_tracks_to_playlist` makes the correct requests."""

    playlist_to_add_to = spotify_client.get_playlist_by_id("4Vv023MaZsc8NTWZ4WJvIL")
    new_tracks_to_add = [
        track for track in spotify_playlist.tracks if track not in playlist_to_add_to
    ]
    assert not any(track in playlist_to_add_to for track in new_tracks_to_add)
    mock_requests.reset()
    caplog.records.clear()
    spotify_client.log_requests = False
    spotify_client.add_tracks_to_playlist(
        new_tracks_to_add,
        playlist_to_add_to,
        log_responses=True,
        update_instance_tracklist=update_instance_tracklist,
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                # pylint: disable=line-too-long
                "url": "https://api.spotify.com/v1/playlists/4Vv023MaZsc8NTWZ4WJvIL/tracks",
                "method": "POST",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            }
        ]
        * 4,
    )

    assert len(caplog.records) == 4
    assert all(record.levelname == "INFO" for record in caplog.records)
    assert all(
        record.message == dumps({"snapshot_id": "MTAsZDVmZjMjJhZTVmZjcxOGNlMA=="})
        for record in caplog.records
    )

    if update_instance_tracklist:
        assert all(
            track in playlist_to_add_to
            for track in new_tracks_to_add
            if not track.is_local
        )
    else:
        assert all(track not in playlist_to_add_to for track in new_tracks_to_add)


def test_add_tracks_to_playlist_ignores_tracks_already_in_playlist(
    spotify_client: SpotifyClient, mock_requests: Mocker
) -> None:
    """Test that tracks which are already in the playlist are ignored."""

    playlist_to_add_to = spotify_client.get_playlist_by_id("4Vv023MaZsc8NTWZ4WJvIL")
    tracks_to_add = playlist_to_add_to.tracks

    mock_requests.reset()

    spotify_client.add_tracks_to_playlist(
        tracks_to_add,
        playlist_to_add_to,
        update_instance_tracklist=True,
    )

    assert not mock_requests.request_history


@mark.parametrize(  # type: ignore[misc]
    [
        "public",
        "collaborative",
    ],
    (
        [True, True],
        [True, False],
        [False, True],
        [False, False],
    ),
)
def test_create_playlist_method(
    spotify_client: SpotifyClient, public: bool, collaborative: bool
) -> None:
    """Test that the `create_playlist` method makes the correct requests."""

    new_playlist = spotify_client.create_playlist(
        name="Test Playlist",
        description="This is a test playlist.",
        public=public,
        collaborative=collaborative,
    )

    assert isinstance(new_playlist, Playlist)
    assert new_playlist.name == "Test Playlist"
    assert new_playlist.description == "This is a test playlist."
    assert new_playlist.public is public
    assert new_playlist.collaborative is collaborative
    assert new_playlist.owner == spotify_client.current_user
    assert new_playlist.tracks == []


@mark.parametrize(  # type: ignore[misc]
    "album_id", ["4julBAGYv4WmRXwhjJ2LPD", "7FvnTARvgjUyWnUT0flUN7"]
)
def test_get_album_by_id_method(
    spotify_client: SpotifyClient,
    album_id: str,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test that the correct Album instance is returned."""

    result = spotify_client.get_album_by_id(album_id)

    assert isinstance(result, Album)
    assert result.id == album_id

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"https://api.spotify.com/v1/albums/{album_id}",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            }
        ],
    )


@mark.parametrize(  # type: ignore[misc]
    "artist_id", ["0q8eApZJs5WDBxayY9769C", "1Ma3pJzPIrAyYPNRkp3SUF"]
)
def test_get_artist_by_id_method(
    spotify_client: SpotifyClient,
    artist_id: str,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test that the correct Artist instance is returned."""

    result = spotify_client.get_artist_by_id(artist_id)

    assert isinstance(result, Artist)
    assert result.id == artist_id

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"https://api.spotify.com/v1/artists/{artist_id}",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            }
        ],
    )


@mark.parametrize(  # type: ignore[misc]
    "playlist_id",
    [
        "2lMx8FU0SeQ7eA5kcMlNpX",
        "2wSNKxLM217jpZnkAgYZPH",
        "4Vv023MaZsc8NTWZ4WJvIL",
        "37i9dQZF1E8Pj76JxE3EGf",
    ],
)
def test_get_playlist_by_id_method(
    spotify_client: SpotifyClient,
    playlist_id: str,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test that the correct Playlist instance is returned."""

    result = spotify_client.get_playlist_by_id(playlist_id)

    assert isinstance(result, Playlist)
    assert result.id == playlist_id

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"https://api.spotify.com/v1/playlists/{playlist_id}",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            }
        ],
    )


@mark.parametrize(  # type: ignore[misc]
    "playlist_id", ["2lMx8FU0SeQ7eA5kcMlNpX", "4Vv023MaZsc8NTWZ4WJvIL"]
)
def test_get_playlist_by_id_after_property_accessed(
    spotify_client: SpotifyClient, playlist_id: str, mock_requests: Mocker
) -> None:
    """Test that the correct Playlist instance is returned."""

    _ = spotify_client.current_user.playlists

    mock_requests.reset()
    result = spotify_client.get_playlist_by_id(playlist_id)

    assert isinstance(result, Playlist)
    assert result.id == playlist_id

    assert not mock_requests.request_history


@mark.parametrize(  # type: ignore[misc]
    "track_id",
    [
        "1PfbIpFjsS1BayUoqB3X7O",
        "4a9fW33mYR8LhXBOLUhbfF",
        "5U5X1TnRhnp9GogRfaE9XQ",
        "5wakjJAy1qMk5h8y1DUEhJ",
        "6zJUp1ihdid6Kn3Ndgcy82",
        "27cgqh0VRhVeM61ugTnorD",
    ],
)
def test_get_track_by_id_method(
    spotify_client: SpotifyClient,
    track_id: str,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test that the correct Track instance is returned."""

    result = spotify_client.get_track_by_id(track_id)

    assert isinstance(result, Track)
    assert result.id == track_id

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"https://api.spotify.com/v1/tracks/{track_id}",
                "method": "GET",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {live_jwt_token}",
                },
            }
        ],
    )
