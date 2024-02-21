"""Fixtures and functions for the Yamaha YAS-209 tests."""

from __future__ import annotations

from http import HTTPStatus
from json import dumps, loads
from os import listdir
from pathlib import Path
from textwrap import dedent
from time import sleep
from typing import TYPE_CHECKING, cast
from xml.etree import ElementTree

import pytest
from aioresponses import aioresponses
from async_upnp_client.client import UpnpRequester, UpnpService, UpnpStateVariable
from async_upnp_client.const import (
    ServiceInfo,
    StateVariableInfo,
    StateVariableTypeInfo,
)
from voluptuous import All, Schema

from tests.conftest import FLAT_FILES_DIR, YieldFixture, read_json_file
from wg_utilities.devices.yamaha_yas_209.yamaha_yas_209 import (
    CurrentTrack,
    YamahaYas209,
)
from wg_utilities.functions.json import JSONObj

if TYPE_CHECKING:
    from wg_utilities.clients._spotify_types import SpotifyEntityJson

YAS_209_IP = "192.168.1.1"
YAS_209_HOST = f"http://{YAS_209_IP}:49152"


def fix_colon_keys(json_obj: JSONObj | SpotifyEntityJson) -> JSONObj:
    """Fix colons replaced with underscores in keys.

    Some keys have colons changed for underscores when they're parsed into Pydantic
    models, this undoes that.

    Args:
        json_obj (dict): the JSON object to fix

    Returns:
        dict: the fixed JSON object
    """

    json_str = dumps(json_obj)

    for key in (
        "xmlns_dc",
        "xmlns_upnp",
        "xmlns_song",
        "upnp_class",
        "song_subid",
        "song_description",
        "song_skiplimit",
        "song_id",
        "song_like",
        "song_singerid",
        "song_albumid",
        "dc_title",
        "dc_creator",
        "upnp_artist",
        "upnp_album",
        "upnp_albumArtURI",
        "dc_creator",
        "song_controls",
    ):
        json_str = json_str.replace(key, key.replace("_", ":"))

    return cast(JSONObj, loads(json_str))


def yamaha_yas_209_get_media_info_responses(
    other_test_parameters: dict[str, CurrentTrack.Info],
) -> YieldFixture[tuple[JSONObj | SpotifyEntityJson, CurrentTrack.Info | None]]:
    """Yield values for testing against GetMediaInfo responses.

    Yields:
        list: a list of `getMediaInfo` responses
    """
    for file in listdir(FLAT_FILES_DIR / "json" / "yamaha_yas_209" / "get_media_info"):
        json = read_json_file(f"yamaha_yas_209/get_media_info/{file}")
        values: CurrentTrack.Info | None = other_test_parameters.get(file)

        yield json, values


def yamaha_yas_209_last_change_av_transport_events(
    other_test_parameters: dict[str, CurrentTrack.Info] | None = None,
) -> YieldFixture[tuple[JSONObj, CurrentTrack.Info | None] | JSONObj]:
    """Yield values for testing against AVTransport payloads.

    Args:
        other_test_parameters (dict[str, CurrentTrack.Info], optional): a dictionary
            of values which are returned for given files. Defaults to None.

    Yields:
        list: a list of `lastChange` events
    """
    other_test_parameters = other_test_parameters or {}
    for file in sorted(
        listdir(
            FLAT_FILES_DIR
            / "json"
            / "yamaha_yas_209"
            / "event_payloads"
            / "av_transport",
        ),
    ):
        json_obj = cast(
            JSONObj,
            fix_colon_keys(
                read_json_file(f"yamaha_yas_209/event_payloads/av_transport/{file}"),
            )["last_change"],
        )

        if values := other_test_parameters.get(
            file,
        ):
            yield json_obj, values
        elif other_test_parameters:
            # If we're sending 2 arguments for any, we need to send 2 arguments for all
            yield json_obj, None
        else:
            # Removing the parentheses here gives me typing errors, and removing
            # the comma makes the `yield` statement fail for some reason
            yield (json_obj,)  # type: ignore[misc]


def yamaha_yas_209_last_change_rendering_control_events() -> YieldFixture[JSONObj]:
    """Yield values for testing against RenderingControl payloads.

    Yields:
        dict: a `lastChange` event
    """
    for file in sorted(
        listdir(
            FLAT_FILES_DIR
            / "json"
            / "yamaha_yas_209"
            / "event_payloads"
            / "rendering_control",
        ),
    ):
        json_obj = cast(
            JSONObj,
            fix_colon_keys(
                read_json_file(f"yamaha_yas_209/event_payloads/rendering_control/{file}"),
            )["last_change"],
        )

        yield json_obj


@pytest.fixture(name="current_track_null")
def current_track_null_() -> CurrentTrack:
    """Return a CurrentTrack object with null values."""
    return CurrentTrack(
        album_art_uri=None,
        media_album_name=None,
        media_artist=None,
        media_duration=0.0,
        media_title=None,
    )


@pytest.fixture(name="mock_aiohttp")
def mock_aiohttp_() -> YieldFixture[aioresponses]:
    """Fixture for mocking async HTTP requests."""

    with aioresponses() as mock_aiohttp:
        for path_object in (
            get_dir := FLAT_FILES_DIR
            / "xml"
            / "yamaha_yas_209"
            / "aiohttp_responses"
            / "get"
        ).rglob("*"):
            if path_object.is_file():
                mock_aiohttp.get(
                    YAS_209_HOST + "/" + str(path_object.relative_to(get_dir)),
                    status=HTTPStatus.OK,
                    reason=HTTPStatus.OK.phrase,
                    body=path_object.read_bytes(),
                    repeat=True,
                )

        yield mock_aiohttp


@pytest.fixture(name="upnp_service_av_transport")
def upnp_service_av_transport_() -> UpnpService:
    """Fixture for creating an UpnpService instance."""
    return UpnpService(
        UpnpRequester(),
        service_info=ServiceInfo(
            control_url="/upnp/control/rendertransport1",
            event_sub_url="/upnp/event/rendertransport1",
            scpd_url="/upnp/scpd/rendertransport1",
            service_id="urn:upnp-org:serviceId:AVTransport",
            service_type="urn:schemas-upnp-org:service:AVTransport:1",
            xml=ElementTree.fromstring(
                dedent(
                    """
                        <ns0:service xmlns:ns0="urn:schemas-upnp-org:device-1-0">
                            <ns0:serviceType>urn:schemas-upnp-org:service:AVTransport:1
                            </ns0:serviceType>
                            <ns0:serviceId>urn:upnp-org:serviceId:AVTransport</ns0:serviceId>
                            <ns0:SCPDURL>/upnp/rendertransportSCPD.xml</ns0:SCPDURL>
                            <ns0:controlURL>/upnp/control/rendertransport1</ns0:controlURL>
                            <ns0:eventSubURL>/upnp/event/rendertransport1</ns0:eventSubURL>
                        </ns0:service>
                    """,
                ).strip(),
            ),
        ),
        state_variables=[],
        actions=[],
    )


@pytest.fixture(name="upnp_service_rendering_control")
def upnp_service_rendering_control_() -> UpnpService:
    """Fixture for creating an UpnpService instance."""
    return UpnpService(
        UpnpRequester(),
        service_info=ServiceInfo(
            control_url="/upnp/control/rendercontrol1",
            event_sub_url="/upnp/event/rendercontrol1",
            scpd_url="/upnp/rendercontrolSCPD.xml",
            service_id="urn:upnp-org:serviceId:RenderingControl",
            service_type="urn:schemas-upnp-org:service:RenderingControl:1",
            xml=ElementTree.fromstring(
                dedent(
                    """
            <ns0:service xmlns:ns0="urn:schemas-upnp-org:device-1-0">
                <ns0:serviceType>urn:schemas-upnp-org:service:RenderingControl:1
                </ns0:serviceType>
                <ns0:serviceId>urn:upnp-org:serviceId:RenderingControl</ns0:serviceId>
                <ns0:SCPDURL>/upnp/rendercontrolSCPD.xml</ns0:SCPDURL>
                <ns0:controlURL>/upnp/control/rendercontrol1</ns0:controlURL>
                <ns0:eventSubURL>/upnp/event/rendercontrol1</ns0:eventSubURL>
            </ns0:service>
                    """,
                ).strip(),
            ),
        ),
        state_variables=[],
        actions=[],
    )


@pytest.fixture(name="upnp_state_variable")
def upnp_state_variable_(request: pytest.FixtureRequest) -> UpnpStateVariable[str]:
    """Fixture for creating an UpnpStateVariable instance."""
    state_var = UpnpStateVariable[str](
        StateVariableInfo(
            name="LastChange",
            send_events=True,
            type_info=StateVariableTypeInfo(
                data_type="string",
                data_type_mapping={"type": str, "in": str, "out": str},
                default_value=None,
                allowed_value_range={},
                allowed_values=None,
                xml=(
                    last_change_xml := ElementTree.fromstring(
                        dedent(
                            """
                                <ns0:stateVariable xmlns:ns0="urn:schemas-upnp-org:service-1-0" sendEvents="yes">
                                    <ns0:name>LastChange</ns0:name>
                                    <ns0:dataType>string</ns0:dataType>
                                </ns0:stateVariable>
                            """,
                        ).strip(),
                    )
                ),
            ),
            xml=last_change_xml,
        ),
        schema=Schema(
            schema=All(),
        ),
    )

    if name_marker := request.node.get_closest_marker("upnp_value_path"):
        state_var.upnp_value = Path(name_marker.args[0]).read_text(encoding="utf-8")

    return state_var


@pytest.fixture(name="yamaha_yas_209")
def yamaha_yas_209_() -> YieldFixture[YamahaYas209]:
    """Fixture for creating a YamahaYAS209 instance."""

    yas_209 = YamahaYas209(
        YAS_209_IP,
        start_listener=False,
        logging=True,
        listen_ip="192.168.1.2",
        listen_port=12345,
    )

    yield yas_209

    yas_209._logging = False

    if yas_209.is_listening:  # pragma: no cover
        yas_209.stop_listening()

        while yas_209.is_listening:
            sleep(0.1)
