# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.spotify.Playlist`."""

from __future__ import annotations

from datetime import datetime, timedelta
from os import listdir

from freezegun import freeze_time
from pytest import mark, raises
from requests_mock import Mocker

from tests.conftest import (
    FLAT_FILES_DIR,
    assert_mock_requests_request_history,
    read_json_file,
)
from tests.unit.clients.spotify.conftest import snapshot_id_request
from wg_utilities.clients import SpotifyClient
from wg_utilities.clients.spotify import Playlist, Track, User

SPOTIFY_PLAYLIST_ALT_SNAPSHOT_ID = (
    "MzI1LGE0MDI4NzhiZGUzYWU3ZDY0MzFjYmI5ZGVjOGFmMDhlMGE0N2Y4ZTE="
)


def test_instantiation(spotify_client: SpotifyClient) -> None:
    """Test that the `Playlist` class instantiates correctly."""

    playlist_json = read_json_file("spotify/v1/playlists/37i9dqzf1e8pj76jxe3egf.json")

    playlist = Playlist.from_json_response(
        playlist_json, spotify_client=spotify_client  # type: ignore[arg-type]
    )

    assert isinstance(playlist, Playlist)
    assert playlist.dict() == playlist_json


def test_owner_property(
    spotify_playlist: Playlist, spotify_user: User, spotify_client: SpotifyClient
) -> None:
    """Test that the `owner` property returns the correct value."""

    assert spotify_playlist.owner == spotify_user

    assert Playlist.from_json_response(
        read_json_file("v1/playlists/37i9dqzf1e8pj76jxe3egf.json", host_name="spotify"),
        spotify_client=spotify_client,
    ).owner == User.from_json_response(
        read_json_file("v1/users/spotify.json", host_name="spotify"),
        spotify_client=spotify_client,
    )


def test_tracks_property(
    spotify_playlist: Playlist,
    spotify_client: SpotifyClient,
    mock_requests: Mocker,
    live_jwt_token: str,
) -> None:
    """Test that the `Playlist.tracks` property returns the correct value."""

    assert not hasattr(spotify_playlist, "_tracks")
    assert all(
        isinstance(track, Track) and track.spotify_client == spotify_client
        for track in spotify_playlist.tracks
    )
    assert hasattr(spotify_playlist, "_tracks")

    expected_requests = [
        {
            # pylint: disable=line-too-long
            "url": f"{SpotifyClient.BASE_URL}/playlists/2lMx8FU0SeQ7eA5kcMlNpX/tracks?offset={(i+1)*50}&limit=50",
            "method": "GET",
            "headers": {"Authorization": f"Bearer {live_jwt_token}"},
        }
        for i in range(10)
    ]
    expected_requests.insert(
        0,
        {
            # pylint: disable=line-too-long
            "url": f"{SpotifyClient.BASE_URL}/playlists/2lMx8FU0SeQ7eA5kcMlNpX/tracks?limit=50",
            "method": "GET",
            "headers": {"Authorization": f"Bearer {live_jwt_token}"},
        },
    )

    assert_mock_requests_request_history(
        mock_requests.request_history, expected_requests  # type: ignore[arg-type]
    )

    # Check subsequent calls to property don't make additional requests
    assert len(spotify_playlist.tracks) == 514
    assert mock_requests.call_count == 11


@mark.parametrize(
    ["track_response_filename", "in_playlist"],
    zip(
        sorted(listdir(FLAT_FILES_DIR / "json" / "spotify" / "v1" / "tracks")),
        (
            False,
            True,
            False,
            False,
            False,
            False,
            True,
        ),
        strict=True,
    ),
)
def test_contains_method(
    spotify_playlist: Playlist,
    spotify_client: SpotifyClient,
    track_response_filename: str,
    in_playlist: bool,
) -> None:
    """Test that `track in playlist` statements work as expected."""
    track = Track.from_json_response(
        read_json_file(  # type: ignore[arg-type]
            f"spotify/v1/tracks/{track_response_filename}"
        ),
        spotify_client=spotify_client,
    )

    assert (track in spotify_playlist) == in_playlist

    if in_playlist:
        assert track.id in [track.id for track in spotify_playlist]
    else:
        assert track.id not in [track.id for track in spotify_playlist]


def test_gt_method(spotify_playlist: Playlist, spotify_client: SpotifyClient) -> None:
    # pylint: disable=comparison-with-itself
    """Test that `playlist > playlist` statements work as expected."""
    spotify_owned_playlist = Playlist.from_json_response(
        read_json_file(  # type: ignore[arg-type]
            "spotify/v1/playlists/37i9dqzf1e8pj76jxe3egf.json"
        ),
        spotify_client=spotify_client,
    )

    my_other_playlist = Playlist.from_json_response(
        read_json_file(  # type: ignore[arg-type]
            "spotify/v1/playlists/4vv023mazsc8ntwz4wjvil.json"
        ),
        spotify_client=spotify_client,
    )

    another_third_party_playlist = Playlist.from_json_response(
        read_json_file(  # type: ignore[arg-type]
            "spotify/v1/playlists/2wsnkxlm217jpznkagyzph.json"
        ),
        spotify_client=spotify_client,
    )

    assert (
        spotify_owned_playlist
        > my_other_playlist
        > spotify_playlist
        > another_third_party_playlist
    )

    with raises(TypeError) as exc_info:
        assert spotify_playlist > "not a Playlist"

    assert (
        str(exc_info.value)
        == "'>' not supported between instances of 'Playlist' and 'str'"
    )

    # Special cases:
    assert not spotify_playlist > spotify_playlist
    assert not spotify_owned_playlist > spotify_owned_playlist


def test_iter_method(spotify_playlist: Playlist) -> None:
    """Test that the `Playlist.__iter__` method works as expected."""
    assert all(isinstance(track, Track) for track in spotify_playlist)

    assert list(spotify_playlist) == spotify_playlist.tracks


def test_lt_method(spotify_playlist: Playlist, spotify_client: SpotifyClient) -> None:
    # pylint: disable=comparison-with-itself
    """Test that `playlist < playlist` statements work as expected."""
    spotify_owned_playlist = Playlist.from_json_response(
        read_json_file(  # type: ignore[arg-type]
            "spotify/v1/playlists/37i9dqzf1e8pj76jxe3egf.json"
        ),
        spotify_client=spotify_client,
    )

    my_other_playlist = Playlist.from_json_response(
        read_json_file(  # type: ignore[arg-type]
            "spotify/v1/playlists/4vv023mazsc8ntwz4wjvil.json"
        ),
        spotify_client=spotify_client,
    )

    another_third_party_playlist = Playlist.from_json_response(
        read_json_file(  # type: ignore[arg-type]
            "spotify/v1/playlists/2wsnkxlm217jpznkagyzph.json"
        ),
        spotify_client=spotify_client,
    )

    assert (
        another_third_party_playlist
        < spotify_playlist
        < my_other_playlist
        < spotify_owned_playlist
    )

    with raises(TypeError) as exc_info:
        assert spotify_playlist < "not a Playlist"

    assert (
        str(exc_info.value)
        == "'<' not supported between instances of 'Playlist' and 'str'"
    )

    # Special cases:
    assert not spotify_playlist < spotify_playlist
    assert not spotify_owned_playlist < spotify_owned_playlist


def test_live_snapshot_id(
    spotify_playlist_alt: Playlist,
) -> None:
    """Test that the `Playlist.live_snapshot_id` property works as expected."""

    assert spotify_playlist_alt.snapshot_id == SPOTIFY_PLAYLIST_ALT_SNAPSHOT_ID

    assert not hasattr(spotify_playlist_alt, "_live_snapshot_id")
    assert not hasattr(spotify_playlist_alt, "_live_snapshot_id_timestamp")

    with freeze_time(frozen_time := datetime.utcnow()):
        # Because a different value is in the `fields=snapshot_id.json` stub
        assert spotify_playlist_alt.live_snapshot_id != spotify_playlist_alt.snapshot_id

    assert spotify_playlist_alt._live_snapshot_id != spotify_playlist_alt.snapshot_id

    assert spotify_playlist_alt._live_snapshot_id_timestamp == frozen_time

    assert spotify_playlist_alt._live_snapshot_id == "new-snapshot-id"
    assert spotify_playlist_alt.live_snapshot_id == "new-snapshot-id"

    assert spotify_playlist_alt.snapshot_id == SPOTIFY_PLAYLIST_ALT_SNAPSHOT_ID


def test_tracks_property_updates_snapshot_id(
    spotify_playlist_alt: Playlist, mock_requests: Mocker, live_jwt_token: str
) -> None:
    """Test that the `Playlist.tracks` property updates the snapshot ID correctly."""

    track_requests: list[dict[str, str | dict[str, str]]] = [
        {
            # pylint: disable=line-too-long
            "url": f"{SpotifyClient.BASE_URL}/playlists/{spotify_playlist_alt.id}/tracks?limit=50",
            "method": "GET",
            "headers": {"Authorization": f"Bearer {live_jwt_token}"},
        },
    ]

    track_requests.extend(
        [
            {
                # pylint: disable=line-too-long
                "url": f"{SpotifyClient.BASE_URL}/playlists/{spotify_playlist_alt.id}/tracks?offset={(i+1)*50}&limit=50",  # noqa: E501
                "method": "GET",
                "headers": {"Authorization": f"Bearer {live_jwt_token}"},
            }
            for i in range(7)
        ]
    )

    assert spotify_playlist_alt.snapshot_id == SPOTIFY_PLAYLIST_ALT_SNAPSHOT_ID

    # First call should add a value to the `_live_snapshot_id` attribute
    _ = spotify_playlist_alt.tracks

    assert (
        spotify_playlist_alt.snapshot_id
        == spotify_playlist_alt._live_snapshot_id
        == SPOTIFY_PLAYLIST_ALT_SNAPSHOT_ID
    )

    assert_mock_requests_request_history(mock_requests.request_history, track_requests)

    mock_requests.reset_mock()

    # Second call should be update `snapshot_id` to the new value
    _ = spotify_playlist_alt.tracks

    assert (
        spotify_playlist_alt.snapshot_id
        == spotify_playlist_alt._live_snapshot_id
        == "new-snapshot-id"
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [snapshot_id_request(spotify_playlist_alt.id, live_jwt_token), *track_requests],
    )

    mock_requests.reset_mock()

    # Third call should not make any requests
    _ = spotify_playlist_alt.tracks

    assert not mock_requests.request_history

    mock_requests.reset_mock()

    # After a minute the only call should be to check the snapshot ID

    with freeze_time(frozen_time := datetime.utcnow() + timedelta(minutes=1)):
        _ = spotify_playlist_alt.tracks

    assert spotify_playlist_alt._live_snapshot_id_timestamp == frozen_time

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [snapshot_id_request(spotify_playlist_alt.id, live_jwt_token)],
    )
