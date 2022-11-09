# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.spotify.User`."""
from __future__ import annotations

from http import HTTPStatus
from unittest.mock import patch

from requests_mock import Mocker

from conftest import read_json_file
from wg_utilities.clients.spotify import (
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
            "email": "test_user_id@gmail.com",
            "explicit_content": {"filter_enabled": False, "filter_locked": False},
            "external_urls": {"spotify": "https://open.spotify.com/user/test_user_id"},
            "followers": {"href": None, "total": 13},
            "href": "https://api.spotify.com/v1/users/test_user_id",
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
            "uri": "spotify:user:test_user_id",
        },
        spotify_client=spotify_client,
    )

    assert isinstance(user, User)
    assert user._spotify_client == spotify_client
    assert user.json == {
        "country": "GB",
        "display_name": "Will Garside",
        "email": "test_user_id@gmail.com",
        "explicit_content": {"filter_enabled": False, "filter_locked": False},
        "external_urls": {"spotify": "https://open.spotify.com/user/test_user_id"},
        "followers": {"href": None, "total": 13},
        "href": "https://api.spotify.com/v1/users/test_user_id",
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
        "uri": "spotify:user:test_user_id",
    }


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

    assert (
        mock_requests.request_history[0].url
        == "https://api.spotify.com/v1/me/player/currently-playing"
    )
    assert mock_requests.request_history[0].method == "GET"
    assert (
        mock_requests.request_history[0].headers["Authorization"]
        == "Bearer test_access_token"
    )
    assert (
        mock_requests.request_history[1].url
        == "https://api.spotify.com/v1/playlists/37i9dqzf1e8pj76jxe3egf"
    )


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

    assert (
        mock_requests.request_history[0].url
        == "https://api.spotify.com/v1/me/player/devices?limit=50"
    )
    assert mock_requests.request_history[0].method == "GET"
    assert (
        mock_requests.request_history[0].headers["Authorization"]
        == "Bearer test_access_token"
    )


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

    assert (
        mock_requests.request_history[0].url
        == "https://api.spotify.com/v1/me/player/currently-playing"
    )
    assert mock_requests.request_history[0].method == "GET"
    assert (
        mock_requests.request_history[0].headers["Authorization"]
        == "Bearer test_access_token"
    )


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


def test_followed_artists_property(
    spotify_user: User, mock_requests: Mocker, spotify_client: SpotifyClient
) -> None:
    """Test that `followed_artists` property makes the expected request."""

    prefix = "spotify/me/following/type=artist&"

    assert spotify_user.followed_artists == [
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
            *read_json_file(f"{prefix}after=77bznf1dr1k5kyez6nn3jb&limit=50.json")[
                "artists"
            ][  # type: ignore[call-overload]
                "items"  # type: ignore[index]
            ],
        ]
    ]

    assert (
        mock_requests.request_history[0].url
        == "https://api.spotify.com/v1/me/following?type=artist&limit=50"
    )
    assert mock_requests.request_history[0].method == "GET"
    assert (
        mock_requests.request_history[0].headers["Authorization"]
        == "Bearer test_access_token"
    )


def test_name_property(spotify_user: User) -> None:
    """Test that `name` property returns the expected value."""
    assert spotify_user.name == "Will Garside"
    spotify_user.json["display_name"] = "Daniel Ek"
    assert spotify_user.name == "Daniel Ek"


def test_top_artists_property(
    spotify_user: User, mock_requests: Mocker, spotify_client: SpotifyClient
) -> None:
    """Test that `top_artists` property makes the expected request."""
    top_artists = spotify_user.top_artists

    assert len(top_artists) == 50
    assert isinstance(top_artists, tuple)
    assert all(isinstance(artist, Artist) for artist in top_artists)
    assert all(artist._spotify_client == spotify_client for artist in top_artists)

    assert (
        mock_requests.request_history[0].url
        == "https://api.spotify.com/v1/me/top/artists?time_range=short_term&limit=50"
    )
    assert mock_requests.request_history[0].method == "GET"
    assert (
        mock_requests.request_history[0].headers["Authorization"]
        == "Bearer test_access_token"
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

    assert (
        mock_requests.request_history[0].url
        == "https://api.spotify.com/v1/me/top/tracks?time_range=short_term&limit=50"
    )
    assert mock_requests.request_history[0].method == "GET"
    assert (
        mock_requests.request_history[0].headers["Authorization"]
        == "Bearer test_access_token"
    )
