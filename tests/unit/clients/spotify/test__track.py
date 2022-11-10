# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.spotify.Track`."""
from __future__ import annotations

from datetime import datetime

from requests_mock import Mocker

from conftest import assert_mock_requests_request_history, read_json_file
from wg_utilities.clients.spotify import Album, Artist, SpotifyClient, Track


def test_instantiation(spotify_client: SpotifyClient) -> None:
    # pylint: disable=line-too-long
    """Test instantiation of the Track class."""
    track = Track(
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
    assert track._spotify_client == spotify_client
    assert track.json == read_json_file("spotify/tracks/27cgqh0VRhVeM61ugTnorD.json")


def test_album_property(spotify_track: Track) -> None:
    """Test that the `album` property instantiates an `Album` correctly."""

    assert isinstance(spotify_track.album, Album)

    assert spotify_track.album.json == spotify_track.json["album"]
    assert spotify_track.album._spotify_client == spotify_track._spotify_client

    api_album_response = read_json_file("spotify/albums/7FvnTARvgjUyWnUT0flUN7.json")
    for k, v in spotify_track.album.json.items():
        assert v == api_album_response[k]


def test_artists_property(spotify_track: Track) -> None:
    """Test that the `artists` property instantiates an `Artist` correctly."""
    assert len(spotify_track.artists) == 1
    assert isinstance(spotify_track.artists[0], Artist)
    assert spotify_track.artists[0].name == "DJ Seinfeld"
    assert spotify_track.artists[0].id == "37YzpfBeFju8QRZ3g0Ha1Q"
    assert spotify_track.artists[0]._spotify_client == spotify_track._spotify_client


def test_audio_features_property(spotify_track: Track, mock_requests: Mocker) -> None:
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
                    "Authorization": "Bearer test_access_token",
                    "Content-Type": "application/json",
                },
            }
        ],
    )

    assert mock_requests.call_count == 1

    # Check subsequent calls don't make a new request
    assert spotify_track.audio_features == expected
    assert mock_requests.call_count == 1


def test_release_date_property(spotify_track: Track) -> None:
    """Test that the `release_date` property returns the correct value."""

    assert spotify_track.release_date == datetime(2021, 9, 3).date()

    spotify_track.json["album"]["release_date_precision"] = "month"
    spotify_track.json["album"]["release_date"] = "2021-09"
    assert spotify_track.release_date == datetime(2021, 9, 1).date()

    spotify_track.json["album"]["release_date_precision"] = "year"
    spotify_track.json["album"]["release_date"] = "2021"
    assert spotify_track.release_date == datetime(2021, 1, 1).date()


def test_tempo_property(spotify_track: Track) -> None:
    """Test that the `tempo` property returns the correct value."""
    assert not hasattr(spotify_track, "_audio_features")
    assert spotify_track.tempo == 125.998
    assert hasattr(spotify_track, "_audio_features")

    spotify_track._audio_features["tempo"] = 420
    assert spotify_track.tempo == 420

    del spotify_track._audio_features["tempo"]  # type: ignore[misc]
    assert spotify_track.tempo is None
