"""Unit Tests for `wg_utilities.clients.spotify.Album`."""

from __future__ import annotations

from datetime import datetime

from requests_mock import Mocker

from conftest import assert_mock_requests_request_history, read_json_file
from wg_utilities.clients.spotify import Album, Artist, SpotifyClient, Track


def test_instantiation(spotify_client: SpotifyClient) -> None:
    """Test instantiation of the Album class."""
    album_json = read_json_file(
        "albums/7FvnTARvgjUyWnUT0flUN7.json", host_name="spotify"
    )

    album = Album.from_json_response(album_json, spotify_client=spotify_client)

    assert isinstance(album, Album)
    assert album.spotify_client == spotify_client


def test_artists_property(
    spotify_album: Album,
    spotify_client: SpotifyClient,
) -> None:
    """Test the `artists` property."""
    assert spotify_album.artists == [
        Artist.from_json_response(
            read_json_file("artists/0q8eApZJs5WDBxayY9769C.json", host_name="spotify"),
            spotify_client=spotify_client,
        ),
        Artist.from_json_response(
            read_json_file("artists/1Ma3pJzPIrAyYPNRkp3SUF.json", host_name="spotify"),
            spotify_client=spotify_client,
        ),
    ]


def test_release_date_property(spotify_album: Album) -> None:
    """Test that the `release_date` property returns the correct value."""

    assert spotify_album.release_date == datetime(2022, 3, 30).date()

    spotify_album.release_date_precision = "month"
    spotify_album.release_date = "2022-03"  # type: ignore[assignment]
    assert spotify_album.release_date == datetime(2022, 3, 1).date()

    spotify_album.release_date_precision = "year"
    spotify_album.release_date = "2022"  # type: ignore[assignment]
    assert spotify_album.release_date == datetime(2022, 1, 1).date()


def test_release_date_property_validation() -> None:
    """Test that `release_date` raises a ValueError if the precision is invalid."""
    # TODO


def test_release_date_precision_property(spotify_album: Album) -> None:
    """Test that the `release_date_precision` property returns the correct value."""
    assert spotify_album.release_date_precision == "day"

    spotify_album.release_date_precision = "month"
    assert spotify_album.release_date_precision == "month"

    spotify_album.release_date_precision = "year"
    assert spotify_album.release_date_precision == "year"


def test_tracks_property(spotify_album: Album, spotify_client: SpotifyClient) -> None:
    """Test the `tracks` property."""

    assert not hasattr(spotify_album, "_tracks")
    assert spotify_album.tracks == [
        Track.from_json_response(
            read_json_file("tracks/1PfbIpFjsS1BayUoqB3X7O.json", host_name="spotify"),
            spotify_client=spotify_client,
        ),
        Track.from_json_response(
            read_json_file("tracks/5U5X1TnRhnp9GogRfaE9XQ.json", host_name="spotify"),
            spotify_client=spotify_client,
        ),
    ]
    assert hasattr(spotify_album, "_tracks")


def test_tracks_property_paginates(
    spotify_client: SpotifyClient, mock_requests: Mocker, live_jwt_token: str
) -> None:
    """Test the `tracks` property paginates when it needs to."""

    album = Album.from_json_response(
        read_json_file("albums/6tb9drnfh9z4sq0pexbbnd.json", host_name="spotify"),
        spotify_client=spotify_client,
    )

    assert not hasattr(album, "_tracks")
    assert len(album.tracks) == 125
    assert hasattr(album, "_tracks")

    assert all(isinstance(track, Track) for track in album.tracks)

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            # pylint: disable=line-too-long
            {
                "url": "https://api.spotify.com/v1/albums/6tb9drnfh9z4sq0pexbbnd/tracks?offset=50&limit=50",
                "method": "GET",
                "headers": {
                    "Authorization": f"Bearer {live_jwt_token}",
                    "Content-Type": "application/json",
                },
            },
            {
                "url": "https://api.spotify.com/v1/albums/6tb9drnfh9z4sq0pexbbnd/tracks?offset=100&limit=50",
                "method": "GET",
                "headers": {
                    "Authorization": f"Bearer {live_jwt_token}",
                    "Content-Type": "application/json",
                },
            },
        ],
    )
