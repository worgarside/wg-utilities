"""Unit Tests for `wg_utilities.clients.spotify.Track`."""
from __future__ import annotations

from datetime import date
from http import HTTPStatus

from pytest import raises
from requests import HTTPError
from requests_mock import Mocker

from tests.conftest import assert_mock_requests_request_history
from wg_utilities.clients.spotify import Album, Artist, SpotifyClient, Track


def test_instantiation(spotify_client: SpotifyClient) -> None:
    # pylint: disable=line-too-long
    """Test instantiation of the Track class."""
    track = Track.from_json_response(
        {
            "album": {
                "album_type": "album",
                "artists": [
                    {
                        "external_urls": {
                            "spotify": "https://open.spotify.com/artist/37YzpfBeFju8QRZ3g0Ha1Q"
                        },
                        "href": "https://api.spotify.com/v1/artists/37YzpfBeFju8QRZ3g0Ha1Q",
                        "id": "37YzpfBeFju8QRZ3g0Ha1Q",
                        "name": "DJ Seinfeld",
                        "type": "artist",
                        "uri": "spotify:artist:37YzpfBeFju8QRZ3g0Ha1Q",
                    }
                ],
                "available_markets": [],
                "external_urls": {
                    "spotify": "https://open.spotify.com/album/7FvnTARvgjUyWnUT0flUN7"
                },
                "href": "https://api.spotify.com/v1/albums/7FvnTARvgjUyWnUT0flUN7",
                "id": "7FvnTARvgjUyWnUT0flUN7",
                "images": [
                    {
                        "height": 640,
                        "url": "https://i.scdn.co/image/ab67616d0000b27357751ae9890e997676b998f2",
                        "width": 640,
                    },
                    {
                        "height": 300,
                        "url": "https://i.scdn.co/image/ab67616d00001e0257751ae9890e997676b998f2",
                        "width": 300,
                    },
                    {
                        "height": 64,
                        "url": "https://i.scdn.co/image/ab67616d0000485157751ae9890e997676b998f2",
                        "width": 64,
                    },
                ],
                "name": "Mirrors",
                "release_date": "2021-09-03",
                "release_date_precision": "day",
                "total_tracks": 10,
                "type": "album",
                "uri": "spotify:album:7FvnTARvgjUyWnUT0flUN7",
            },
            "artists": [
                {
                    "external_urls": {
                        "spotify": "https://open.spotify.com/artist/37YzpfBeFju8QRZ3g0Ha1Q"
                    },
                    "href": "https://api.spotify.com/v1/artists/37YzpfBeFju8QRZ3g0Ha1Q",
                    "id": "37YzpfBeFju8QRZ3g0Ha1Q",
                    "name": "DJ Seinfeld",
                    "type": "artist",
                    "uri": "spotify:artist:37YzpfBeFju8QRZ3g0Ha1Q",
                }
            ],
            "available_markets": [],
            "disc_number": 1,
            "duration_ms": 296360,
            "explicit": False,
            "external_ids": {"isrc": "GBCFB2100390"},
            "external_urls": {
                "spotify": "https://open.spotify.com/track/27cgqh0VRhVeM61ugTnorD"
            },
            "href": "https://api.spotify.com/v1/tracks/27cgqh0VRhVeM61ugTnorD",
            "id": "27cgqh0VRhVeM61ugTnorD",
            "is_local": False,
            "name": "These Things Will Come To Be",
            "popularity": 56,
            "preview_url": "https://p.scdn.co/mp3-preview/6e7e31ce91fa7523d807ef6aee98d93e4fe4c8ba?cid=230c2ac940f14f9aa4294af862300e9b",  # pylint: disable=line-too-long  # noqa: E501
            "track_number": 6,
            "type": "track",
            "uri": "spotify:track:27cgqh0VRhVeM61ugTnorD",
        },
        spotify_client=spotify_client,
    )

    assert isinstance(track, Track)
    assert track.album.name == "Mirrors"
    assert track.id == "27cgqh0VRhVeM61ugTnorD"
    assert track.name == "These Things Will Come To Be"
    assert track.spotify_client == spotify_client


def test_album_property(spotify_track: Track) -> None:
    """Test that the `album` property instantiates an `Album` correctly."""

    assert isinstance(spotify_track.album, Album)

    assert spotify_track.album.spotify_client == spotify_track.spotify_client


def test_artist_property(spotify_track: Track) -> None:
    """Test that the `artist` property instantiates an `Artist` correctly."""
    assert isinstance(spotify_track.artist, Artist)
    assert spotify_track.artist.name == "DJ Seinfeld"
    assert spotify_track.artist.id == "37YzpfBeFju8QRZ3g0Ha1Q"
    assert spotify_track.artist.spotify_client == spotify_track.spotify_client


def test_artists_property(spotify_track: Track) -> None:
    """Test that the `artists` property instantiates an `Artist` correctly."""
    assert len(spotify_track.artists) == 1
    assert isinstance(spotify_track.artists[0], Artist)
    assert spotify_track.artists[0].name == "DJ Seinfeld"
    assert spotify_track.artists[0].id == "37YzpfBeFju8QRZ3g0Ha1Q"
    assert spotify_track.artists[0].spotify_client == spotify_track.spotify_client


def test_audio_features_property(
    spotify_track: Track, mock_requests: Mocker, live_jwt_token: str
) -> None:
    """Test that the `audio_features` property makes the correct request."""

    expected = {
        "danceability": 0.674,
        "energy": 0.74,
        "key": 4,
        "loudness": -9.138,
        "mode": 1,
        "speechiness": 0.0504,
        "acousticness": 0.515,
        "instrumentalness": 0.818,
        "liveness": 0.319,
        "valence": 0.166,
        "tempo": 125.998,
        "type": "audio_features",
        "id": "27cgqh0VRhVeM61ugTnorD",
        "uri": "spotify:track:27cgqh0VRhVeM61ugTnorD",
        "track_href": "https://api.spotify.com/v1/tracks/27cgqh0VRhVeM61ugTnorD",
        # pylint: disable=line-too-long
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/27cgqh0VRhVeM61ugTnorD",
        "duration_ms": 296360,
        "time_signature": 4,
    }

    assert spotify_track.audio_features == expected

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                # pylint: disable=line-too-long
                "url": "https://api.spotify.com/v1/audio-features/27cgqh0VRhVeM61ugTnorD",
                "method": "GET",
                "headers": {
                    "Authorization": f"Bearer {live_jwt_token}",
                    "Content-Type": "application/json",
                },
            }
        ],
    )

    assert mock_requests.call_count == 1

    # Check subsequent calls don't make a new request
    assert spotify_track.audio_features == expected
    assert mock_requests.call_count == 1


def test_audio_features_not_found(
    spotify_client: SpotifyClient, mock_requests: Mocker
) -> None:
    """Test that when a track doesn't have audio features, no exceptions are raised."""

    track = spotify_client.get_track_by_id("0YHujB8olZYDC3GwYEHbG8")

    assert track.name == "January 1st 2022"
    assert track.artists[0].name == "Fred again.."
    assert track.album.name == "Actual Life 3 (January 1 - September 9 2022)"

    mock_requests.get(
        f"{spotify_client.BASE_URL}/audio-features/0YHujB8olZYDC3GwYEHbG8",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        reason=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
    )

    with raises(HTTPError) as exc_info:
        _ = track.audio_features

    assert str(exc_info.value) == (
        "500 Server Error: Internal Server Error for url: "
        "https://api.spotify.com/v1/audio-features/0YHujB8olZYDC3GwYEHbG8"
    )

    mock_requests.get(
        f"{spotify_client.BASE_URL}/audio-features/0YHujB8olZYDC3GwYEHbG8",
        status_code=HTTPStatus.NOT_FOUND,
        reason=HTTPStatus.NOT_FOUND.phrase,
    )

    assert not track.audio_features


def test_release_date_property(spotify_track: Track, spotify_album: Album) -> None:
    """Test that the `release_date` property returns the correct value."""
    assert spotify_track.release_date == date(2021, 9, 3)

    for track in spotify_album.tracks:
        assert track.release_date == spotify_album.release_date


def test_tempo_property(spotify_track: Track) -> None:
    """Test that the `tempo` property returns the correct value."""
    assert not hasattr(spotify_track, "_audio_features")
    assert spotify_track.tempo == 125.998
    assert hasattr(spotify_track, "_audio_features")

    spotify_track.audio_features.tempo = 420  # type: ignore[union-attr]
    assert spotify_track.tempo == 420

    del spotify_track.audio_features.tempo  # type: ignore[union-attr]
    assert spotify_track.tempo is None
