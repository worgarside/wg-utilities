"""Unit Tests for `wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.YamahaYas209`."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from http import HTTPStatus
from logging import DEBUG, INFO
from textwrap import dedent
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

from aioresponses import aioresponses
from async_upnp_client.client import UpnpService, UpnpStateVariable
from async_upnp_client.const import StateVariableInfo, StateVariableTypeInfo
from freezegun import freeze_time
from pytest import LogCaptureFixture, mark, raises

from conftest import FLAT_FILES_DIR
from wg_utilities.devices.yamaha_yas_209 import YamahaYas209
from wg_utilities.devices.yamaha_yas_209.yamaha_yas_209 import (
    CurrentTrack,
    LastChangeRenderingControl,
    Yas209Service,
    Yas209State,
)


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

    with raises(ValueError) as exc_info:
        YamahaYas209("192.168.1.1", listen_ip="192.168.1.2")

    assert (
        str(exc_info.value)
        == "Argument `listen_port` cannot be None when `listen_ip` is not None:"
        " '192.168.1.2'"
    )


def test_listen_exits_early_if_already_listening(
    yamaha_yas_209: YamahaYas209, caplog: LogCaptureFixture
) -> None:
    """Test that `listen` exits early if already `self._listening` is True."""
    yamaha_yas_209._listening = True  # pylint: disable=protected-access

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
    mock_sleep: MagicMock, yamaha_yas_209: YamahaYas209, caplog: LogCaptureFixture
) -> None:
    """Test that `listen` starts listening if `self._listening` is False."""

    async_call_count = 0

    async def _mock_async_function(self: YamahaYas209) -> None:
        """Mock async function."""
        nonlocal async_call_count

        yamaha_yas_209._listening = True  # pylint: disable=protected-access
        yamaha_yas_209._active_service_ids = [  # pylint: disable=protected-access
            v.service_id for v in Yas209Service.__members__.values()
        ]

        async_call_count += 1

        assert self == yamaha_yas_209

    with patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.YamahaYas209._subscribe",
        _mock_async_function,
    ):
        yamaha_yas_209.listen()

    # For some reason this is called way more than I'd expect: AFAICT it's only called
    # in the `while not self._listening and worker_exception is None` loop
    assert mock_sleep.call_count > 100
    assert {c.args for c in mock_sleep.call_args_list} == {(0.01,)}
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

        yamaha_yas_209._listening = True  # pylint: disable=protected-access
        yamaha_yas_209._active_service_ids = [  # pylint: disable=protected-access
            v.service_id for v in Yas209Service.__members__.values()
        ]

        call_count += 1

        assert self == yamaha_yas_209

        raise Exception("Test")

    with patch(
        "wg_utilities.devices.yamaha_yas_209.yamaha_yas_209.YamahaYas209._subscribe",
        _mock_async_function,
    ), raises(Exception) as exc_info:
        yamaha_yas_209.listen()

    assert call_count == 1

    assert str(exc_info.value) == "Test"


@patch("wg_utilities.devices.yamaha_yas_209.YamahaYas209._parse_xml_dict")
def test_on_event_wrapper_parses_xml_dicts(
    mock_parse_xml_dict: MagicMock,
    yamaha_yas_209: YamahaYas209,
    upnp_service_av_transport: UpnpService,
    upnp_state_variable: UpnpStateVariable,
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

    with raises(AttributeError) as exc_info:
        yamaha_yas_209.on_event_wrapper(
            upnp_service_av_transport, [upnp_state_variable]
        )

    assert called

    assert str(exc_info.value) == "'NoneType' object has no attribute 'copy'"
    assert (
        exc_info.traceback[2].statement.lines[0].strip() == "payload = payload.copy()"
    )


@mark.upnp_value_path(  # type: ignore[misc]
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
    upnp_state_variable: UpnpStateVariable,
) -> None:
    """Test that an AVTransport service state change updates the local state."""

    def _mock_set_state_side_effect(
        state: Yas209State, local_only: bool = False
    ) -> None:
        _ = local_only
        yamaha_yas_209._state = state  # pylint: disable=protected-access

    mock_set_state.side_effect = _mock_set_state_side_effect

    assert yamaha_yas_209.state == Yas209State.UNKNOWN
    yamaha_yas_209.on_event_wrapper(upnp_service_av_transport, [upnp_state_variable])
    assert yamaha_yas_209.state == Yas209State.PLAYING

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


@mark.upnp_value_path(  # type: ignore[misc]
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
    upnp_state_variable: UpnpStateVariable,
    current_track_null: CurrentTrack,
    mock_aiohttp: aioresponses,
) -> None:
    """Test that an AVTransport service state change updates the local state attribute.

    The `on_event_wrapper` is called a couple of times with different
    UPNPStateVariables. The `current_track` and `state` properties are checked each
    time for complete testing throughout.
    """

    with open(
        FLAT_FILES_DIR
        / "xml"
        / "yamaha_yas_209"
        / "get_media_info"
        / "nothing_playing.xml",
        "rb",
    ) as fin:
        get_media_info_response_nothing_playing = fin.read()

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

    assert yamaha_yas_209.state == Yas209State.STOPPED
    assert yamaha_yas_209.current_track == current_track_null

    with open(
        FLAT_FILES_DIR
        / "xml"
        / "yamaha_yas_209"
        / "get_media_info"
        / "different_people_spotify.xml",
        encoding="utf-8",
    ) as fin:
        mock_aiohttp.post(
            f"http://{yamaha_yas_209.ip}/upnp/control/rendertransport1",
            status=HTTPStatus.OK,
            reason=HTTPStatus.OK.phrase,
            body=fin.read(),
        )

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

    with open(
        FLAT_FILES_DIR
        / "xml"
        / "yamaha_yas_209"
        / "get_media_info"
        / "nothing_playing.xml",
        encoding="utf-8",
    ) as fin:
        mock_aiohttp.post(
            f"http://{yamaha_yas_209.ip}/upnp/control/rendertransport1",
            status=HTTPStatus.OK,
            reason=HTTPStatus.OK.phrase,
            body=fin.read(),
        )

    yamaha_yas_209.on_event_wrapper(
        upnp_service_av_transport, [new_upnp_state_variable]
    )

    assert yamaha_yas_209.state == Yas209State.STOPPED
    assert yamaha_yas_209.current_track == current_track_null


@mark.upnp_value_path(  # type: ignore[misc]
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
    upnp_state_variable: UpnpStateVariable,
    mock_aiohttp: aioresponses,
) -> None:
    """Test that an AVTransport service state change updates the local state."""

    def _mock_set_volume_level_side_effect(
        value: float, local_only: bool = False
    ) -> None:
        _ = local_only
        # pylint: disable=protected-access
        yamaha_yas_209._volume_level = round(value, 2)

    mock_set_volume_level.side_effect = _mock_set_volume_level_side_effect

    with open(
        FLAT_FILES_DIR / "xml" / "yamaha_yas_209" / "get_volume" / "50.xml",
        encoding="utf-8",
    ) as fin:
        get_volume_response = fin.read()

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


@freeze_time()  # type: ignore[misc]
def test_on_event_callback_called_correctly(
    yamaha_yas_209: YamahaYas209,
    upnp_service_rendering_control: UpnpService,
    upnp_state_variable: UpnpStateVariable,
) -> None:
    """Test that the callback is called correctly.

    Bit of a long test this one, needed some "verbose" setup -.-
    """

    payload_dir = FLAT_FILES_DIR / "xml" / "yamaha_yas_209" / "event_payloads"

    # `upnp_state_variable` is "blank", so first thing to do is make an `AVTransport`
    # copy and a `RenderingControl` copy
    upnp_state_variable_rendering_control = deepcopy(upnp_state_variable)
    upnp_state_variable_av_transport = deepcopy(upnp_state_variable)

    with open(payload_dir / "rendering_control" / "56.xml", encoding="utf-8") as fin:
        # The `RenderingControl` copy is pretty simple as the service argument is
        # RenderingControl-flavoured
        upnp_state_variable_rendering_control.upnp_value = fin.read()

    with open(
        payload_dir / "av_transport" / "payload_20220622204720404264.xml",
        encoding="utf-8",
    ) as fin:
        upnp_state_variable_av_transport.upnp_value = fin.read()
        # The `AVTransport` state variable needs to be re-written, mainly to change the
        # name from `LastChange` to something else
        # pylint: disable=protected-access
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
        # pylint: disable=protected-access
        yamaha_yas_209._parse_xml_dict(last_change_value)
        yamaha_yas_209._parse_xml_dict(something_else_value)

        assert payload == {
            # This whole test has frozen time, so we can just use `datetime.now()`
            "timestamp": datetime.now(),
            "service_id": upnp_service_rendering_control.service_id,
            "service_type": upnp_service_rendering_control.service_type,
            # The last change will be a `LastChange` instance
            "last_change": LastChangeRenderingControl.parse(last_change_value["-"]),
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
