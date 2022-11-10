# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.spotify.User`."""
from __future__ import annotations

from http import HTTPStatus
from unittest.mock import patch

from pytest import FixtureRequest, mark, raises
from requests_mock import Mocker

from conftest import assert_mock_requests_request_history, read_json_file
from wg_utilities.clients.spotify import (
    Album,
    Artist,
    Device,
    Playlist,
    SpotifyClient,
    Track,
    User,
)


def test_instantiation(spotify_client: SpotifyClient) -> None:
    """Tests instantiation of User class."""

    user = User(
        {
            "country": "GB",
            "display_name": "Will Garside",
            "email": "test_email_address@gmail.com",
            "explicit_content": {"filter_enabled": False, "filter_locked": False},
            "external_urls": {"spotify": "https://open.spotify.com/user/worgarside"},
            "followers": {"href": None, "total": 13},
            "href": "https://api.spotify.com/v1/users/worgarside",
            "id": "worgarside",
            "images": [
                {
                    "height": None,
                    "url": "https://via.placeholder.com/200x100",
                    "width": None,
                }
            ],
            "product": "premium",
            "type": "user",
            "uri": "spotify:user:worgarside",
        },
        spotify_client=spotify_client,
    )

    assert isinstance(user, User)
    assert user._spotify_client == spotify_client
    assert user.json == {
        "country": "GB",
        "display_name": "Will Garside",
        "email": "test_email_address@gmail.com",
        "explicit_content": {"filter_enabled": False, "filter_locked": False},
        "external_urls": {"spotify": "https://open.spotify.com/user/worgarside"},
        "followers": {"href": None, "total": 13},
        "href": "https://api.spotify.com/v1/users/worgarside",
        "id": "worgarside",
        "images": [
            {
                "height": None,
                "url": "https://via.placeholder.com/200x100",
                "width": None,
            }
        ],
        "product": "premium",
        "type": "user",
        "uri": "spotify:user:worgarside",
    }


@mark.parametrize(  # type: ignore[misc]
    ["entity_fixture", "request_values"],
    [
        # pylint: disable=line-too-long
        (
            "spotify_album",
            {
                "url": f"{SpotifyClient.BASE_URL}/me/albums?ids=4julBAGYv4WmRXwhjJ2LPD",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ),
        (
            "spotify_artist",
            {
                "url": f"{SpotifyClient.BASE_URL}/me/following?type=artist&ids=1Ma3pJzPIrAyYPNRkp3SUF",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ),
        (
            "spotify_playlist",
            {
                "url": f"{SpotifyClient.BASE_URL}/playlists/37i9dQZF1E8Pj76JxE3EGf/followers?ids=worgarside",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ),
        (
            "spotify_track",
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?ids=27cgqh0VRhVeM61ugTnorD",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ),
    ],
)
def test_save_unsave_methods(
    spotify_user: User,
    mock_requests: Mocker,
    entity_fixture: str,
    request_values: dict[str, str | dict[str, str]],
    request: FixtureRequest,
) -> None:
    """Test that `save` method makes the expected request per entity."""
    entity = request.getfixturevalue(entity_fixture)

    spotify_user.save(entity=entity)

    request_values["method"] = "PUT"

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [request_values],
    )

    mock_requests.reset_mock()

    spotify_user.unsave(entity=entity)

    request_values["method"] = "DELETE"

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [request_values],
    )

    assert mock_requests.call_count == 1


def test_save_unsave_methods_with_invalid_type(spotify_user: User) -> None:
    """Test that `save` method raises an error if an invalid entity type is passed."""

    device = Device.parse_obj(
        read_json_file("spotify/me/player/devices/limit=50.json")["devices"][
            0  # type: ignore[index]
        ]
    )

    with raises(TypeError) as exc_info:
        spotify_user.save(entity=device)  # type: ignore[arg-type]

    assert (
        str(exc_info.value) == "Cannot save entity of type `Device`. "
        "Must be one of: Album, Artist, Playlist, Track"
    )

    with raises(TypeError) as exc_info:
        spotify_user.unsave(entity=device)  # type: ignore[arg-type]

    assert (
        str(exc_info.value) == "Cannot unsave entity of type `Device`. "
        "Must be one of: Album, Artist, Playlist, Track"
    )


def test_albums_property(spotify_user: User, mock_requests: Mocker) -> None:
    """Test that `albums` property makes the expected request."""

    assert not hasattr(spotify_user, "_albums")
    assert all(
        isinstance(album, Album)
        and album._spotify_client == spotify_user._spotify_client
        for album in spotify_user.albums
    )
    assert hasattr(spotify_user, "_albums")

    assert mock_requests.call_count == 2

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "https://api.spotify.com/v1/me/albums?limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/me/albums?offset=50&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ],
    )

    # Check subsequent calls to property don't make additional requests
    assert len(spotify_user._albums) == 80
    assert mock_requests.call_count == 2


def test_artists_property(
    spotify_user: User, mock_requests: Mocker, spotify_client: SpotifyClient
) -> None:
    """Test that `artists` property makes the expected request."""

    prefix = "spotify/me/following/type=artist&"

    assert spotify_user.artists == [
        Artist(artist_json, spotify_client=spotify_client)
        for artist_json in [  # type: ignore[misc]
            *read_json_file(f"{prefix}limit=50.json")[
                "artists"
            ][  # type: ignore[call-overload]
                "items"  # type: ignore[index]
            ],
            *read_json_file(f"{prefix}after=3iOvXCl6edW5Um0fXEBRXy&limit=50.json")[
                "artists"
            ][  # type: ignore[call-overload]
                "items"  # type: ignore[index]
            ],
            *read_json_file(f"{prefix}after=77BznF1Dr1k5KyEZ6Nn3jB&limit=50.json")[
                "artists"
            ][  # type: ignore[call-overload]
                "items"  # type: ignore[index]
            ],
        ]
    ]

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            # pylint: disable=line-too-long
            {
                "url": "https://api.spotify.com/v1/me/following?type=artist&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/me/following?type=artist&after=3iOvXCl6edW5Um0fXEBRXy&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/me/following?type=artist&after=77BznF1Dr1k5KyEZ6Nn3jB&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ],
    )

    assert mock_requests.call_count == 3


def test_current_track_property(
    spotify_user: User,
    mock_requests: Mocker,
) -> None:
    """Test that `current_track` property makes the expected request."""

    assert spotify_user.current_track == Track(
        json=read_json_file(  # type: ignore[arg-type]
            "spotify/tracks/5wakjjay1qmk5h8y1duehj.json"
        ),
        spotify_client=spotify_user._spotify_client,
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "https://api.spotify.com/v1/me/player/currently-playing",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ],
    )

    assert mock_requests.call_count == 1


def test_current_track_nothing_playing(
    spotify_user: User, mock_requests: Mocker
) -> None:
    """Test that `current_track` property returns None if nothing is playing."""
    mock_requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        status_code=HTTPStatus.NO_CONTENT,
        reason=HTTPStatus.NO_CONTENT.phrase,
    )

    assert spotify_user.current_track is None


def test_current_playlist_property(
    spotify_user: User,
    mock_requests: Mocker,
    spotify_playlist: Playlist,
) -> None:
    """Test that `current_playlist` property makes the expected request."""
    assert not mock_requests.request_history

    with patch.object(
        spotify_user._spotify_client,
        "get_playlist_by_id",
        wraps=spotify_user._spotify_client.get_playlist_by_id,
    ) as mock_get_playlist_by_id:
        assert spotify_user.current_playlist == spotify_playlist

    mock_get_playlist_by_id.assert_called_once_with("37i9dqzf1e8pj76jxe3egf")

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "https://api.spotify.com/v1/me/player/currently-playing",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/playlists/37i9dqzf1e8pj76jxe3egf",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ],
    )

    assert mock_requests.call_count == 2


def test_current_playlist_nothing_playing(
    spotify_user: User, mock_requests: Mocker
) -> None:
    """Test that `current_playlist` property returns None if nothing is playing."""
    mock_requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        status_code=HTTPStatus.NO_CONTENT,
        reason=HTTPStatus.NO_CONTENT.phrase,
    )

    assert spotify_user.current_playlist is None


def test_devices_property(spotify_user: User, mock_requests: Mocker) -> None:
    """Test that `devices` property makes the expected request."""

    assert spotify_user.devices == [
        Device.parse_obj(device_json)
        for device_json in read_json_file(
            "spotify/me/player/devices/limit=50.json"
        )[  # type: ignore[union-attr]
            "devices"
        ]
    ]

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "https://api.spotify.com/v1/me/player/devices?limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ],
    )


def test_name_property(spotify_user: User) -> None:
    """Test that `name` property returns the expected value."""
    assert spotify_user.name == "Will Garside"
    spotify_user.json["display_name"] = "Daniel Ek"
    assert spotify_user.name == "Daniel Ek"


def test_playlist_property(
    spotify_user: User,
    mock_requests: Mocker,
) -> None:
    """Test that `playlist` property makes the expected request."""
    assert not hasattr(spotify_user, "_playlists")
    assert all(
        isinstance(playlist, Playlist)
        and playlist._spotify_client == spotify_user._spotify_client
        and playlist.owner == spotify_user
        for playlist in spotify_user.playlists
    )
    assert hasattr(spotify_user, "_playlists")

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            # pylint: disable=line-too-long
            {
                "url": "https://api.spotify.com/v1/me/playlists?limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/users/worgarside/playlists?offset=50&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/users/worgarside/playlists?offset=100&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/users/worgarside/playlists?offset=150&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ],
    )

    # Check subsequent calls to property don't make additional requests
    assert len(spotify_user.playlists) == 116
    assert mock_requests.call_count == 4


def test_top_artists_property(
    spotify_user: User, mock_requests: Mocker, spotify_client: SpotifyClient
) -> None:
    """Test that `top_artists` property makes the expected request."""
    top_artists = spotify_user.top_artists

    assert len(top_artists) == 50
    assert isinstance(top_artists, tuple)
    assert all(isinstance(artist, Artist) for artist in top_artists)
    assert all(artist._spotify_client == spotify_client for artist in top_artists)

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                # pylint: disable=line-too-long
                "url": "https://api.spotify.com/v1/me/top/artists?time_range=short_term&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ],
    )


def test_top_tracks_property(
    spotify_user: User, mock_requests: Mocker, spotify_client: SpotifyClient
) -> None:
    """Test that `top_tracks` property makes the expected request."""
    top_tracks = spotify_user.top_tracks

    assert len(top_tracks) == 50
    assert isinstance(top_tracks, tuple)
    assert all(isinstance(track, Track) for track in top_tracks)
    assert all(track._spotify_client == spotify_client for track in top_tracks)

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                # pylint: disable=line-too-long
                "url": "https://api.spotify.com/v1/me/top/tracks?time_range=short_term&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ],
    )


def test_tracks_property(
    spotify_user: User, mock_requests: Mocker, spotify_client: SpotifyClient
) -> None:
    """Test that `tracks` property makes the expected request."""
    assert not hasattr(spotify_user, "_tracks")
    assert all(
        isinstance(track, Track) and track._spotify_client == spotify_client
        for track in spotify_user.tracks
    )
    assert hasattr(spotify_user, "_tracks")

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "https://api.spotify.com/v1/me/tracks?limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/me/tracks?offset=50&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/me/tracks?offset=100&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/me/tracks?offset=150&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
            {
                "url": "https://api.spotify.com/v1/me/tracks?offset=200&limit=50",
                "method": "GET",
                "headers": {"Authorization": "Bearer test_access_token"},
            },
        ],
    )

    # Check subsequent calls to property don't make additional requests
    assert len(spotify_user.tracks) == 250
    assert mock_requests.call_count == 5
