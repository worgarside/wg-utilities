# pylint: disable=protected-access,too-many-lines
"""Unit Tests for `wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.YamahaYas209`."""
from __future__ import annotations

from asyncio import new_event_loop
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from http import HTTPStatus
from logging import DEBUG, ERROR, INFO, WARNING
from textwrap import dedent
from threading import Thread
from time import sleep
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

import pytest
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from async_upnp_client.aiohttp import AiohttpNotifyServer
from async_upnp_client.client import (
    UpnpDevice,
    UpnpRequester,
    UpnpService,
    UpnpStateVariable,
)
from async_upnp_client.const import (
    AddressTupleVXType,
    StateVariableInfo,
    StateVariableTypeInfo,
)
from async_upnp_client.exceptions import UpnpResponseError
from async_upnp_client.utils import get_local_ip
from freezegun import freeze_time
from xmltodict import parse as parse_xml
from yarl import URL

from tests.conftest import FLAT_FILES_DIR, TEST_EXCEPTION, TestError
from wg_utilities.devices.yamaha_yas_209 import YamahaYas209
from wg_utilities.devices.yamaha_yas_209.yamaha_yas_209 import (
    CurrentTrack,
    LastChangeRenderingControl,
    Yas209Service,
    Yas209State,
    _needs_device,
)

ON_TOP = CurrentTrack(
    album_art_uri="https://i.scdn.co/image/ab67616d0000b2733198dc8920850509e8a07d8c",
    media_album_name="Flume",
    media_artist="Flume",
    media_duration=(3 * 60) + 51,
    media_title="On Top",
)


FRESH_SUBSCRIPTION_CALL = RequestCall(
    args=(),
    kwargs={
        "headers": {
            "NT": "upnp:event",
            "TIMEOUT": "Second-1800",
            "HOST": "192.168.1.1:49152",
            "CALLBACK": "<http://192.168.1.2:12345/notify>",
        },
        "data": None,
        "allow_redirects": True,
        "timeout": 5,
    },
)
RESUBSCRIPTION_CALL_AV = RequestCall(
    args=(),
    kwargs={
        "headers": {
            "HOST": "192.168.1.1:49152",
            "SID": "uuid:e80e4092-5dd0-11ed-8ec1-b1deb019e391",
            "TIMEOUT": "Second-1800.0",
        },
        "data": None,
        "allow_redirects": True,
        "timeout": 5,
    },
)

RESUBSCRIPTION_CALL_RC = RequestCall(
    args=(),
    kwargs={
        "headers": {
            "HOST": "192.168.1.1:49152",
            "SID": "uuid:e80e4092-5dd0-11ed-8ec1-b1deb019e392",
            "TIMEOUT": "Second-1800.0",
        },
        "data": None,
        "allow_redirects": True,
        "timeout": 5,
    },
)


def add_av_subscription_call(
    mock_aiohttp: aioresponses,
    yamaha_yas_209: YamahaYas209,
    *,
    repeat: bool = False,
    exception: Exception | None = None,
) -> None:
    """Add a mocked subscription call response for the AVT service.

    Args:
        mock_aiohttp (aioresponses): The `aioresponses` instance to mock the response
            with.
        yamaha_yas_209 (YamahaYas209): The instance of the class that was tested.
        repeat (bool, optional): Whether to repeat the response. Defaults to False.
        exception (Exception, optional): An exception to raise. Defaults to None.
    """
    mock_aiohttp.add(
        f"http://{yamaha_yas_209.ip}:49152/upnp/event/rendertransport1",
        headers={
            "Date": "Sun, 06 Nov 2022 12:38:25 GMT",
            "Server": "Linux/4.4.22",
            "Content-Length": "0",
            "SID": "uuid:e80e4092-5dd0-11ed-8ec1-b1deb019e391",
            "TIMEOUT": "Second-1800",
        },
        status=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        method="SUBSCRIBE",
        repeat=repeat,
        exception=exception,
    )


def add_rc_subscription_call(
    mock_aiohttp: aioresponses,
    yamaha_yas_209: YamahaYas209,
    *,
    repeat: bool = False,
    exception: Exception | None = None,
) -> None:
    """Add a mocked subscription call response for the RC service.

    Args:
        mock_aiohttp (aioresponses): The `aioresponses` instance to mock the response
            with.
        yamaha_yas_209 (YamahaYas209): The instance of the class that was tested.
        repeat (bool, optional): Whether to repeat the response. Defaults to False.
        exception (Exception, optional): An exception to raise. Defaults to None.
    """
    mock_aiohttp.add(
        f"http://{yamaha_yas_209.ip}:49152/upnp/event/rendercontrol1",
        headers={
            "Date": "Sun, 06 Nov 2022 12:45:34 GMT",
            "Server": "Linux/4.4.22",
            "Content-Length": "0",
            "SID": "uuid:e80e4092-5dd0-11ed-8ec1-b1deb019e392",
            "TIMEOUT": "Second-1800",
        },
        status=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        method="SUBSCRIBE",
        repeat=repeat,
        exception=exception,
    )


def assert_only_post_request_is(
    url: str,
    requests: dict[tuple[str, URL], list[RequestCall]],
    yamaha_yas_209: YamahaYas209,
) -> None:
    """Run assertion for multiple tests.

    Args:
        url (str): The URL that the request should be made to.
        requests (dict[tuple[str, URL], list[RequestCall]]): The requests that were
            made.
        yamaha_yas_209 (YamahaYas209): The instance of the class that was tested.
    """

    assert requests.pop(("POST", URL(url))) == [
        RequestCall(
            args=(),
            kwargs={
                "headers": {
                    # pylint: disable=line-too-long
                    "SOAPAction": '"urn:schemas-upnp-org:service:AVTransport:1#GetMediaInfo"',
                    "Host": f"{yamaha_yas_209.ip}:49152",
                    "Content-Type": 'text/xml; charset="utf-8"',
                },
                # pylint: disable=line-too-long
                "data": """<?xml version="1.0"?><s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:GetMediaInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:GetMediaInfo></s:Body></s:Envelope>""",  # noqa: E501
                "allow_redirects": True,
                "timeout": 5,
            },
        )
    ]
    assert all(key[0] == "GET" for key in requests), str(requests)


def mock_get_info_response(
    file_name: str, mock_aiohttp: aioresponses, yamaha_yas_209: YamahaYas209
) -> str:
    """Mock the response for `get_info`.

    Args:
        file_name (str): The name of the file to read the response from.
        mock_aiohttp (aioresponses): The `aioresponses` instance to mock the response
            with.
        yamaha_yas_209 (YamahaYas209): The instance of the class that was tested.

    Returns:
        str: The URL that the response was mocked for.
    """

    mock_aiohttp.post(
        (url := f"http://{yamaha_yas_209.ip}:49152/upnp/control/rendertransport1"),
        status=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        body=(
            FLAT_FILES_DIR / "xml" / "yamaha_yas_209" / "get_media_info" / file_name
        ).read_text(),
    )

    return url


def test_instantiation() -> None:
    """Test that the class can be instantiated."""
    yas_209 = YamahaYas209("192.168.1.1")

    assert isinstance(yas_209, YamahaYas209)

    assert yas_209.ip == "192.168.1.1"
    assert yas_209.on_event is None
    assert yas_209.description_url == "http://192.168.1.1:49152/description.xml"
    assert yas_209.on_volume_update is None
    assert yas_209.on_track_update is None
    assert yas_209.on_state_update is None


def test_providing_listen_ip_only_raises_exception() -> None:
    """Test that setting only the `listen_ip` and not the port raises an exception."""

    with pytest.raises(ValueError) as exc_info:
        YamahaYas209("192.168.1.1", listen_ip="192.168.1.2")

    assert (
        str(exc_info.value)
        == "Argument `listen_port` cannot be None when `listen_ip` is not None:"
        " '192.168.1.2'"
    )


def test_listen_exits_early_if_already_listening(
    yamaha_yas_209: YamahaYas209, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that `listen` exits early if already `self._listening` is True."""
    yamaha_yas_209._listening = True

    yamaha_yas_209.listen()

    assert len(caplog.records) == 2
    assert caplog.records[0].levelno == INFO
    assert caplog.records[0].message == "Starting listener"
    assert caplog.records[1].levelno == DEBUG
    assert caplog.records[1].message == "Already listening to '', returning immediately"


def test_auto_listening_works() -> None:
    """Test that the `listen` method is called when `start_listener` is True."""

    with patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.YamahaYas209.listen"
    ) as mock_listen:
        YamahaYas209("192.168.1.1", start_listener=False)
        mock_listen.assert_not_called()

        YamahaYas209("192.168.1.1", start_listener=True)
        mock_listen.assert_called_once()


@patch("wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.sleep")
def test_listen_starts_listening(
    mock_sleep: MagicMock,
    yamaha_yas_209: YamahaYas209,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that `listen` starts listening if `self._listening` is False."""

    async_call_count = 0

    async def _mock_async_function(self: YamahaYas209) -> None:
        """Mock async function."""
        nonlocal async_call_count

        yamaha_yas_209._listening = True
        yamaha_yas_209._active_service_ids = [
            v.service_id for v in Yas209Service.__members__.values()
        ]

        async_call_count += 1

        assert self == yamaha_yas_209

    with patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.YamahaYas209._subscribe",
        _mock_async_function,
    ):
        # Sometimes logs from the teardown of the previous test get caught here... -.-
        caplog.clear()
        yamaha_yas_209.listen()

    assert {c.args for c in mock_sleep.call_args_list} in (set(), {(0.01,)})
    assert async_call_count == 1

    assert len(caplog.records) == 2
    assert caplog.records[0].levelno == INFO
    assert caplog.records[0].message == "Starting listener"
    assert caplog.records[1].levelno == DEBUG
    assert (
        caplog.records[1].message == "Listen action complete, now subscribed to "
        "'urn:upnp-org:serviceId:AVTransport', "
        "'urn:upnp-org:serviceId:ConnectionManager', "
        "'urn:wiimu-com:serviceId:PlayQueue', "
        "'urn:tencent-com:serviceId:QPlay', "
        "'urn:upnp-org:serviceId:RenderingControl'"
    )


def test_listen_reraises_exception_from_subscribe_worker(
    yamaha_yas_209: YamahaYas209,
) -> None:
    """Test that `listen` starts listening if `self._listening` is False."""

    call_count = 0

    async def _mock_async_function(self: YamahaYas209) -> None:
        """Mock async function."""
        nonlocal call_count

        yamaha_yas_209._listening = True
        yamaha_yas_209._active_service_ids = [
            v.service_id for v in Yas209Service.__members__.values()
        ]

        call_count += 1

        assert self == yamaha_yas_209

        raise TEST_EXCEPTION

    with patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.YamahaYas209._subscribe",
        _mock_async_function,
    ), pytest.raises(TestError) as exc_info:
        yamaha_yas_209.listen()

    assert call_count == 1

    assert exc_info.value == TEST_EXCEPTION


@patch("wg_utilities.devices.yamaha_yas_209.YamahaYas209._parse_xml_dict")
def test_on_event_wrapper_parses_xml_dicts(
    mock_parse_xml_dict: MagicMock,
    yamaha_yas_209: YamahaYas209,
    upnp_service_av_transport: UpnpService,
    upnp_state_variable: UpnpStateVariable[str],
) -> None:
    """Test that the `on_event` wrapper works."""

    called = False

    def _mock_parse_xml_dict_side_effect(xml_payloads: dict[str, object]) -> None:
        nonlocal called
        assert xml_payloads == {upnp_state_variable.name: upnp_state_variable.value}
        # Setting this to None will throw an exception on the next step in the
        # `on_event_wrapper` method, exiting the test early.
        xml_payloads["LastChange"] = None
        called = True

    mock_parse_xml_dict.side_effect = _mock_parse_xml_dict_side_effect

    with pytest.raises(TypeError) as exc_info:
        yamaha_yas_209.on_event_wrapper(
            upnp_service_av_transport, [upnp_state_variable]
        )

    assert called
    assert str(exc_info.value) == "Expected a dict, got <class 'NoneType'>"


@pytest.mark.upnp_value_path(
    # You & I by JANEVA
    FLAT_FILES_DIR
    / "xml"
    / "yamaha_yas_209"
    / "event_payloads"
    / "av_transport"
    / "payload_20230408232348755378.xml"
)
def test_xml_payloads_with_ampersands_can_be_parsed(
    yamaha_yas_209: YamahaYas209,
    upnp_service_av_transport: UpnpService,
    upnp_state_variable: UpnpStateVariable[str],
) -> None:
    """Test that a song with an ampersand in the title can be parsed."""

    yamaha_yas_209.on_event_wrapper(upnp_service_av_transport, [upnp_state_variable])


@pytest.mark.upnp_value_path(
    # Obvs by Jamie XX
    FLAT_FILES_DIR
    / "xml"
    / "yamaha_yas_209"
    / "event_payloads"
    / "av_transport"
    / "payload_20220622204720404264.xml"
)
@patch("wg_utilities.devices.yamaha_yas_209.YamahaYas209.set_state")
def test_av_transport_state_change_updates_local_state(
    mock_set_state: MagicMock,
    yamaha_yas_209: YamahaYas209,
    upnp_service_av_transport: UpnpService,
    upnp_state_variable: UpnpStateVariable[str],
) -> None:
    """Test that an AVTransport service state change updates the local state."""

    def _mock_set_state_side_effect(
        state: Yas209State, local_only: bool = False
    ) -> None:
        _ = local_only
        yamaha_yas_209._state = state

    mock_set_state.side_effect = _mock_set_state_side_effect

    assert yamaha_yas_209.state == Yas209State.UNKNOWN
    yamaha_yas_209.on_event_wrapper(upnp_service_av_transport, [upnp_state_variable])
    assert (
        yamaha_yas_209.state == Yas209State.PLAYING  # type: ignore[comparison-overlap]
    )

    mock_set_state.assert_called_once_with(
        Yas209State.PLAYING,
        local_only=True,
    )

    mock_set_state.reset_mock()

    new_upnp_state_variable = deepcopy(upnp_state_variable)
    new_upnp_state_variable.upnp_value = dedent(
        """
        <Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
          <InstanceID val="0">
          <TransportState val="STOPPED"/>
          <CurrentTransportActions val="Play,Stop"/>
          </InstanceID>
        </Event>
    """
    ).strip()

    yamaha_yas_209.on_event_wrapper(
        upnp_service_av_transport, [new_upnp_state_variable]
    )

    assert yamaha_yas_209.state == Yas209State.STOPPED

    mock_set_state.assert_called_once_with(
        Yas209State.STOPPED,
        local_only=True,
    )


@pytest.mark.upnp_value_path(
    # Obvs by Jamie XX
    FLAT_FILES_DIR
    / "xml"
    / "yamaha_yas_209"
    / "event_payloads"
    / "av_transport"
    / "payload_20220622204720404264.xml"
)
def test_av_transport_ctm_updates_current_track(
    yamaha_yas_209: YamahaYas209,
    upnp_service_av_transport: UpnpService,
    upnp_state_variable: UpnpStateVariable[str],
    current_track_null: CurrentTrack,
    mock_aiohttp: aioresponses,
) -> None:
    """Test that an AVTransport service state change updates the local state attribute.

    The `on_event_wrapper` is called a couple of times with different
    UPNPStateVariables. The `current_track` and `state` properties are checked each
    time for complete testing throughout.
    """

    get_media_info_response_nothing_playing = (
        FLAT_FILES_DIR
        / "xml"
        / "yamaha_yas_209"
        / "get_media_info"
        / "nothing_playing.xml"
    ).read_text()

    mock_aiohttp.post(
        f"http://{yamaha_yas_209.ip}:49152/upnp/control/rendertransport1",
        status=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        body=get_media_info_response_nothing_playing,
    )

    new_upnp_state_variable = deepcopy(upnp_state_variable)
    new_upnp_state_variable.upnp_value = dedent(
        """
        <Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
          <InstanceID val="0">
          <TransportState val="STOPPED"/>
          <CurrentTransportActions val="Play,Stop"/>
          </InstanceID>
        </Event>
    """
    ).strip()

    assert yamaha_yas_209.state == Yas209State.UNKNOWN
    assert yamaha_yas_209.current_track == current_track_null

    yamaha_yas_209.on_event_wrapper(
        upnp_service_av_transport, [new_upnp_state_variable]
    )

    assert (
        yamaha_yas_209.state == Yas209State.STOPPED  # type: ignore[comparison-overlap]
    )
    assert yamaha_yas_209.current_track == current_track_null

    yamaha_yas_209.on_event_wrapper(upnp_service_av_transport, [upnp_state_variable])
    assert yamaha_yas_209.state == Yas209State.PLAYING
    assert yamaha_yas_209.current_track == CurrentTrack(
        # pylint: disable=line-too-long
        album_art_uri="https://i.scdn.co/image/ab67616d0000b2736aa1dfa0a98baa542251df5a",
        media_album_name="In Colour",
        media_artist="Jamie xx",
        media_duration=231.0,
        media_title="Obvs",
    )

    yamaha_yas_209.on_event_wrapper(
        upnp_service_av_transport, [new_upnp_state_variable]
    )

    assert yamaha_yas_209.state == Yas209State.STOPPED
    assert yamaha_yas_209.current_track == current_track_null


@pytest.mark.upnp_value_path(
    FLAT_FILES_DIR
    / "xml"
    / "yamaha_yas_209"
    / "event_payloads"
    / "rendering_control"
    / "56.xml"
)
@patch("wg_utilities.devices.yamaha_yas_209.YamahaYas209.set_volume_level")
def test_rendering_control_updates_volume(
    mock_set_volume_level: MagicMock,
    yamaha_yas_209: YamahaYas209,
    upnp_service_rendering_control: UpnpService,
    upnp_state_variable: UpnpStateVariable[str],
    mock_aiohttp: aioresponses,
) -> None:
    """Test that an AVTransport service state change updates the local state."""

    def _mock_set_volume_level_side_effect(
        value: float, local_only: bool = False
    ) -> None:
        _ = local_only

        yamaha_yas_209._volume_level = round(value, 2)

    mock_set_volume_level.side_effect = _mock_set_volume_level_side_effect

    get_volume_response = (
        FLAT_FILES_DIR / "xml" / "yamaha_yas_209" / "get_volume" / "50.xml"
    ).read_text()

    mock_aiohttp.post(
        f"http://{yamaha_yas_209.ip}:49152/upnp/control/rendercontrol1",
        status=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        body=get_volume_response,
    )

    assert yamaha_yas_209.volume_level == 0.5

    yamaha_yas_209.on_event_wrapper(
        upnp_service_rendering_control, [upnp_state_variable]
    )
    assert yamaha_yas_209.volume_level == 0.56

    mock_set_volume_level.assert_called_once_with(
        0.56,
        local_only=True,
    )

    mock_set_volume_level.reset_mock()

    new_upnp_state_variable = deepcopy(upnp_state_variable)
    new_upnp_state_variable.upnp_value = dedent(
        """
            <Event xmlns="urn:schemas-upnp-org:metadata-1-0/RCS/">
                <InstanceID val="0">
                    <Volume channel="Master" val="20"/>
                    <Mute channel="Master" val="0"/>
                    <TimeStamp val="93296666"/>
                </InstanceID>
            </Event>
        """
    ).strip()

    yamaha_yas_209.on_event_wrapper(
        upnp_service_rendering_control, [new_upnp_state_variable]
    )

    assert yamaha_yas_209.volume_level == 0.2

    mock_set_volume_level.assert_called_once_with(
        0.2,
        local_only=True,
    )


@freeze_time()
def test_on_event_callback_called_correctly(
    yamaha_yas_209: YamahaYas209,
    upnp_service_rendering_control: UpnpService,
    upnp_state_variable: UpnpStateVariable[str],
) -> None:
    """Test that the callback is called correctly.

    Bit of a long test this one, needed some "verbose" setup -.-
    """

    payload_dir = FLAT_FILES_DIR / "xml" / "yamaha_yas_209" / "event_payloads"

    # `upnp_state_variable` is "blank", so first thing to do is make an `AVTransport`
    # copy and a `RenderingControl` copy
    upnp_state_variable_rendering_control = deepcopy(upnp_state_variable)
    upnp_state_variable_av_transport = deepcopy(upnp_state_variable)

    # The `RenderingControl` copy is pretty simple as the service argument is
    # RenderingControl-flavoured
    upnp_state_variable_rendering_control.upnp_value = (
        payload_dir / "rendering_control" / "56.xml"
    ).read_text()

    upnp_state_variable_av_transport.upnp_value = (
        payload_dir / "av_transport" / "payload_20220622204720404264.xml"
    ).read_text()
    # The `AVTransport` state variable needs to be re-written, mainly to change the
    # name from `LastChange` to something else

    upnp_state_variable_av_transport._state_variable_info = StateVariableInfo(
        name="SomethingElse",
        send_events=True,
        type_info=StateVariableTypeInfo(
            data_type="string",
            data_type_mapping={"type": str, "in": str, "out": str},
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=(
                something_else_xml := ElementTree.fromstring(
                    """
                    <ns0:stateVariable xmlns:ns0="urn:schemas-upnp-org:service-1-0"
                                        sendEvents="yes">
                        <ns0:name>SomethingElse</ns0:name>
                        <ns0:dataType>string</ns0:dataType>
                    </ns0:stateVariable>
                """
                )
            ),
        ),
        xml=something_else_xml,
    )

    call_count = 0

    def _on_event(payload: YamahaYas209.EventPayloadInfo) -> None:
        nonlocal call_count

        # To parse the XML in the same way as the YamahaYas209, we first need to wrap
        # it in a dict
        last_change_value = {"-": upnp_state_variable_rendering_control.upnp_value}
        something_else_value = {
            "SomethingElse": upnp_state_variable_av_transport.upnp_value
        }

        # Those "XML-dicts" can then be parsed into full "JSON-dicts"

        yamaha_yas_209._parse_xml_dict(last_change_value)  # type: ignore[arg-type]
        yamaha_yas_209._parse_xml_dict(something_else_value)  # type: ignore[arg-type]

        assert payload == {
            # This whole test has frozen time, so we can just use `datetime.utcnow()`
            "timestamp": datetime.utcnow(),
            "service_id": upnp_service_rendering_control.service_id,
            "service_type": upnp_service_rendering_control.service_type,
            # The last change will be a `LastChange` instance
            "last_change": LastChangeRenderingControl.parse(
                last_change_value["-"]  # type: ignore[arg-type]
            ),
            "other_xml_payloads": something_else_value,
        }

        call_count += 1

    yamaha_yas_209.on_event_wrapper(
        upnp_service_rendering_control,
        [upnp_state_variable_rendering_control, upnp_state_variable_av_transport],
    )

    assert call_count == 0

    # Set the `on_event` callback
    yamaha_yas_209.on_event = _on_event

    yamaha_yas_209.on_event_wrapper(
        upnp_service_rendering_control,
        [upnp_state_variable_rendering_control, upnp_state_variable_av_transport],
    )

    assert call_count == 1


def test_call_service_action_value_error(yamaha_yas_209: YamahaYas209) -> None:
    """Test that an unknown action raise a `ValueError`."""

    with pytest.raises(ValueError) as exc_info:
        yamaha_yas_209._call_service_action(
            Yas209Service.AVT,
            "GetCurrentConnectionIDs",
        )

    assert str(exc_info.value) == (
        "Unexpected action 'GetCurrentConnectionIDs' for service 'AVTransport'. Must "
        "be one of 'GetCurrentTransportActions', 'GetDeviceCapabilities', 'GetInfoEx', "
        "'GetMediaInfo', 'GetPlayType', 'GetPositionInfo', 'GetTransportInfo', "
        "'GetTransportSettings', 'Next', 'Pause', 'Play', 'Previous', 'Seek', "
        "'SeekBackward', 'SeekForward', 'SetAVTransportURI', 'SetPlayMode', 'Stop'"
    )


def test_call_service_routes_call_correctly(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test that a service action is called correctly."""

    get_media_info_response = (
        FLAT_FILES_DIR
        / "xml"
        / "yamaha_yas_209"
        / "get_media_info"
        / "different_people_spotify.xml"
    ).read_text()

    mock_aiohttp.post(
        url := f"http://{yamaha_yas_209.ip}:49152/upnp/control/rendertransport1",
        status=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        body=get_media_info_response,
    )

    yamaha_yas_209._call_service_action(Yas209Service.AVT, "GetMediaInfo", InstanceID=0)

    assert_only_post_request_is(url, mock_aiohttp.requests, yamaha_yas_209)


def test_call_service_action_callback(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test that a service action is called correctly."""

    get_media_info_response = (
        FLAT_FILES_DIR
        / "xml"
        / "yamaha_yas_209"
        / "get_media_info"
        / "different_people_spotify.xml"
    ).read_text()

    mock_aiohttp.post(
        f"http://{yamaha_yas_209.ip}:49152/upnp/control/rendertransport1",
        status=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        body=get_media_info_response,
    )

    call_count = 0

    def _cb(res: Mapping[str, object]) -> None:
        nonlocal call_count
        assert (
            str(res["CurrentURIMetaData"]).strip()
            == parse_xml(get_media_info_response)["s:Envelope"]["s:Body"][
                "u:GetMediaInfoResponse"
            ]["CurrentURIMetaData"].strip()
        )
        call_count += 1

    yamaha_yas_209._call_service_action(
        Yas209Service.AVT, "GetMediaInfo", InstanceID=0, callback=_cb
    )

    assert call_count == 1


def test_pause_calls_correct_service_action(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the pause method calls the correct service action."""

    with patch.object(
        yamaha_yas_209, "_call_service_action"
    ) as mock_call_service_action:
        yamaha_yas_209.pause()

        mock_call_service_action.assert_called_once_with(
            Yas209Service.AVT, "Pause", InstanceID=0
        )


def test_play_calls_correct_service_action(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the play method calls the correct service action."""

    with patch.object(
        yamaha_yas_209, "_call_service_action"
    ) as mock_call_service_action:
        yamaha_yas_209.play()

        mock_call_service_action.assert_called_once_with(
            Yas209Service.AVT, "Play", InstanceID=0, Speed="1"
        )


def test_play_pause_calls_correct_service_action(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the play_pause method calls the correct service action."""

    with patch.object(yamaha_yas_209, "pause") as mock_pause, patch.object(
        yamaha_yas_209, "play"
    ) as mock_play:
        yamaha_yas_209.play_pause()

        assert yamaha_yas_209.state == Yas209State.UNKNOWN
        mock_play.assert_called_once()

        yamaha_yas_209.set_state(Yas209State.PLAYING, local_only=True)
        assert (
            yamaha_yas_209.state
            == Yas209State.PLAYING  # type: ignore[comparison-overlap]
        )

        yamaha_yas_209.play_pause()
        mock_play.assert_called_once()
        mock_pause.assert_called_once()


def test_mute_calls_correct_service_action(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the mute method calls the correct service action."""

    with patch.object(
        yamaha_yas_209, "_call_service_action"
    ) as mock_call_service_action:
        yamaha_yas_209.mute()

        mock_call_service_action.assert_called_once_with(
            Yas209Service.RC,
            "SetMute",
            InstanceID=0,
            Channel="Master",
            DesiredMute=True,
        )


def test_next_track_calls_correct_service_action(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the next_track method calls the correct service action."""

    with patch.object(
        yamaha_yas_209, "_call_service_action"
    ) as mock_call_service_action:
        yamaha_yas_209.next_track()

        mock_call_service_action.assert_called_once_with(
            Yas209Service.AVT, "Next", InstanceID=0
        )


def test_previous_track_calls_correct_service_action(
    yamaha_yas_209: YamahaYas209,
) -> None:
    """Test that the previous_track method calls the correct service action."""

    with patch.object(
        yamaha_yas_209, "_call_service_action"
    ) as mock_call_service_action:
        yamaha_yas_209.previous_track()

        mock_call_service_action.assert_called_once_with(
            Yas209Service.AVT, "Previous", InstanceID=0
        )


def test_set_state_raises_type_error(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the set_state method raises a TypeError for an invalid state."""

    with pytest.raises(TypeError) as exc_info:
        yamaha_yas_209.set_state("invalid_state")  # type: ignore[arg-type]

    assert str(exc_info.value) == "Expected a Yas209State instance."


def test_set_state_sets_local_state(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the set_state method sets the local state."""

    yamaha_yas_209.set_state(Yas209State.PLAYING, local_only=True)

    assert yamaha_yas_209.state == Yas209State.PLAYING

    with patch.object(yamaha_yas_209, "play") as mock_play, patch.object(
        yamaha_yas_209, "pause"
    ) as mock_pause, patch.object(yamaha_yas_209, "stop") as mock_stop:
        yamaha_yas_209.set_state(Yas209State.PLAYING, local_only=True)

        mock_play.assert_not_called()

        yamaha_yas_209.set_state(Yas209State.PAUSED_PLAYBACK, local_only=True)

        mock_pause.assert_not_called()

        yamaha_yas_209.set_state(Yas209State.STOPPED, local_only=True)

        mock_stop.assert_not_called()


def test_set_state_sets_correct_state_property(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the set_state method sets the correct state property."""

    with patch.object(yamaha_yas_209, "play") as mock_play, patch.object(
        yamaha_yas_209, "pause"
    ) as mock_pause, patch.object(yamaha_yas_209, "stop") as mock_stop:
        yamaha_yas_209.set_state(Yas209State.PLAYING, local_only=False)

        assert yamaha_yas_209.state == Yas209State.PLAYING
        mock_play.assert_called_once()

        yamaha_yas_209.set_state(Yas209State.PAUSED_PLAYBACK, local_only=False)

        assert (
            yamaha_yas_209.state
            == Yas209State.PAUSED_PLAYBACK  # type: ignore[comparison-overlap]
        )
        mock_pause.assert_called_once()

        yamaha_yas_209.set_state(Yas209State.STOPPED, local_only=False)

        assert yamaha_yas_209.state == Yas209State.STOPPED
        mock_stop.assert_called_once()


def test_set_state_on_state_update(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the set_state method calls the state callback."""

    call_count = 0
    active_state = None

    def _cb(state_value: str) -> None:
        nonlocal call_count

        assert active_state is not None
        assert state_value == active_state.value
        call_count += 1

    yamaha_yas_209.on_state_update = _cb

    yamaha_yas_209.set_state(active_state := Yas209State.PLAYING, local_only=True)
    assert call_count == 1

    yamaha_yas_209.set_state(
        active_state := Yas209State.PAUSED_PLAYBACK, local_only=True
    )
    assert call_count == 2

    yamaha_yas_209.set_state(active_state := Yas209State.STOPPED, local_only=True)
    assert call_count == 3


def test_set_volume_level_calls_correct_service_action(
    yamaha_yas_209: YamahaYas209,
) -> None:
    """Test that the set_volume_level method calls the correct service action."""

    with patch.object(
        yamaha_yas_209, "_call_service_action"
    ) as mock_call_service_action:
        yamaha_yas_209.set_volume_level(0.5)

        mock_call_service_action.assert_called_once_with(
            Yas209Service.RC,
            "SetVolume",
            InstanceID=0,
            Channel="Master",
            DesiredVolume=50,
        )


def test_set_volume_level_raises_value_error(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the `set_volume_level` method raises a ValueError."""

    with pytest.raises(ValueError) as exc_info:
        yamaha_yas_209.set_volume_level(1.1)

    assert str(exc_info.value) == "Volume level must be between 0 and 1"

    with pytest.raises(ValueError) as exc_info:
        yamaha_yas_209.set_volume_level(-0.1)

    assert str(exc_info.value) == "Volume level must be between 0 and 1"


def test_set_volume_level_on_volume_update(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the set_volume_level method calls the volume_level callback."""

    call_count = 0
    active_volume_level = 0.0

    def _cb(volume_level_value: float) -> None:
        nonlocal call_count

        assert volume_level_value == active_volume_level
        call_count += 1

    yamaha_yas_209.on_volume_update = _cb

    yamaha_yas_209.set_volume_level(active_volume_level := 0.5, local_only=True)
    assert call_count == 1

    yamaha_yas_209.set_volume_level(active_volume_level := 0.25, local_only=True)
    assert call_count == 2

    yamaha_yas_209.set_volume_level(active_volume_level := 0.75, local_only=True)
    assert call_count == 3


def test_stop_calls_correct_service_action(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the stop method calls the correct service action."""

    with patch.object(
        yamaha_yas_209, "_call_service_action"
    ) as mock_call_service_action:
        yamaha_yas_209.stop()

        mock_call_service_action.assert_called_once_with(
            Yas209Service.AVT, "Stop", InstanceID=0, Speed="1"
        )


def test_stop_listening_sets_attribute(
    yamaha_yas_209: YamahaYas209, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the `stop_listening` sets the attribute as expected."""

    yamaha_yas_209._listening = True

    caplog.clear()
    yamaha_yas_209.stop_listening()

    assert yamaha_yas_209.is_listening is False
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == DEBUG
    assert (
        caplog.records[0].message
        == "Stopping event listener (will take <= 120 seconds)"
    )


def test_unmute_calls_correct_service_action(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the unmute method calls the correct service action."""

    with patch.object(
        yamaha_yas_209, "_call_service_action"
    ) as mock_call_service_action:
        yamaha_yas_209.unmute()

        mock_call_service_action.assert_called_once_with(
            Yas209Service.RC,
            "SetMute",
            InstanceID=0,
            Channel="Master",
            DesiredMute=False,
        )


def test_volume_down_calls_correct_service_action(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the volume_down method calls the correct service action."""

    yamaha_yas_209.set_volume_level(current_level := 0.5, local_only=True)

    def _set_volume(volume_level: float) -> None:
        yamaha_yas_209._volume_level = volume_level

    with patch.object(
        yamaha_yas_209, "set_volume_level", side_effect=_set_volume
    ) as mock_set_volume_level:
        for _ in range(10):
            yamaha_yas_209.volume_down()
            mock_set_volume_level.assert_called_once_with(
                current_level := round(current_level - 0.02, 2)
            )
            mock_set_volume_level.reset_mock()


def test_volume_up_calls_correct_service_action(yamaha_yas_209: YamahaYas209) -> None:
    """Test that the volume_up method calls the correct service action."""

    yamaha_yas_209.set_volume_level(current_level := 0.5, local_only=True)

    def _set_volume(volume_level: float) -> None:
        yamaha_yas_209._volume_level = volume_level

    with patch.object(
        yamaha_yas_209, "set_volume_level", side_effect=_set_volume
    ) as mock_set_volume_level:
        for _ in range(10):
            yamaha_yas_209.volume_up()
            mock_set_volume_level.assert_called_once_with(
                current_level := round(current_level + 0.02, 2)
            )
            mock_set_volume_level.reset_mock()


def test_album_art_uri_property(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test that the album_art_uri property returns the expected value."""

    mock_aiohttp.post(
        url := f"http://{yamaha_yas_209.ip}:49152/upnp/control/rendertransport1",
        status=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        body=(
            FLAT_FILES_DIR
            / "xml"
            / "yamaha_yas_209"
            / "get_media_info"
            / "different_people_spotify.xml"
        ).read_text(),
    )

    assert (
        yamaha_yas_209.album_art_uri
        == "https://i.scdn.co/image/ab67616d0000b273c565a3629c5def95a0f85668"
    )
    assert_only_post_request_is(url, mock_aiohttp.requests, yamaha_yas_209)


def test_current_track_property_gets_correct_info(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test that the current_track property gets the correct info."""

    url = mock_get_info_response("on_top_spotify.xml", mock_aiohttp, yamaha_yas_209)

    assert not hasattr(yamaha_yas_209, "_current_track")
    assert yamaha_yas_209.current_track == ON_TOP
    assert hasattr(yamaha_yas_209, "_current_track")
    assert_only_post_request_is(url, mock_aiohttp.requests, yamaha_yas_209)

    with patch.object(yamaha_yas_209, "get_media_info") as mock_get_media_info:
        assert yamaha_yas_209.current_track == ON_TOP
        mock_get_media_info.assert_not_called()


def test_current_track_setter_on_track_update(yamaha_yas_209: YamahaYas209) -> None:
    """Test the `current_track` setter calls the callback with the correct value."""

    call_count = 0

    def _cb(value: CurrentTrack.Info) -> None:
        nonlocal call_count
        assert value == ON_TOP.json
        call_count += 1

    yamaha_yas_209.on_track_update = _cb
    yamaha_yas_209.current_track = ON_TOP

    assert call_count == 1


def test_current_track_setter_raises_type_error(yamaha_yas_209: YamahaYas209) -> None:
    """Test the `current_track` setter raises a `TypeError` with invalid types."""

    with pytest.raises(TypeError) as exc_info:
        yamaha_yas_209.current_track = "invalid"  # type: ignore[assignment]

    assert str(exc_info.value) == "Expected a CurrentTrack instance."


def test_media_album_name_property_gets_correct_info(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test that the media_album_name property gets the correct info."""

    url = mock_get_info_response("on_top_spotify.xml", mock_aiohttp, yamaha_yas_209)

    assert not hasattr(yamaha_yas_209, "_current_track")
    assert yamaha_yas_209.media_album_name == "Flume"
    assert yamaha_yas_209._current_track == ON_TOP
    assert_only_post_request_is(url, mock_aiohttp.requests, yamaha_yas_209)

    with patch.object(yamaha_yas_209, "get_media_info") as mock_get_media_info:
        assert yamaha_yas_209.media_album_name == "Flume"
        mock_get_media_info.assert_not_called()


def test_media_artist_property_gets_correct_info(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test that the media_artist property gets the correct info."""

    url = mock_get_info_response("on_top_spotify.xml", mock_aiohttp, yamaha_yas_209)

    assert not hasattr(yamaha_yas_209, "_current_track")
    assert yamaha_yas_209.media_artist == "Flume"
    assert yamaha_yas_209._current_track == ON_TOP
    assert_only_post_request_is(url, mock_aiohttp.requests, yamaha_yas_209)

    with patch.object(yamaha_yas_209, "get_media_info") as mock_get_media_info:
        assert yamaha_yas_209.media_artist == "Flume"
        mock_get_media_info.assert_not_called()


def test_media_duration_property_gets_correct_info(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test that the media_duration property gets the correct info."""

    url = mock_get_info_response("on_top_spotify.xml", mock_aiohttp, yamaha_yas_209)

    assert not hasattr(yamaha_yas_209, "_current_track")
    assert yamaha_yas_209.media_duration == 231
    assert yamaha_yas_209._current_track == ON_TOP
    assert_only_post_request_is(url, mock_aiohttp.requests, yamaha_yas_209)

    with patch.object(yamaha_yas_209, "get_media_info") as mock_get_media_info:
        assert yamaha_yas_209.media_duration == 231
        mock_get_media_info.assert_not_called()


def test_get_media_info(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test that the get_media_info method returns the correct info."""

    url = mock_get_info_response("on_top_spotify.xml", mock_aiohttp, yamaha_yas_209)

    assert yamaha_yas_209.get_media_info() == {
        "CurrentURI": "spotify:track:42Kznon0GBYL1bU24DkZSm",
        "CurrentURIMetaData": {
            "item": {
                "dc:creator": "Flume",
                "dc:title": "On Top",
                "id": "0",
                "res": {
                    "duration": "00:03:51.000",
                    # pylint: disable=line-too-long
                    "protocolInfo": "http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=01;",
                    "text": "spotify:track:42Kznon0GBYL1bU24DkZSm",
                },
                "song:albumid": "0",
                "song:description": None,
                "song:id": "42Kznon0GBYL1bU24DkZSm",
                "song:like": "0",
                "song:singerid": "0",
                "song:skiplimit": "0",
                "song:subid": "Outrun",
                "upnp:album": "Flume",
                # pylint: disable=line-too-long
                "upnp:albumArtURI": "https://i.scdn.co/image/ab67616d0000b2733198dc8920850509e8a07d8c",
                "upnp:artist": "Flume",
            },
            "upnp:class": "object.item.audioItem.musicTrack",
            "xmlns": "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/",
            "xmlns:dc": "http://purl.org/dc/elements/1.1/",
            "xmlns:song": "www.wiimu.com/song/",
            "xmlns:upnp": "urn:schemas-upnp-org:metadata-1-0/upnp/",
        },
        "MediaDuration": "00:03:51",
        "NextURI": "",
        "NextURIMetaData": "",
        "NrTracks": 0,
        "PlayMedium": "SPOTIFY",
        "RecordMedium": "NOT_IMPLEMENTED",
        "TrackSource": "spotify:playlist:0rByozJfX63TyYLWoMVnrl",
        "WriteStatus": "NOT_IMPLEMENTED",
    }
    assert_only_post_request_is(url, mock_aiohttp.requests, yamaha_yas_209)


def test_media_title_property_gets_correct_info(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test that the media_title property gets the correct info."""
    url = mock_get_info_response("on_top_spotify.xml", mock_aiohttp, yamaha_yas_209)

    assert not hasattr(yamaha_yas_209, "_current_track")
    assert yamaha_yas_209.media_title == "On Top"

    assert yamaha_yas_209._current_track == ON_TOP
    assert_only_post_request_is(url, mock_aiohttp.requests, yamaha_yas_209)

    with patch.object(yamaha_yas_209, "get_media_info") as mock_get_media_info:
        assert yamaha_yas_209.media_title == "On Top"
        mock_get_media_info.assert_not_called()


def test_state_property(yamaha_yas_209: YamahaYas209) -> None:
    """Test the state property returns the correct value."""
    assert not hasattr(yamaha_yas_209, "_state")
    assert yamaha_yas_209.state == Yas209State.UNKNOWN

    yamaha_yas_209.set_state(Yas209State.PLAYING, local_only=True)

    assert yamaha_yas_209.state == yamaha_yas_209._state == Yas209State.PLAYING


def test_volume_level_property_returns_correct_value(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test the volume_level property returns the correct value."""

    get_volume_response = (
        FLAT_FILES_DIR / "xml" / "yamaha_yas_209" / "get_volume" / "50.xml"
    ).read_text()

    mock_aiohttp.post(
        f"http://{yamaha_yas_209.ip}:49152/upnp/control/rendercontrol1",
        status=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        body=get_volume_response,
    )

    assert not hasattr(yamaha_yas_209, "_volume_level")
    assert yamaha_yas_209.volume_level == yamaha_yas_209._volume_level == 0.5


def test_needs_device_decorator(
    yamaha_yas_209: YamahaYas209, mock_aiohttp: aioresponses
) -> None:
    """Test that the needs_device decorator works."""

    assert not hasattr(yamaha_yas_209, "device")

    @_needs_device  # type: ignore[arg-type]
    def _worker(self: YamahaYas209) -> None:
        """Test the decorator with dummy function."""
        assert self == yamaha_yas_209

    _worker(yamaha_yas_209)

    assert hasattr(yamaha_yas_209, "device")
    assert isinstance(yamaha_yas_209.device, UpnpDevice)
    assert yamaha_yas_209.device.device_url == yamaha_yas_209.description_url
    assert yamaha_yas_209.device.friendly_name == "Will's YAS-209"

    assert next(iter(mock_aiohttp.requests.keys())) == (
        "GET",
        URL("http://192.168.1.1:49152/description.xml"),
    )

    mock_aiohttp.requests.clear()

    # Calling the function once the device already exists should not make a new request
    _worker(yamaha_yas_209)

    assert not mock_aiohttp.requests


def test_subscribe_creates_notify_server_with_correct_subscriptions(
    yamaha_yas_209: YamahaYas209,
    mock_aiohttp: aioresponses,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the `_subscribe` method creates a notify server.

    The subscription calls and logging are also tested.
    """

    add_av_subscription_call(mock_aiohttp, yamaha_yas_209)
    add_rc_subscription_call(mock_aiohttp, yamaha_yas_209)

    fake_aiohttp_server: AiohttpNotifyServer | None = None

    def _sleep_side_effect(_: int) -> None:
        """When the `async_sleep` call is made, force-stop the subscription loop."""
        yamaha_yas_209._listening = False

    def _fake_server(
        requester: UpnpRequester,
        source: AddressTupleVXType,
        callback_url: str,
    ) -> AiohttpNotifyServer:
        """Create a real/fake(?) server for use in the test."""
        nonlocal fake_aiohttp_server
        fake_aiohttp_server = AiohttpNotifyServer(
            requester=requester, source=source, callback_url=callback_url
        )
        return fake_aiohttp_server

    local_ip = get_local_ip("")

    with patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.AiohttpNotifyServer",
        side_effect=_fake_server,
    ) as mock_aiohttp_notify_server, patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.async_sleep",
        side_effect=_sleep_side_effect,
    ):
        caplog.clear()
        new_event_loop().run_until_complete(yamaha_yas_209._subscribe())

        assert fake_aiohttp_server is not None

        mock_aiohttp_notify_server.assert_called_once_with(
            yamaha_yas_209.device.requester,
            source=(local_ip, yamaha_yas_209._source_port),
            callback_url="http://192.168.1.2:12345/notify",
        )

    assert (first_record := caplog.records.pop(0)).levelno == DEBUG
    assert first_record.message == dedent(
        f"""
        Listen IP:          192.168.1.2
        Listen Port:        12345
        Source IP:          {local_ip}
        Source Port:        0
        Callback URL:       http://192.168.1.2:12345/notify
        Server Listen IP:   {local_ip}
        Server Listen Port: {fake_aiohttp_server.listen_port}
        """
    )
    assert (second_record := caplog.records.pop(0)).levelno == INFO
    assert second_record.message == f"Subscribed to {Yas209Service.AVT.service_id}"
    assert (third_record := caplog.records.pop(0)).levelno == INFO
    assert third_record.message == f"Subscribed to {Yas209Service.RC.service_id}"

    mock_aiohttp.requests.pop(
        ("SUBSCRIBE", URL("http://192.168.1.1:49152/upnp/event/rendertransport1"))
    )
    mock_aiohttp.requests.pop(
        ("SUBSCRIBE", URL("http://192.168.1.1:49152/upnp/event/rendercontrol1"))
    )
    assert all(key[0] == "GET" for key in mock_aiohttp.requests)


def test_subscribe_creates_notify_server_logs_subscription_errors(
    yamaha_yas_209: YamahaYas209,
    mock_aiohttp: aioresponses,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the `_subscribe` method logs any exceptions when subscribing to services."""

    add_av_subscription_call(mock_aiohttp, yamaha_yas_209)
    add_rc_subscription_call(
        mock_aiohttp,
        yamaha_yas_209,
        exception=(UpnpResponseError(status=HTTPStatus.INTERNAL_SERVER_ERROR)),
    )

    def _sleep_side_effect(_: int) -> None:
        """When the `async_sleep` call is made, force-stop the subscription loop."""
        yamaha_yas_209._listening = False

    with patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.async_sleep",
        side_effect=_sleep_side_effect,
    ):
        caplog.clear()
        new_event_loop().run_until_complete(yamaha_yas_209._subscribe())

    # Verbose debug log
    caplog.records.pop(0)

    assert (second_record := caplog.records.pop(0)).levelno == INFO
    assert second_record.message == f"Subscribed to {Yas209Service.AVT.service_id}"
    assert (third_record := caplog.records.pop(0)).levelno == ERROR
    assert (
        third_record.message == f"Unable to subscribe to {Yas209Service.RC.service_id}"
    )

    assert mock_aiohttp.requests.pop(
        ("SUBSCRIBE", URL("http://192.168.1.1:49152/upnp/event/rendertransport1"))
    ) == [FRESH_SUBSCRIPTION_CALL]
    assert mock_aiohttp.requests.pop(
        ("SUBSCRIBE", URL("http://192.168.1.1:49152/upnp/event/rendercontrol1"))
    ) == [FRESH_SUBSCRIPTION_CALL]
    assert all(key[0] == "GET" for key in mock_aiohttp.requests)


def test_subscribe_resubscribes_to_active_services(
    yamaha_yas_209: YamahaYas209,
    mock_aiohttp: aioresponses,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the `_subscribe` method logs any exceptions when subscribing to services."""

    add_av_subscription_call(mock_aiohttp, yamaha_yas_209, repeat=True)
    add_rc_subscription_call(mock_aiohttp, yamaha_yas_209, repeat=True)

    call_count = 0

    def _sleep_side_effect(_: int) -> None:
        """Skip sleep delays.

        Will cause the loop to exit after 121 calls (i.e. after the first main
        subscription loop).
        """
        nonlocal call_count
        call_count += 1
        if call_count > 120:
            yamaha_yas_209._listening = False

    with patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.async_sleep",
        side_effect=_sleep_side_effect,
    ):
        caplog.clear()
        new_event_loop().run_until_complete(yamaha_yas_209._subscribe())

    assert mock_aiohttp.requests.pop(
        ("SUBSCRIBE", URL("http://192.168.1.1:49152/upnp/event/rendertransport1"))
    ) == [FRESH_SUBSCRIPTION_CALL, RESUBSCRIPTION_CALL_AV]

    assert mock_aiohttp.requests.pop(
        ("SUBSCRIBE", URL("http://192.168.1.1:49152/upnp/event/rendercontrol1"))
    ) == [FRESH_SUBSCRIPTION_CALL, RESUBSCRIPTION_CALL_RC]
    assert all(key[0] == "GET" for key in mock_aiohttp.requests)
    assert "Resubscribing to all services" in caplog.text

    assert call_count == 121


def test_subscribe_resubscribes_to_failed_services(
    yamaha_yas_209: YamahaYas209,
    mock_aiohttp: aioresponses,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the `_subscribe` method logs any exceptions when subscribing to services."""

    add_av_subscription_call(mock_aiohttp, yamaha_yas_209, repeat=True)
    add_rc_subscription_call(
        mock_aiohttp,
        yamaha_yas_209,
        exception=UpnpResponseError(status=HTTPStatus.INTERNAL_SERVER_ERROR),
    )
    add_rc_subscription_call(mock_aiohttp, yamaha_yas_209, repeat=True)

    call_count = 0

    def _sleep_side_effect(_: int) -> None:
        """Skip sleep delays.

        Will cause the loop to exit after 121 calls (i.e. after the first main
        subscription loop).
        """
        nonlocal call_count
        call_count += 1
        if call_count > 120:
            yamaha_yas_209._listening = False

    with patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.async_sleep",
        side_effect=_sleep_side_effect,
    ):
        caplog.clear()
        new_event_loop().run_until_complete(yamaha_yas_209._subscribe())

    assert caplog.records[-1].levelno == DEBUG
    assert (
        caplog.records[-1].message
        == "Exiting subscription loop, `self._listening` is `False`"
    )

    assert caplog.records[-2].levelno == DEBUG
    assert caplog.records[-2].message == "Exiting listener loop"

    assert caplog.records[-3].levelno == DEBUG
    assert (
        caplog.records[-3].message
        == f"Attempting to create originally failed subscription for"
        f" {Yas209Service.RC.service_id}"
    )

    assert call_count == 121


@pytest.mark.parametrize(
    ("logging", "expected_level"),
    [
        (True, ERROR),
        (False, WARNING),
    ],
)
def test_subscribe_keeps_retrying_failed_subscriptions(
    yamaha_yas_209: YamahaYas209,
    mock_aiohttp: aioresponses,
    caplog: pytest.LogCaptureFixture,
    logging: bool,
    expected_level: int,
) -> None:
    """Test the `_subscribe` method logs any exceptions when subscribing to services."""

    yamaha_yas_209._logging = logging

    add_av_subscription_call(mock_aiohttp, yamaha_yas_209, repeat=True)

    # Mock the RC subscription call to fail on the first two attempts
    add_rc_subscription_call(
        mock_aiohttp,
        yamaha_yas_209,
        exception=(
            response_exception := UpnpResponseError(
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
        ),
    )
    add_rc_subscription_call(mock_aiohttp, yamaha_yas_209, exception=response_exception)

    # Mock the RC subscription call to succeed thereafter
    add_rc_subscription_call(mock_aiohttp, yamaha_yas_209, repeat=True)

    call_count = 0

    def _sleep_side_effect(_: int) -> None:
        """Skip sleep delays.

        Will cause the loop to exit after 121 calls (i.e. after the first main
        subscription loop).
        """
        nonlocal call_count
        call_count += 1
        if call_count > 120:
            yamaha_yas_209._listening = False

    with patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.async_sleep",
        side_effect=_sleep_side_effect,
    ):
        caplog.clear()
        new_event_loop().run_until_complete(yamaha_yas_209._subscribe())

    assert mock_aiohttp.requests.pop(
        ("SUBSCRIBE", URL("http://192.168.1.1:49152/upnp/event/rendertransport1"))
    ) == [
        FRESH_SUBSCRIPTION_CALL,
        RESUBSCRIPTION_CALL_AV,
    ]

    assert mock_aiohttp.requests.pop(
        ("SUBSCRIBE", URL("http://192.168.1.1:49152/upnp/event/rendercontrol1"))
    ) == [FRESH_SUBSCRIPTION_CALL, FRESH_SUBSCRIPTION_CALL]

    warning_log_index = -3 if logging else -1

    assert caplog.records[warning_log_index].levelno == expected_level
    assert caplog.records[warning_log_index].message == (
        f"Still unable to subscribe to {Yas209Service.RC.service_id}: "
        f'UpnpCommunicationError("{response_exception!r}", None)'
    )

    assert call_count == 121

    if yamaha_yas_209.is_listening:  # pragma: no cover
        yamaha_yas_209.stop_listening()

        while yamaha_yas_209.is_listening:
            sleep(0.1)


def test_stop_listening_stops_listener(
    yamaha_yas_209: YamahaYas209,
    mock_aiohttp: aioresponses,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the `stop_listening` method stops the listener."""

    add_av_subscription_call(mock_aiohttp, yamaha_yas_209, repeat=True)
    add_rc_subscription_call(mock_aiohttp, yamaha_yas_209, repeat=True)

    def _worker() -> None:
        new_event_loop().run_until_complete(yamaha_yas_209._subscribe())

    caplog.clear()
    stopper_thread = Thread(target=_worker)
    stopper_thread.start()
    sleep(0.1)
    yamaha_yas_209.stop_listening()

    # These are the only real meaningful assertion; just the fact that the tests gets
    # this far is a passing scenario (i.e. the listener loop has exited)
    assert yamaha_yas_209.is_listening is False

    assert caplog.records[-1].levelno == DEBUG
    assert (
        caplog.records[-1].message
        == "Stopping event listener (will take <= 120 seconds)"
    )
