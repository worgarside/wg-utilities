# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.spotify.Album`."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus

from requests_mock import Mocker

from conftest import assert_mock_requests_request_history, read_json_file
from wg_utilities.clients.spotify import (
    Album,
    AlbumType,
    Artist,
    SpotifyClient,
    Track,
    _AlbumInfo,
)


def test_instantiation(spotify_client: SpotifyClient) -> None:
    """Test instantiation of the Album class."""
    album_json: _AlbumInfo = read_json_file(  # type: ignore[assignment]
        "spotify/albums/7FvnTARvgjUyWnUT0flUN7.json"
    )

    album = Album(album_json, spotify_client=spotify_client)

    assert isinstance(album, Album)
    assert album._spotify_client == spotify_client


def test_artists_property(
    spotify_album: Album,
    spotify_client: SpotifyClient,
) -> None:
    """Test the `artists` property."""
    assert spotify_album.artists == [
        Artist(
            read_json_file(  # type: ignore[arg-type]
                "spotify/artists/0q8eApZJs5WDBxayY9769C.json"
            ),
            spotify_client=spotify_client,
        ),
        Artist(
            read_json_file(  # type: ignore[arg-type]
                "spotify/artists/1Ma3pJzPIrAyYPNRkp3SUF.json"
            ),
            spotify_client=spotify_client,
        ),
    ]


def test_release_date_property(spotify_album: Album) -> None:
    """Test that the `release_date` property returns the correct value."""

    assert spotify_album.release_date == datetime(2022, 3, 30).date()

    spotify_album.json["release_date_precision"] = "month"
    spotify_album.json["release_date"] = "2022-03"
    assert spotify_album.release_date == datetime(2022, 3, 1).date()

    spotify_album.json["release_date_precision"] = "year"
    spotify_album.json["release_date"] = "2022"
    assert spotify_album.release_date == datetime(2022, 1, 1).date()

    del spotify_album.json["release_date_precision"]  # type: ignore[misc]
    spotify_album.json["release_date"] = "not a date"
    assert spotify_album.release_date == "not a date"


def test_release_date_precision_property(spotify_album: Album) -> None:
    """Test that the `release_date_precision` property returns the correct value."""
    assert spotify_album.release_date_precision == "day"

    spotify_album.json["release_date_precision"] = "month"
    assert (
        spotify_album.release_date_precision
        == "month"  # type: ignore[comparison-overlap]
    )

    spotify_album.json["release_date_precision"] = "year"
    assert spotify_album.release_date_precision == "year"


def test_tracks_property(spotify_album: Album, spotify_client: SpotifyClient) -> None:
    """Test the `tracks` property."""
    assert not hasattr(spotify_album, "_tracks")
    assert spotify_album.tracks == [
        Track(
            read_json_file(  # type: ignore[arg-type]
                "spotify/tracks/1PfbIpFjsS1BayUoqB3X7O.json"
            ),
            spotify_client=spotify_client,
        ),
        Track(
            read_json_file(  # type: ignore[arg-type]
                "spotify/tracks/5U5X1TnRhnp9GogRfaE9XQ.json",
            ),
            spotify_client=spotify_client,
        ),
    ]
    assert hasattr(spotify_album, "_tracks")


def test_tracks_property_paginates(spotify_album: Album, mock_requests: Mocker) -> None:
    """Test the `tracks` property paginates when it needs to.

    I couldn't find any real responses for this, so I've just fudged it a little.
    """

    fake_next_url = (
        f"https://api.spotify.com/v1/albums/{spotify_album.id}/tracks?offset=2"
    )

    spotify_album.json["tracks"]["next"] = fake_next_url

    mock_requests.get(
        fake_next_url,
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        # This file returns tracks with no next URL
        json=read_json_file("spotify/me/tracks/offset=200&limit=50.json"),
    )

    assert not hasattr(spotify_album, "_tracks")
    assert len(spotify_album.tracks) == 52
    assert hasattr(spotify_album, "_tracks")

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": fake_next_url + "&limit=50",
                "method": "GET",
                "headers": {
                    "Authorization": "Bearer test_access_token",
                    "Content-Type": "application/json",
                },
            }
        ],
    )


def test_type_property(spotify_album: Album) -> None:
    """Test that the `type` property returns the correct value."""
    assert spotify_album.type == AlbumType.SINGLE
    spotify_album.json["album_type"] = "album"
    assert spotify_album.type == AlbumType.ALBUM
    spotify_album.json["album_type"] = "compilation"
    assert spotify_album.type == AlbumType.COMPILATION
