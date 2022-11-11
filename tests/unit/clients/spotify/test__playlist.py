# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.spotify.Playlist`."""

from __future__ import annotations

from copy import deepcopy
from os import listdir

from pytest import mark, raises
from requests_mock import Mocker

from conftest import (
    FLAT_FILES_DIR,
    assert_mock_requests_request_history,
    read_json_file,
)
from wg_utilities.clients import SpotifyClient
from wg_utilities.clients.spotify import Playlist, Track, User


def test_instantiation(spotify_client: SpotifyClient) -> None:
    """Test that the `Playlist` class instantiates correctly."""

    playlist_json = read_json_file("spotify/playlists/37i9dqzf1e8pj76jxe3egf.json")

    playlist = Playlist(
        playlist_json, spotify_client=spotify_client  # type: ignore[arg-type]
    )

    assert isinstance(playlist, Playlist)
    assert playlist.json == playlist_json


def test_is_collaborative_property(
    spotify_playlist: Playlist, spotify_client: SpotifyClient
) -> None:
    """Test that the `is_collaborative` property returns the correct value."""

    assert not spotify_playlist.is_collaborative

    assert spotify_client.get_playlist_by_id("2wSNKxLM217jpZnkAgYZPH").is_collaborative


def test_is_public_property(
    spotify_playlist: Playlist, spotify_client: SpotifyClient
) -> None:
    """Test that the `is_public` property returns the correct value."""

    assert not spotify_playlist.is_public

    assert spotify_client.get_playlist_by_id("2wSNKxLM217jpZnkAgYZPH").is_public


def test_owner_property(
    spotify_playlist: Playlist, spotify_user: User, spotify_client: SpotifyClient
) -> None:
    """Test that the `owner` property returns the correct value."""

    assert spotify_playlist.owner == spotify_user

    assert Playlist(
        read_json_file(  # type: ignore[arg-type]
            "spotify/playlists/37i9dqzf1e8pj76jxe3egf.json"
        ),
        spotify_client=spotify_client,
    ).owner == User(
        read_json_file("spotify/users/spotify.json"),  # type: ignore[arg-type]
        spotify_client=spotify_client,
    )


def test_tracks_property(
    spotify_playlist: Playlist, spotify_client: SpotifyClient, mock_requests: Mocker
) -> None:
    """Test that the `Playlist.tracks` property returns the correct value."""

    assert not hasattr(spotify_playlist, "_tracks")
    assert all(
        isinstance(track, Track) and track._spotify_client == spotify_client
        for track in spotify_playlist.tracks
    )
    assert hasattr(spotify_playlist, "_tracks")

    expected_requests = [
        {
            # pylint: disable=line-too-long
            "url": f"https://api.spotify.com/v1/playlists/2lMx8FU0SeQ7eA5kcMlNpX/tracks?offset={(i+1)*50}&limit=50",
            "method": "GET",
            "headers": {"Authorization": "Bearer test_access_token"},
        }
        for i in range(10)
    ]
    expected_requests.insert(
        0,
        {
            # pylint: disable=line-too-long
            "url": "https://api.spotify.com/v1/playlists/2lMx8FU0SeQ7eA5kcMlNpX/tracks?limit=50",
            "method": "GET",
            "headers": {"Authorization": "Bearer test_access_token"},
        },
    )

    assert_mock_requests_request_history(
        mock_requests.request_history, expected_requests  # type: ignore[arg-type]
    )

    # Check subsequent calls to property don't make additional requests
    assert len(spotify_playlist.tracks) == 518
    assert mock_requests.call_count == 11


@mark.parametrize(  # type: ignore[misc]
    ["track_response_filename", "in_playlist"],
    zip(
        sorted(listdir(FLAT_FILES_DIR / "json" / "spotify" / "tracks")),
        (
            True,
            False,
            False,
            False,
            False,
            True,
        ),
    ),
)
def test_contains_method(
    spotify_playlist: Playlist,
    spotify_client: SpotifyClient,
    track_response_filename: str,
    in_playlist: bool,
) -> None:
    """Test that `track in playlist` statements work as expected."""
    track = Track(
        read_json_file(  # type: ignore[arg-type]
            f"spotify/tracks/{track_response_filename}"
        ),
        spotify_client=spotify_client,
    )

    assert (track in spotify_playlist) == in_playlist

    if in_playlist:
        assert track.id in [track.id for track in spotify_playlist]
    else:
        assert track.id not in [track.id for track in spotify_playlist]


def test_gt_method(spotify_playlist: Playlist, spotify_client: SpotifyClient) -> None:
    # pylint: disable=comparison-with-itself,unneeded-not
    """Test that `playlist > playlist` statements work as expected."""
    spotify_owned_playlist = Playlist(
        read_json_file(  # type: ignore[arg-type]
            "spotify/playlists/37i9dqzf1e8pj76jxe3egf.json"
        ),
        spotify_client=spotify_client,
    )

    my_other_playlist = Playlist(
        read_json_file(  # type: ignore[arg-type]
            "spotify/playlists/4vv023mazsc8ntwz4wjvil.json"
        ),
        spotify_client=spotify_client,
    )

    another_third_party_playlist = Playlist(
        read_json_file(  # type: ignore[arg-type]
            "spotify/playlists/2wsnkxlm217jpznkagyzph.json"
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

    same_name_different_owner = deepcopy(spotify_playlist)
    same_name_different_owner.json["owner"]["id"] = "spotify"
    same_name_different_owner.json["owner"]["display_name"] = "Spotify"
    same_name_different_owner.json["id"] = "abcdefghijklmnopqrstuv"

    # Same name, first is owned by me
    assert same_name_different_owner.owner != spotify_playlist.owner
    assert not spotify_playlist > same_name_different_owner

    # Same name, second is owned by me
    assert same_name_different_owner > spotify_playlist


def test_iter_method(spotify_playlist: Playlist) -> None:
    """Test that the `Playlist.__iter__` method works as expected."""
    assert all(isinstance(track, Track) for track in spotify_playlist)

    assert list(t for t in spotify_playlist) == spotify_playlist.tracks


def test_lt_method(spotify_playlist: Playlist, spotify_client: SpotifyClient) -> None:
    # pylint: disable=comparison-with-itself,unneeded-not
    """Test that `playlist < playlist` statements work as expected."""
    spotify_owned_playlist = Playlist(
        read_json_file(  # type: ignore[arg-type]
            "spotify/playlists/37i9dqzf1e8pj76jxe3egf.json"
        ),
        spotify_client=spotify_client,
    )

    my_other_playlist = Playlist(
        read_json_file(  # type: ignore[arg-type]
            "spotify/playlists/4vv023mazsc8ntwz4wjvil.json"
        ),
        spotify_client=spotify_client,
    )

    another_third_party_playlist = Playlist(
        read_json_file(  # type: ignore[arg-type]
            "spotify/playlists/2wsnkxlm217jpznkagyzph.json"
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

    same_name_different_owner = deepcopy(spotify_playlist)
    same_name_different_owner.json["owner"]["id"] = "spotify"
    same_name_different_owner.json["owner"]["display_name"] = "Spotify"
    same_name_different_owner.json["id"] = "abcdefghijklmnopqrstuv"

    # Same name, first is owned by me
    assert same_name_different_owner.owner != spotify_playlist.owner
    assert not same_name_different_owner < spotify_playlist

    # Same name, second is owned by me
    assert spotify_playlist < same_name_different_owner
