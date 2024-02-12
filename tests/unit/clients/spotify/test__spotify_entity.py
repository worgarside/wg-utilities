"""Unit Tests for `wg_utilities.clients.spotify.SpotifyEntity`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wg_utilities.clients._spotify_types import SpotifyBaseEntityJson
from wg_utilities.clients.spotify import SpotifyClient, SpotifyEntity


def test_summary_json_is_immutable(
    spotify_entity: SpotifyEntity[SpotifyBaseEntityJson],
) -> None:
    """Test that the summary_json property is immutable."""
    with pytest.raises(ValidationError) as exc_info:
        spotify_entity.summary_json = {}  # type: ignore[typeddict-item]

    assert "Field is frozen" in str(exc_info.value)


def test_summary_json_is_correct(
    spotify_entity: SpotifyEntity[SpotifyBaseEntityJson],
) -> None:
    """Test that the summary_json property is correct."""
    assert spotify_entity.summary_json == {
        "id": "0gxyHStUsqpMadRV0Di1Qt",
        "uri": "spotify:artist:0gxyHStUsqpMadRV0Di1Qt",
        "href": f"{SpotifyClient.BASE_URL}/artists/0gxyHStUsqpMadRV0Di1Qt",
        "external_urls": {
            "spotify": "https://open.spotify.com/artist/0gxyHStUsqpMadRV0Di1Qt",
        },
    }

    # There's nothing exclude-able for a SpotifyEntity's summary JSON
    assert spotify_entity.model_dump() == spotify_entity.summary_json


def test_from_json_response_instantiation(spotify_client: SpotifyClient) -> None:
    """Test instantiation of the SpotifyEntity class."""
    spotify_entity = SpotifyEntity[SpotifyBaseEntityJson].from_json_response(
        {
            "href": "https://www.example.com",
            "id": "unique identity value",
            "uri": "entity:unique identity value",
            "external_urls": {
                "spotify": "https://www.example.com",
            },
        },
        spotify_client=spotify_client,
        metadata={"key": "value"},
    )

    assert isinstance(spotify_entity, SpotifyEntity)

    assert spotify_entity.model_dump() == {
        "external_urls": {
            "spotify": "https://www.example.com",
        },
        "href": "https://www.example.com",
        "id": "unique identity value",
        "metadata": {"key": "value"},
        "uri": "entity:unique identity value",
    }
    assert spotify_entity.spotify_client == spotify_client
    assert spotify_entity.metadata == {"key": "value"}
    assert spotify_entity.id == "unique identity value"
    assert spotify_entity.name == ""
    assert spotify_entity.description == ""
    assert spotify_entity.url == "https://www.example.com"
    assert spotify_entity.uri == "entity:unique identity value"
    assert spotify_entity.href == "https://www.example.com"
    assert spotify_entity.external_urls == {"spotify": "https://www.example.com"}


def test_url_property(spotify_entity: SpotifyEntity[SpotifyBaseEntityJson]) -> None:
    """Test the url property of the SpotifyEntity class."""

    assert (
        spotify_entity.url == "https://open.spotify.com/artist/0gxyHStUsqpMadRV0Di1Qt"
    )

    del spotify_entity.external_urls["spotify"]
    assert (
        spotify_entity.url
        == "https://open.spotify.com/spotifyentity/0gxyHStUsqpMadRV0Di1Qt"
    )


def test_eq(
    spotify_entity: SpotifyEntity[SpotifyBaseEntityJson], spotify_client: SpotifyClient
) -> None:
    """Test the __eq__ method of the SpotifyEntity class."""

    assert spotify_entity == spotify_entity  # pylint: disable=comparison-with-itself
    assert spotify_entity == SpotifyEntity[SpotifyBaseEntityJson].model_validate(
        {
            **spotify_entity.model_dump(exclude_none=True),
            "spotify_client": spotify_client,
        }
    )

    assert spotify_entity != SpotifyEntity[SpotifyBaseEntityJson](
        href=f"{SpotifyClient.BASE_URL}/artists/1Ma3pJzPIrAyYPNRkp3SUF",
        id="1Ma3pJzPIrAyYPNRkp3SUF",
        uri="spotify:artist:1Ma3pJzPIrAyYPNRkp3SUF",
        external_urls={
            "spotify": "https://open.spotify.com/artist/1Ma3pJzPIrAyYPNRkp3SUF"
        },
        spotify_client=spotify_client,
        metadata={},
    )
    assert spotify_entity != "not a SpotifyEntity[SpotifyBaseEntityJson]"


def test_gt(
    spotify_entity: SpotifyEntity[SpotifyBaseEntityJson],
) -> None:
    """Test the __gt__ method of the SpotifyEntity class."""

    new_entity = SpotifyEntity[SpotifyBaseEntityJson](
        id="12345",
        href="",
        uri="",
        external_urls={"spotify": ""},
        spotify_client=spotify_entity.spotify_client,
    )

    assert new_entity > spotify_entity
    assert not spotify_entity > new_entity

    with pytest.raises(TypeError) as exc_info:
        assert spotify_entity > "not a SpotifyEntity"

    assert (
        str(exc_info.value)
        == "'>' not supported between instances of 'SpotifyEntity' and 'str'"
    )


def test_hash(spotify_entity: SpotifyEntity[SpotifyBaseEntityJson]) -> None:
    """Test the __hash__ method of the SpotifyEntity class."""

    assert hash(spotify_entity) == hash(
        'SpotifyEntity(id="0gxyHStUsqpMadRV0Di1Qt", name="")'
    )


def test_lt(spotify_entity: SpotifyEntity[SpotifyBaseEntityJson]) -> None:
    """Test the __lt__ method of the SpotifyEntity class."""

    new_entity = SpotifyEntity[SpotifyBaseEntityJson](
        id="12345",
        href="",
        uri="",
        external_urls={"spotify": ""},
        spotify_client=spotify_entity.spotify_client,
    )

    assert spotify_entity < new_entity
    assert not new_entity < spotify_entity

    with pytest.raises(TypeError) as exc_info:
        assert spotify_entity < "not a SpotifyEntity"  # type: ignore[operator]

    assert (
        str(exc_info.value)
        == "'<' not supported between instances of 'SpotifyEntity' and 'str'"
    )


def test_repr(spotify_entity: SpotifyEntity[SpotifyBaseEntityJson]) -> None:
    """Test the __repr__ method of the SpotifyEntity class."""

    assert repr(spotify_entity) == 'SpotifyEntity(id="0gxyHStUsqpMadRV0Di1Qt", name="")'


def test_str(spotify_entity: SpotifyEntity[SpotifyBaseEntityJson]) -> None:
    """Test the __str__ method of the SpotifyEntity class."""

    assert str(spotify_entity) == "SpotifyEntity (0gxyHStUsqpMadRV0Di1Qt)"
