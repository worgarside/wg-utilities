# pylint: disable=protected-access
"""Unit Tests for `wg_utilities.clients.spotify.SpotifyEntity`."""
from __future__ import annotations

from textwrap import dedent

from pytest import raises

from wg_utilities.clients.spotify import SpotifyClient, SpotifyEntity


def test_instantiation(spotify_client: SpotifyClient) -> None:
    """Test instantiation of the SpotifyEntity class."""
    spotify_entity = SpotifyEntity(
        {
            "description": "tbd",
            "href": "tbd",
            "id": "tbd",
            "name": "tbd",
            "uri": "tbd",
            "external_urls": {"spotify": "tbd"},
        },
        spotify_client=spotify_client,
        metadata={"key": "value"},
    )

    assert isinstance(spotify_entity, SpotifyEntity)

    assert spotify_entity.json == {
        "description": "tbd",
        "href": "tbd",
        "id": "tbd",
        "name": "tbd",
        "uri": "tbd",
        "external_urls": {"spotify": "tbd"},
    }
    assert spotify_entity._spotify_client == spotify_client
    assert spotify_entity.metadata == {"key": "value"}


def test_pretty_json_property(spotify_entity: SpotifyEntity) -> None:
    """Test the pretty_json property of the SpotifyEntity class."""

    assert (
        spotify_entity.pretty_json
        == dedent(
            """
    {
      "description": "The official number one song of all time.",
      "href": "https://api.spotify.com/v1/artists/0gxyHStUsqpMadRV0Di1Qt",
      "id": "0gxyHStUsqpMadRV0Di1Qt",
      "name": "Rick Astley",
      "uri": "spotify:artist:0gxyHStUsqpMadRV0Di1Qt",
      "external_urls": {
        "spotify": "https://open.spotify.com/artist/0gxyHStUsqpMadRV0Di1Qt"
      }
    }
"""
        ).strip()
    )


def test_description_property(spotify_entity: SpotifyEntity) -> None:
    """Test the description property of the SpotifyEntity class."""

    assert spotify_entity.description == "The official number one song of all time."


def test_endpoint_property(spotify_entity: SpotifyEntity) -> None:
    """Test the endpoint property of the SpotifyEntity class."""

    assert (
        spotify_entity.endpoint
        == "https://api.spotify.com/v1/artists/0gxyHStUsqpMadRV0Di1Qt"
    )


def test_id_property(spotify_entity: SpotifyEntity) -> None:
    """Test the id property of the SpotifyEntity class."""

    assert spotify_entity.id == "0gxyHStUsqpMadRV0Di1Qt"


def test_name_property(spotify_entity: SpotifyEntity) -> None:
    """Test the name property of the SpotifyEntity class."""

    assert spotify_entity.name == "Rick Astley"


def test_uri_property(spotify_entity: SpotifyEntity) -> None:
    """Test the uri property of the SpotifyEntity class."""

    assert spotify_entity.uri == "spotify:artist:0gxyHStUsqpMadRV0Di1Qt"

    del spotify_entity.json["uri"]  # type: ignore[misc]
    assert spotify_entity.uri == "spotify:spotifyentity:0gxyHStUsqpMadRV0Di1Qt"


def test_url_property(spotify_entity: SpotifyEntity) -> None:
    """Test the url property of the SpotifyEntity class."""

    assert (
        spotify_entity.url == "https://open.spotify.com/artist/0gxyHStUsqpMadRV0Di1Qt"
    )

    del spotify_entity.json["external_urls"]  # type: ignore[misc]
    assert (
        spotify_entity.url
        == "https://open.spotify.com/spotifyentity/0gxyHStUsqpMadRV0Di1Qt"
    )


def test_eq(spotify_entity: SpotifyEntity) -> None:
    """Test the __eq__ method of the SpotifyEntity class."""

    assert spotify_entity == spotify_entity  # pylint: disable=comparison-with-itself
    assert spotify_entity == SpotifyEntity(
        spotify_entity.json, spotify_client=spotify_entity._spotify_client
    )
    assert spotify_entity != SpotifyEntity(
        {"id": "12345"},  # type: ignore[typeddict-item]
        spotify_client=spotify_entity._spotify_client,
    )
    assert spotify_entity != "not a SpotifyEntity"


def test_gt(spotify_entity: SpotifyEntity) -> None:
    """Test the __gt__ method of the SpotifyEntity class."""

    new_entity = SpotifyEntity(
        {
            "id": "12345",
            "description": "",
            "href": "",
            "name": "",
            "uri": "",
            "external_urls": {"spotify": ""},
        },
        spotify_client=spotify_entity._spotify_client,
    )

    assert spotify_entity > new_entity
    assert not spotify_entity > new_entity  # pylint: disable=unneeded-not

    with raises(TypeError) as exc_info:
        assert spotify_entity > "not a SpotifyEntity"

    assert (
        str(exc_info.value)
        == "'>' not supported between instances of 'SpotifyEntity' and 'str'"
    )


def test_hash(spotify_entity: SpotifyEntity) -> None:
    """Test the __hash__ method of the SpotifyEntity class."""

    assert hash(spotify_entity) == hash(
        'SpotifyEntity(id="0gxyHStUsqpMadRV0Di1Qt", name="Rick Astley")'
    )


def test_lt(spotify_entity: SpotifyEntity) -> None:
    """Test the __lt__ method of the SpotifyEntity class."""

    new_entity = SpotifyEntity(
        {
            "id": "12345",
            "description": "",
            "href": "",
            "name": "",
            "uri": "",
            "external_urls": {"spotify": ""},
        },
        spotify_client=spotify_entity._spotify_client,
    )

    assert new_entity < spotify_entity
    assert not spotify_entity < new_entity  # pylint: disable=unneeded-not

    with raises(TypeError) as exc_info:
        assert spotify_entity < "not a SpotifyEntity"  # type: ignore[operator]

    assert (
        str(exc_info.value)
        == "'<' not supported between instances of 'SpotifyEntity' and 'str'"
    )


def test_repr(spotify_entity: SpotifyEntity) -> None:
    """Test the __repr__ method of the SpotifyEntity class."""

    assert (
        repr(spotify_entity)
        == 'SpotifyEntity(id="0gxyHStUsqpMadRV0Di1Qt", name="Rick Astley")'
    )


def test_str(spotify_entity: SpotifyEntity) -> None:
    """Test the __str__ method of the SpotifyEntity class."""

    assert str(spotify_entity) == "Rick Astley (0gxyHStUsqpMadRV0Di1Qt)"
