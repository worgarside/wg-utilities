# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.spotify.Artist`."""

from __future__ import annotations

from wg_utilities.clients.spotify import Album, Artist, SpotifyClient, _ArtistInfo


def test_instantiation(spotify_client: SpotifyClient) -> None:
    """Test instantiation of the Artist class."""
    artist_json: _ArtistInfo = {
        "external_urls": {
            "spotify": "https://open.spotify.com/artist/1Ma3pJzPIrAyYPNRkp3SUF"
        },
        "followers": {"href": None, "total": 147955},
        "genres": ["deep house", "electronica", "float house", "lo-fi house"],
        "href": "https://api.spotify.com/v1/artists/1Ma3pJzPIrAyYPNRkp3SUF",
        "id": "1Ma3pJzPIrAyYPNRkp3SUF",
        "images": [
            # pylint: disable=line-too-long
            {
                "height": 640,
                "url": "https://i.scdn.co/image/ab6761610000e5eb220be919258c7391c5c0727b",
                "width": 640,
            },
            {
                "height": 320,
                "url": "https://i.scdn.co/image/ab67616100005174220be919258c7391c5c0727b",
                "width": 320,
            },
            {
                "height": 160,
                "url": "https://i.scdn.co/image/ab6761610000f178220be919258c7391c5c0727b",
                "width": 160,
            },
        ],
        "name": "Ross from Friends",
        "popularity": 46,
        "type": "artist",
        "uri": "spotify:artist:1Ma3pJzPIrAyYPNRkp3SUF",
    }

    artist = Artist(
        artist_json,
        spotify_client=spotify_client,
    )

    assert isinstance(artist, Artist)
    assert artist._spotify_client == spotify_client
    assert artist.json == artist_json


def test_albums_property(spotify_artist: Artist) -> None:
    """Test the albums property of the Artist class."""

    assert not hasattr(spotify_artist, "_albums")
    assert isinstance(spotify_artist.albums, list)
    assert hasattr(spotify_artist, "_albums")

    assert len(spotify_artist.albums) == 39

    assert all(isinstance(album, Album) for album in spotify_artist.albums)
