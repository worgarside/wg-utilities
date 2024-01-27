"""Unit Tests for `wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.CurrentTrack`."""
from __future__ import annotations

from typing import Literal

import pytest

from tests.unit.devices.yamaha_yas_209.conftest import (
    yamaha_yas_209_get_media_info_responses,
    yamaha_yas_209_last_change_av_transport_events,
)
from wg_utilities.devices.yamaha_yas_209.yamaha_yas_209 import (
    CurrentTrack,
    GetMediaInfoResponse,
    LastChangeAVTransport,
)
from wg_utilities.functions.json import JSONObj


def test_instantiation() -> None:
    """Test that the class can be instantiated."""
    current_track = CurrentTrack(
        # pylint: disable=line-too-long
        album_art_uri="https://i.scdn.co/image/ab67616d0000b273dc30583ba717007b00cceb25",
        media_album_name="Abbey Road",
        media_artist="The Beatles",
        media_duration=259,
        media_title="Come Together",
    )

    assert isinstance(current_track, CurrentTrack)

    assert (
        current_track.album_art_uri
        == "https://i.scdn.co/image/ab67616d0000b273dc30583ba717007b00cceb25"
    )
    assert current_track.media_album_name == "Abbey Road"
    assert current_track.media_artist == "The Beatles"
    assert current_track.media_duration == 259
    assert current_track.media_title == "Come Together"


def test_json_property() -> None:
    """Test that `json` property returns the expected values."""

    current_track = CurrentTrack(
        # pylint: disable=line-too-long
        album_art_uri="https://i.scdn.co/image/ab67616d0000b273dc30583ba717007b00cceb25",
        media_album_name="Abbey Road",
        media_artist="The Beatles",
        media_duration=259,
        media_title="Come Together",
    )

    assert current_track.json == {
        # pylint: disable=line-too-long
        "album_art_uri": "https://i.scdn.co/image/ab67616d0000b273dc30583ba717007b00cceb25",
        "media_album_name": "Abbey Road",
        "media_artist": "The Beatles",
        "media_duration": 259,
        "media_title": "Come Together",
    }


@pytest.mark.parametrize(
    ("media_info_dict", "json_values"),
    yamaha_yas_209_get_media_info_responses(
        other_test_parameters={
            # pylint: disable=line-too-long
            "aura_avoure_spotify.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b2735889215746f6e9de26b85d60",
                "media_album_name": "U",
                "media_artist": "Avoure",
                "media_duration": (8 * 60) + 41,
                "media_title": "Aura",
            },
            "clair_de_lune_flight_facilities_alexa.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b273bb0ba14641d1c0b6b61a5234",
                "media_album_name": "idk",
                "media_artist": "Flight Facilities",
                "media_duration": (7 * 60) + 39,
                "media_title": "Clair De Lune",
            },
            "nothing_playing.json": {
                "album_art_uri": None,
                "media_album_name": None,
                "media_artist": None,
                "media_duration": 0,
                "media_title": None,
            },
        }
    ),
)
def test_from_get_media_info(
    media_info_dict: JSONObj,
    json_values: CurrentTrack.Info | None,
) -> None:
    """Test that `from_get_media_info` returns the expected values."""

    current_track = CurrentTrack.from_get_media_info(
        GetMediaInfoResponse.model_validate(media_info_dict)
    )

    assert current_track.json == json_values


@pytest.mark.parametrize(
    ("last_change_dict", "json_values"),
    yamaha_yas_209_last_change_av_transport_events(
        other_test_parameters={
            # pylint: disable=line-too-long
            "payload_20220913163159429624.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b2737bf7d3c5b31ebe3c7a885a9f",
                "media_album_name": "GANG",
                "media_artist": "Headie One",
                "media_duration": (3 * 60) + 10,
                "media_title": "SOLDIERS (feat. Sampha)",
            },
            "payload_20220915212001052341.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b2730eb07859a23c65cc9b54dab0",
                "media_album_name": "Clash of Joy",
                "media_artist": "Farsi",
                "media_duration": (5 * 60) + 27,
                "media_title": "Clash of Joy",
            },
            "payload_20220918002242476951.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b273a2196fd3af1eda81beb8826a",
                "media_album_name": "Harmonic Frequencies",
                "media_artist": "Elkka",
                "media_duration": (6 * 60) + 23,
                "media_title": "Music To Heal To",
            },
            "payload_20220918131627129225.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b273c1ddfb80737e8ce407427e2c",
                "media_album_name": "450",
                "media_artist": "Bad Boy Chiller Crew",
                "media_duration": (4 * 60) + 16,
                "media_title": "450 - 2020 Mix",
            },
            "payload_20221006153011540795.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b273ac29a65e7ffcfa6f9cb0d342",
                "media_album_name": "Interstellar (Original Motion Picture Soundtrack) [Expanded Edi",
                "media_artist": "Hans Zimmer",
                "media_duration": (2 * 60) + 6,
                "media_title": "Cornfield Chase",
            },
            "payload_20221009232228389305.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b27326f7709399913201ebe40eee",
                "media_album_name": "4x4=12",
                "media_artist": "deadmau5",
                "media_duration": (8 * 60) + 22,
                "media_title": "Raise Your Weapon",
            },
            "payload_20221010115238677548.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b2730929504a158ce5146e00c60e",
                "media_album_name": "Friend Zone (Ross from Friends Remix)",
                "media_artist": "Thundercat",
                "media_duration": (4 * 60) + 14,
                "media_title": "Friend Zone - Ross from Friends Remix",
            },
            "payload_20221010115653760816.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b2734506b8d7af0e3b7406f6b5df",
                "media_album_name": "All Under One Roof Raving",
                "media_artist": "Jamie xx",
                "media_duration": (5 * 60) + 59,
                "media_title": "All Under One Roof Raving",
            },
            "payload_20221013234843601604.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b273eb6412542b6e16fc44261405",
                "media_album_name": "Lonely Dulcimer / In Effect",
                "media_artist": "Dusky",
                "media_duration": (3 * 60) + 13,
                "media_title": "Lonely Dulcimer",
            },
            "payload_20221014001138224727.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b273bdc29122c006443e569ab389",
                "media_album_name": "KILL DEM",
                "media_artist": "Jamie xx",
                "media_duration": (3 * 60) + 43,
                "media_title": "KILL DEM",
            },
            "payload_20221017162615246918.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b2736e0759c0137223701e4f4c3b",
                "media_album_name": "low down",
                "media_artist": "venbee",
                "media_duration": (3 * 60) + 2,
                "media_title": "low down",
            },
            "payload_20221017165926278322.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b2731471f00a157b8d6e0e5696d4",
                "media_album_name": "Eyes Closed",
                "media_artist": "Netsky",
                "media_duration": (6 * 60) + 19,
                "media_title": "Eyes Closed",
            },
            "payload_20221019184409527432.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b27343e421b48df3b4a09ce3c722",
                "media_album_name": "Echoes",
                "media_artist": "Kove",
                "media_duration": (3 * 60) + 14,
                "media_title": "Echoes",
            },
            "payload_20221020151757703074.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b2733105b5ce5f8eb452bddb28fc",
                "media_album_name": "Ultraviolet (High Contrast Remix)",
                "media_artist": "Freya Ridings",
                "media_duration": (5 * 60) + 29,
                "media_title": "Ultraviolet - High Contrast Remix",
            },
            "payload_20221020164433292040.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b273a5903731fb2c73f61a99bd4a",
                "media_album_name": "Organ",
                "media_artist": "Dimension",
                "media_duration": (4 * 60) + 25,
                "media_title": "UK Border Patrol",
            },
            "payload_20221020170008212447.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b27394b507dbd18300a1cd94b7ff",
                "media_album_name": "Energy Fantasy (Remixes)",
                "media_artist": "Totally Enormous Extinct Dinosaurs",
                "media_duration": (5 * 60) + 56,
                "media_title": 'Energy Fantasy - Baltra "Vocal" Remix',
            },
            "payload_20221026180422994828.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b273ed18dfb77bb536bff76f7553",
                "media_album_name": "That's Another Story_Less Track Version for Digital Delivery",
                "media_artist": "toe",
                "media_duration": 5 * 60,
                "media_title": "グッドバイ_starRo Remix",
            },
            "payload_20221026182222744146.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b2739538f803ee21180700a21362",
                "media_album_name": "Safe",
                "media_artist": "Monkey Safari",
                "media_duration": (8 * 60) + 21,
                "media_title": "Safe",
            },
            "payload_20221031145534438150.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b273f56d363d03630bf3ee50b705",
                "media_album_name": "Clara (the night is dark)",
                "media_artist": "Fred again..",
                "media_duration": (4 * 60) + 38,
                "media_title": "Clara (the night is dark)",
            },
            "payload_20221031162556457495.json": {
                "album_art_uri": "https://i.scdn.co/image/ab67616d0000b2735fc235dac602275bcfb0c869",
                "media_album_name": "What They Say EP",
                "media_artist": "Maya Jane Coles",
                "media_duration": (6 * 60) + 40,
                "media_title": "What They Say",
            },
        }
    ),
)
def test_from_last_change_av_transport(
    last_change_dict: dict[Literal["Event"], object],
    json_values: CurrentTrack.Info | None,
) -> None:
    """Test that `from_last_change` returns the expected values (AVTransport)."""
    last_change = LastChangeAVTransport.parse(last_change_dict)

    # Replicates normal behaviour of `YamahaYas209.on_event_wrapper`
    if last_change.Event.InstanceID.CurrentTrackMetaData is None:
        return

    current_track = CurrentTrack.from_last_change(last_change)

    assert current_track.json == json_values


def test_str() -> None:
    """Test that `str` returns the expected values."""
    assert (
        str(
            CurrentTrack(
                # pylint: disable=line-too-long
                album_art_uri="https://i.scdn.co/image/ab67616d0000b273f56d363d03630bf3ee50b705",
                media_album_name="Clara (the night is dark)",
                media_artist="Fred again..",
                media_duration=278,
                media_title="Clara (the night is dark)",
            )
        )
        == "'Clara (the night is dark)' by Fred again.."
    )

    assert (
        str(
            CurrentTrack(
                album_art_uri=None,
                media_album_name=None,
                media_artist=None,
                media_duration=0,
                media_title=None,
            )
        )
        == "NULL"
    )


def test_repr() -> None:
    """Test that `repr` returns the expected values."""
    assert (
        repr(
            CurrentTrack(
                # pylint: disable=line-too-long
                album_art_uri="https://i.scdn.co/image/ab67616d0000b273f56d363d03630bf3ee50b705",
                media_album_name="Clara (the night is dark)",
                media_artist="Fred again..",
                media_duration=278,
                media_title="Clara (the night is dark)",
            )
        )
        == "CurrentTrack(\"'Clara (the night is dark)' by Fred again..\")"
    )

    assert (
        repr(
            CurrentTrack(
                album_art_uri=None,
                media_album_name=None,
                media_artist=None,
                media_duration=0,
                media_title=None,
            )
        )
        == "CurrentTrack('NULL')"
    )


def test_eq() -> None:
    """Test that `__eq__` returns the expected values."""

    clara = CurrentTrack(
        # pylint: disable=line-too-long
        album_art_uri="https://i.scdn.co/image/ab67616d0000b273f56d363d03630bf3ee50b705",
        media_album_name="Clara (the night is dark)",
        media_artist="Fred again..",
        media_duration=278,
        media_title="Clara (the night is dark)",
    )

    null_track = CurrentTrack(
        album_art_uri=None,
        media_album_name=None,
        media_artist=None,
        media_duration=0,
        media_title=None,
    )

    assert clara == CurrentTrack(
        # pylint: disable=line-too-long
        album_art_uri="https://i.scdn.co/image/ab67616d0000b273f56d363d03630bf3ee50b705",
        media_album_name="Clara (the night is dark)",
        media_artist="Fred again..",
        media_duration=278,
        media_title="Clara (the night is dark)",
    )

    assert (
        null_track
        == CurrentTrack(
            album_art_uri=None,
            media_album_name=None,
            media_artist=None,
            media_duration=0,
            media_title=None,
        )
        == CurrentTrack.null_track()
    )

    assert null_track != clara

    assert clara != "wrong type"
    # pylint: disable=unnecessary-dunder-call
    assert clara.__eq__("wrong type") is NotImplemented
