# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.spotify.User`."""
from __future__ import annotations

from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Literal
from unittest.mock import patch

from freezegun import freeze_time
from pytest import FixtureRequest, mark, raises
from requests_mock import Mocker

from tests.conftest import assert_mock_requests_request_history, read_json_file
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
    """Test instantiation of User class."""

    user = User.from_json_response(
        {  # type: ignore[arg-type]
            "country": "GB",
            "display_name": "Will Garside",
            "email": "test_email_address@gmail.com",
            "explicit_content": {"filter_enabled": False, "filter_locked": False},
            "external_urls": {"spotify": "https://open.spotify.com/user/worgarside"},
            "followers": {"href": None, "total": 13},
            "href": f"{SpotifyClient.BASE_URL}/users/worgarside",
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
    assert user.spotify_client == spotify_client
    assert user.dict(exclude_none=True, exclude_unset=True) == {
        "country": "GB",
        "display_name": "Will Garside",
        "email": "test_email_address@gmail.com",
        "explicit_content": {"filter_enabled": False, "filter_locked": False},
        "external_urls": {"spotify": "https://open.spotify.com/user/worgarside"},
        "followers": {"href": None, "total": 13},
        "href": f"{SpotifyClient.BASE_URL}/users/worgarside",
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


def test_set_user_name_value(spotify_user: User) -> None:
    """Test that `display_name` property returns the expected value."""
    assert spotify_user.name == "Will Garside"

    assert "name" not in read_json_file("v1/me.json", host_name="spotify")


def test_get_playlists_by_name_unique_names(
    spotify_user: User, spotify_playlist: Playlist
) -> None:
    """Test that the `get_playlists_by_name` searches the User's playlists correctly."""

    result = spotify_user.get_playlists_by_name("Chill Electronica", return_all=False)

    assert result == spotify_playlist


def test_get_playlists_by_name_duplicate_names(
    spotify_user: User, spotify_playlist: Playlist
) -> None:
    """Test that the `get_playlists_by_name` searches the User's playlists correctly.

    This test requires that the User has two playlists with the same name, and the
    easiest way to do that is to patch the `playlists` property to return the usual
    result, but doubled.
    """

    user_playlists = spotify_user.playlists
    spotify_user._set_private_attr("_playlists", user_playlists + user_playlists)

    result = spotify_user.get_playlists_by_name("Chill Electronica", return_all=True)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == spotify_playlist
    assert result[1] == spotify_playlist


def test_get_playlists_by_name_no_matches(spotify_user: User) -> None:
    """Test that `get_playlists_by_name` returns None if no matches are found."""

    assert spotify_user.get_playlists_by_name("Bad Music", return_all=False) is None
    assert spotify_user.get_playlists_by_name("Bad Music", return_all=True) == []


def test_get_recently_liked_tracks_track_limit(
    spotify_user: User,
    spotify_client: SpotifyClient,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test that the expected number of tracks are returned by the method."""
    result = spotify_user.get_recently_liked_tracks(track_limit=150)

    assert len(result) == 150
    assert isinstance(result, list)
    assert all(isinstance(track, Track) for track in result)
    assert all(track.spotify_client == spotify_client for track in result)

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?offset=50&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?offset=100&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )


# Freezing time to when I wrote this test, otherwise the hardcoded values in the flat
# files will be out of date.
@freeze_time("2022-11-11")
def test_get_recently_liked_tracks_day_limit(
    spotify_user: User,
    spotify_client: SpotifyClient,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test that the expected number of tracks are returned by the method."""

    result = spotify_user.get_recently_liked_tracks(day_limit=7)

    assert result
    assert isinstance(result, list)
    assert all(isinstance(track, Track) for track in result)
    assert all(track.spotify_client == spotify_client for track in result)
    assert all(
        track.metadata["saved_at"] > datetime.utcnow() - timedelta(days=7)
        for track in result
    )
    assert not any(
        track.metadata["saved_at"] <= datetime.utcnow() - timedelta(days=7)
        for track in result
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )


@mark.parametrize(
    ["entity_fixture", "request_values"],
    [
        (
            "spotify_album",
            {
                "url": f"{SpotifyClient.BASE_URL}/me/albums?ids=4julBAGYv4WmRXwhjJ2LPD",
                "headers": {},
            },
        ),
        # pylint: disable=line-too-long
        (
            "spotify_artist",
            {
                "url": f"{SpotifyClient.BASE_URL}/me/following?type=artist&ids=1Ma3pJzPIrAyYPNRkp3SUF",
                "headers": {},
            },
        ),
        (
            "spotify_playlist",
            {
                "url": f"{SpotifyClient.BASE_URL}/playlists/2lMx8FU0SeQ7eA5kcMlNpX/followers?ids=worgarside",
                "headers": {},
            },
        ),
        (
            "spotify_track",
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?ids=27cgqh0VRhVeM61ugTnorD",
                "headers": {},
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
    live_jwt_token: str,
) -> None:
    """Test that `save` method makes the expected request per entity."""
    entity = request.getfixturevalue(entity_fixture)

    spotify_user.save(entity=entity)

    request_values["headers"][
        "Authorization"
    ] = f"Bearer {live_jwt_token}"  # type: ignore[index]
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
        read_json_file("spotify/v1/me/player/devices/limit=50.json")["devices"][
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


def test_albums_property(
    spotify_user: User, mock_requests: Mocker, live_jwt_token: str
) -> None:
    """Test that `albums` property makes the expected request."""

    assert not hasattr(spotify_user, "_albums")
    assert all(
        isinstance(album, Album) and album.spotify_client == spotify_user.spotify_client
        for album in spotify_user.albums
    )
    assert hasattr(spotify_user, "_albums")

    assert mock_requests.call_count == 2

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"{SpotifyClient.BASE_URL}/me/albums?limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/me/albums?offset=50&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )

    # Check subsequent calls to property don't make additional requests
    assert len(spotify_user._albums) == 80
    assert mock_requests.call_count == 2


def test_artists_property(
    spotify_user: User,
    mock_requests: Mocker,
    spotify_client: SpotifyClient,
    live_jwt_token: str,
) -> None:
    """Test that `artists` property makes the expected request."""

    prefix = "spotify/v1/me/following/type=artist&"

    assert spotify_user.artists == [
        Artist.from_json_response(artist_json, spotify_client=spotify_client)
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
                "url": f"{SpotifyClient.BASE_URL}/me/following?type=artist&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/me/following?type=artist&after=3iOvXCl6edW5Um0fXEBRXy&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/me/following?type=artist&after=77BznF1Dr1k5KyEZ6Nn3jB&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )

    assert mock_requests.call_count == 3


def test_current_track_property(
    spotify_user: User,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test that `current_track` property makes the expected request."""

    assert spotify_user.current_track == Track.from_json_response(
        read_json_file(  # type: ignore[arg-type]
            "spotify/v1/tracks/6zJUp1ihdid6Kn3Ndgcy82.json"
        ),
        spotify_client=spotify_user.spotify_client,
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"{SpotifyClient.BASE_URL}/me/player/currently-playing",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )

    assert mock_requests.call_count == 1


def test_current_track_nothing_playing(
    spotify_user: User, mock_requests: Mocker
) -> None:
    """Test that `current_track` property returns None if nothing is playing."""
    mock_requests.get(
        f"{SpotifyClient.BASE_URL}/me/player/currently-playing",
        status_code=HTTPStatus.NO_CONTENT,
        reason=HTTPStatus.NO_CONTENT.phrase,
    )

    assert spotify_user.current_track is None


def test_current_playlist_property(
    spotify_user: User,
    mock_requests: Mocker,
    spotify_playlist: Playlist,
    live_jwt_token: str,
) -> None:
    """Test that `current_playlist` property makes the expected request."""
    assert not mock_requests.request_history

    with patch.object(
        spotify_user.spotify_client,
        "get_playlist_by_id",
        wraps=spotify_user.spotify_client.get_playlist_by_id,
    ) as mock_get_playlist_by_id:
        assert spotify_user.current_playlist == spotify_playlist

    mock_get_playlist_by_id.assert_called_once_with("2lMx8FU0SeQ7eA5kcMlNpX")

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"{SpotifyClient.BASE_URL}/me/player/currently-playing",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/playlists/2lMx8FU0SeQ7eA5kcMlNpX",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )

    assert mock_requests.call_count == 2


def test_current_playlist_nothing_playing(
    spotify_user: User, mock_requests: Mocker
) -> None:
    """Test that `current_playlist` property returns None if nothing is playing."""
    mock_requests.get(
        f"{SpotifyClient.BASE_URL}/me/player/currently-playing",
        status_code=HTTPStatus.NO_CONTENT,
        reason=HTTPStatus.NO_CONTENT.phrase,
    )

    assert spotify_user.current_playlist is None


def test_devices_property(
    spotify_user: User, mock_requests: Mocker, live_jwt_token: str
) -> None:
    """Test that `devices` property makes the expected request."""

    assert spotify_user.devices == [
        Device.parse_obj(device_json)
        for device_json in read_json_file(
            "spotify/v1/me/player/devices/limit=50.json"
        )[  # type: ignore[union-attr]
            "devices"
        ]
    ]

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"{SpotifyClient.BASE_URL}/me/player/devices?limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )


def test_name_property(spotify_user: User) -> None:
    """Test that `name` property returns the expected value."""
    assert spotify_user.name == "Will Garside"


def test_playlist_property(
    spotify_user: User,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test that `playlist` property makes the expected request."""
    assert not hasattr(spotify_user, "_playlists")
    assert all(
        isinstance(playlist, Playlist)
        and playlist.spotify_client == spotify_user.spotify_client
        and playlist.owner == spotify_user
        for playlist in spotify_user.playlists
    )
    assert hasattr(spotify_user, "_playlists")

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            # pylint: disable=line-too-long
            {
                "url": f"{SpotifyClient.BASE_URL}/me/playlists?limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/users/worgarside/playlists?offset=50&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/users/worgarside/playlists?offset=100&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/users/worgarside/playlists?offset=150&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )

    # Check subsequent calls to property don't make additional requests
    assert len(spotify_user.playlists) == 116
    assert mock_requests.call_count == 4


def test_top_artists_property(
    spotify_user: User,
    mock_requests: Mocker,
    spotify_client: SpotifyClient,
    live_jwt_token: str,
) -> None:
    """Test that `top_artists` property makes the expected request."""
    top_artists = spotify_user.top_artists

    assert len(top_artists) == 50
    assert isinstance(top_artists, tuple)
    assert all(isinstance(artist, Artist) for artist in top_artists)
    assert all(artist.spotify_client == spotify_client for artist in top_artists)

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                # pylint: disable=line-too-long
                "url": f"{SpotifyClient.BASE_URL}/me/top/artists?time_range=short_term&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )


def test_top_tracks_property(
    spotify_user: User,
    mock_requests: Mocker,
    spotify_client: SpotifyClient,
    live_jwt_token: str,
) -> None:
    """Test that `top_tracks` property makes the expected request."""
    top_tracks = spotify_user.top_tracks

    assert len(top_tracks) == 50
    assert isinstance(top_tracks, tuple)
    assert all(isinstance(track, Track) for track in top_tracks)
    assert all(track.spotify_client == spotify_client for track in top_tracks)

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                # pylint: disable=line-too-long
                "url": f"{SpotifyClient.BASE_URL}/me/top/tracks?time_range=short_term&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )


def test_tracks_property(
    spotify_user: User,
    mock_requests: Mocker,
    spotify_client: SpotifyClient,
    live_jwt_token: str,
) -> None:
    """Test that `tracks` property makes the expected request."""
    assert not hasattr(spotify_user, "_tracks")
    assert all(
        isinstance(track, Track) and track.spotify_client == spotify_client
        for track in spotify_user.tracks
    )
    assert hasattr(spotify_user, "_tracks")

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?offset=50&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?offset=100&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?offset=150&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
            {
                "url": f"{SpotifyClient.BASE_URL}/me/tracks?offset=200&limit=50",
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            },
        ],
    )

    # Check subsequent calls to property don't make additional requests
    assert len(spotify_user.tracks) == 250
    assert mock_requests.call_count == 5


@mark.parametrize(
    "properties_to_reset",
    [
        None,
        ("albums",),
        ("artists",),
        ("playlists",),
        ("top_artists",),
        ("top_tracks",),
        ("tracks",),
        ("artists", "playlists", "top_artists", "top_tracks", "tracks"),
        ("albums", "playlists", "top_artists", "top_tracks", "tracks"),
        ("albums", "artists", "top_artists", "top_tracks", "tracks"),
        ("albums", "artists", "playlists", "top_tracks", "tracks"),
        ("albums", "artists", "playlists", "top_artists", "tracks"),
        ("albums", "artists", "playlists", "top_artists", "top_tracks"),
        ("top_tracks", "artists", "tracks", "top_artists"),
        ("top_tracks", "top_artists", "tracks"),
        ("albums", "tracks", "top_artists", "playlists", "artists"),
        ("top_artists", "albums"),
        ("top_tracks", "tracks", "playlists", "top_artists"),
        ("artists", "tracks", "albums", "playlists"),
        ("tracks", "albums", "top_tracks", "top_artists", "playlists"),
        ("artists", "top_artists", "albums", "top_tracks"),
        ("albums", "top_tracks", "tracks", "top_artists"),
        ("top_tracks", "albums", "top_artists", "artists", "tracks"),
        ("artists", "tracks", "top_tracks", "playlists", "albums"),
        ("playlists", "artists", "top_tracks", "albums", "tracks"),
        ("playlists", "top_tracks", "tracks", "top_artists", "albums"),
        ("albums", "artists", "tracks", "top_tracks", "playlists"),
        ("playlists", "tracks", "top_tracks", "top_artists", "artists"),
        ("top_tracks", "top_artists", "tracks", "artists", "playlists"),
        ("tracks", "playlists", "top_artists", "top_tracks", "artists"),
        ("tracks", "albums", "top_tracks", "playlists", "artists"),
        ("albums", "playlists", "top_artists", "tracks", "top_tracks"),
        ("albums", "artists", "top_tracks", "top_artists"),
    ],
)
def test_reset_properties(
    spotify_user: User,
    properties_to_reset: list[
        Literal[
            "albums",
            "artists",
            "playlists",
            "top_artists",
            "top_tracks",
            "tracks",
        ]
    ]
    | None,
    mock_requests: Mocker,
) -> None:
    """Test that `reset_properties` resets the properties of the user."""

    attr_names = (
        "_albums",
        "_artists",
        "_playlists",
        "_top_artists",
        "_top_tracks",
        "_tracks",
    )

    for attr in attr_names:
        assert not hasattr(spotify_user, attr)

    _ = spotify_user.albums
    _ = spotify_user.artists
    _ = spotify_user.playlists
    _ = spotify_user.top_artists
    _ = spotify_user.top_tracks
    _ = spotify_user.tracks

    for attr in attr_names:
        assert hasattr(spotify_user, attr)

    spotify_user.reset_properties(properties_to_reset)

    if properties_to_reset is None:
        for attr in attr_names:
            assert not hasattr(spotify_user, attr)
            getattr(spotify_user, attr.lstrip("_"))
            assert hasattr(spotify_user, attr)
    else:
        for attr in attr_names:
            if (prop_name := attr.lstrip("_")) in properties_to_reset:
                assert not hasattr(spotify_user, attr)
                getattr(spotify_user, prop_name)
                assert hasattr(spotify_user, attr)
            else:
                assert hasattr(spotify_user, attr)
                mock_requests.reset_mock()
                getattr(spotify_user, prop_name)
                assert mock_requests.call_count == 0


def test_playlist_refresh_time(spotify_user: User, mock_requests: Mocker) -> None:
    """Test that `playlist` property refreshes after 15 minutes."""

    assert not mock_requests.request_history

    with freeze_time(frozen_time := datetime.utcnow()):
        assert not hasattr(spotify_user, "_playlist_refresh_time")
        _ = spotify_user.playlists

    assert spotify_user._playlist_refresh_time == frozen_time

    # There are 4 pages for the test Playlist response
    assert len(mock_requests.request_history) == 4

    with freeze_time(frozen_time + timedelta(minutes=14, seconds=59)):
        _ = spotify_user.playlists
        assert spotify_user._playlist_refresh_time == frozen_time

    assert len(mock_requests.request_history) == 4

    with freeze_time(new_frozen_time := frozen_time + timedelta(minutes=15, seconds=1)):
        _ = spotify_user.playlists
        assert spotify_user._playlist_refresh_time == new_frozen_time

    assert len(mock_requests.request_history) == 8
