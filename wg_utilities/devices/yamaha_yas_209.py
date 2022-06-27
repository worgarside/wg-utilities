"""This module has classes etc. for subscribing to YAS-209 updates"""
from __future__ import annotations

from asyncio import get_event_loop, new_event_loop
from asyncio import sleep as async_sleep
from copy import deepcopy
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from logging import DEBUG, getLogger
from threading import Thread
from time import sleep, strptime
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
)

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpRequester
from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.utils import get_local_ip
from mypy_extensions import Arg, KwArg, VarArg
from pydantic import BaseModel, Extra, Field  # pylint: disable=no-name-in-module
from xmltodict import parse as parse_xml

from wg_utilities.functions import traverse_dict

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


# pylint: disable=too-few-public-methods
class StateVariable(BaseModel, extra=Extra.forbid):
    """BaseModel for state variables in DLNA payload"""

    channel: str
    val: str


# pylint: disable=too-few-public-methods
class CurrentTrackMetaDataItemRes(BaseModel, extra=Extra.forbid):
    """BaseModel for part of the DLNA payload"""

    protocolInfo: str
    duration: str
    text: Optional[str]


# pylint: disable=too-few-public-methods
class TrackMetaDataItem(BaseModel, extra=Extra.forbid):
    """BaseModel for part of the DLNA payload"""

    id: str
    song_subid: Union[str, None] = Field(..., alias="song:subid")
    song_description: Union[str, None] = Field(..., alias="song:description")
    song_skiplimit: str = Field(..., alias="song:skiplimit")
    song_id: Union[str, None] = Field(..., alias="song:id")
    song_like: str = Field(..., alias="song:like")
    song_singerid: str = Field(..., alias="song:singerid")
    song_albumid: str = Field(..., alias="song:albumid")
    res: CurrentTrackMetaDataItemRes
    dc_title: Optional[str] = Field(..., alias="dc:title")
    dc_creator: Optional[str] = Field(..., alias="dc:creator")
    upnp_artist: Optional[str] = Field(..., alias="upnp:artist")
    upnp_album: Optional[str] = Field(..., alias="upnp:album")
    upnp_albumArtURI: str = Field(..., alias="upnp:albumArtURI")


# pylint: disable=too-few-public-methods
class TrackMetaData(BaseModel, extra=Extra.forbid):
    """BaseModel for part of the DLNA payload"""

    xmlns_dc: Literal["http://purl.org/dc/elements/1.1/"] = Field(..., alias="xmlns:dc")
    xmlns_upnp: Literal["urn:schemas-upnp-org:metadata-1-0/upnp/"] = Field(
        ..., alias="xmlns:upnp"
    )
    xmlns_song: Literal["www.wiimu.com/song/"] = Field(..., alias="xmlns:song")
    xmlns: Literal["urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"]
    upnp_class: Literal["object.item.audioItem.musicTrack"] = Field(
        ..., alias="upnp:class"
    )
    item: TrackMetaDataItem


class InstanceIDAVTransport(BaseModel, extra=Extra.forbid):
    """BaseModel for part of the DLNA payload"""

    val: str
    TransportState: str
    TransportStatus: Optional[str]
    NumberOfTracks: Optional[str]
    CurrentTrack: Optional[str]
    CurrentTrackDuration: Optional[str]
    CurrentMediaDuration: Optional[str]
    CurrentTrackURI: Optional[str]
    AVTransportURI: Optional[str]
    TrackSource: Optional[str]
    CurrentTrackMetaData: Optional[TrackMetaData]
    AVTransportURIMetaData: Optional[TrackMetaData]
    PlaybackStorageMedium: Optional[str]
    PossiblePlaybackStorageMedia: Optional[str]
    PossibleRecordStorageMedia: Optional[str]
    RecordStorageMedium: Optional[str]
    CurrentPlayMode: Optional[str]
    TransportPlaySpeed: Optional[str]
    RecordMediumWriteStatus: Optional[str]
    CurrentRecordQualityMode: Optional[str]
    PossibleRecordQualityModes: Optional[str]
    RelativeTimePosition: Optional[str]
    AbsoluteTimePosition: Optional[str]
    RelativeCounterPosition: Optional[str]
    AbsoluteCounterPosition: Optional[str]
    CurrentTransportActions: Optional[str]


class InstanceIDRenderingControl(BaseModel, extra=Extra.forbid):
    """BaseModel for part of the DLNA payload"""

    val: str
    Mute: StateVariable
    Channel: Optional[StateVariable]
    Equaluzer: Optional[StateVariable]  # There's a typo in the schema, this is correct
    Volume: StateVariable
    PresetNameList: Optional[str]
    TimeStamp: Optional[str]


class EventAVTransport(BaseModel, extra=Extra.forbid):
    """BaseModel for part of the DLNA payload"""

    xmlns: Literal["urn:schemas-upnp-org:metadata-1-0/AVT/"]
    InstanceID: InstanceIDAVTransport


class EventRenderingControl(BaseModel, extra=Extra.forbid):
    """BaseModel for part of the DLNA payload"""

    xmlns: Literal["urn:schemas-upnp-org:metadata-1-0/RCS/"]
    InstanceID: InstanceIDRenderingControl


class LastChange(BaseModel, extra=Extra.forbid):
    """BaseModel for the DLNA payload"""

    Event: Any

    @classmethod
    def parse(cls, payload: Dict[Literal["Event"], Any]) -> LastChange:
        """Parse a `LastChange` model from the payload dictionary.

        Args:
            payload (Dict[str, Any]): the DLNA DMR payload

        Raises:
            ValidationError: If any of the specified model fields are empty or of the
             wrong type.
            ValueError: if more than just "Event" is in the payload

        Returns:
            LastChange: The parsed `Case`.
        """

        event = payload.pop("Event")

        if len(payload) > 0:
            raise ValueError(
                f"""Unexpected keys in payload: '{"', '".join(payload.keys())}'"""
            )

        return cls(Event=event)


class LastChangeAVTransport(LastChange):
    """BaseModel for an AVTransport DLNA payload"""

    Event: EventAVTransport


class LastChangeRenderingControl(LastChange):
    """BaseModel for a RenderingControl DLNA payload"""

    Event: EventRenderingControl


LastChangeTypeVar = TypeVar("LastChangeTypeVar", bound=LastChange)


class CurrentTrack:
    """Class for easy processing/passing of track metadata

    Attributes:
        album_art_uri (str): URL for album artwork
        media_album_name (str): album name
        media_artist (str): track's artist(s)
        media_title (str): track's title
    """

    DURATION_FORMAT = "%H:%M:%S.%f"

    class Info(TypedDict):
        """Info for the attributes of this class"""

        album_art_uri: str
        media_album_name: str
        media_artist: str
        media_duration: float
        media_title: str

    def __init__(
        self,
        *,
        album_art_uri: str,
        media_album_name: str,
        media_artist: str,
        media_duration: float,
        media_title: str,
    ):
        self.album_art_uri = album_art_uri
        self.media_album_name = media_album_name
        self.media_artist = media_artist
        self.media_duration = media_duration
        self.media_title = media_title

    @classmethod
    def from_last_change(cls, last_change: LastChangeTypeVar) -> CurrentTrack:
        """
        Args:
            last_change (LastChangeAVTransport): the payload from the last DLNA change

        Returns:
            CurrentTrack: a CurrentTrack instance with relevant info
        """
        item = last_change.Event.InstanceID.CurrentTrackMetaData.item

        duration_time = strptime(item.res.duration, cls.DURATION_FORMAT)

        duration_delta = timedelta(
            hours=duration_time.tm_hour,
            minutes=duration_time.tm_min,
            seconds=duration_time.tm_sec,
        )

        return CurrentTrack(
            album_art_uri=item.upnp_albumArtURI,
            media_album_name=item.upnp_album,
            media_artist=item.dc_creator,
            media_duration=duration_delta.total_seconds(),
            media_title=item.dc_title,
        )

    @property
    def json(self) -> CurrentTrack.Info:
        """
        Returns:
            CurrentTrack.Info: info on the currently playing track
        """
        return {
            "album_art_uri": self.album_art_uri,
            "media_album_name": self.media_album_name,
            "media_artist": self.media_artist,
            "media_duration": self.media_duration,
            "media_title": self.media_title,
        }


class Yas209State(Enum):
    """Enumeration for states as they come in the DLNA payload"""

    PLAYING = "playing"
    PAUSED_PLAYBACK = "paused"
    STOPPED = "off"
    NO_MEDIA_PRESENT = "idle"
    UNKNOWN = "unknown"


class Yas209Service(Enum):
    """Enumeration for available YAS-209 services"""

    AVT = "urn:schemas-upnp-org:service:AVTransport:1", (
        "GetCurrentTransportActions",
        "GetDeviceCapabilities",
        "GetInfoEx",
        "GetMediaInfo",
        "GetPlayType",
        "GetPositionInfo",
        "GetTransportInfo",
        "GetTransportSettings",
        "Next",
        "Pause",
        "Play",
        "Previous",
        "Seek",
        "SeekBackward",
        "SeekForward",
        "SetAVTransportURI",
        "SetPlayMode",
        "Stop",
    )
    CM = "urn:schemas-upnp-org:service:ConnectionManager:1", (
        "GetCurrentConnectionIDs",
        "GetCurrentConnectionInfo",
        "GetProtocolInfo",
    )
    PQ = "urn:schemas-wiimu-com:service:PlayQueue:1", (
        "AppendQueue",
        "AppendTracksInQueue",
        "AppendTracksInQueueEx",
        "BackUpQueue",
        "BrowseQueue",
        "CreateQueue",
        "DeleteActionQueue",
        "DeleteQueue",
        "GetKeyMapping",
        "GetQueueIndex",
        "GetQueueLoopMode",
        "GetQueueOnline",
        "GetUserAccountHistory",
        "GetUserFavorites",
        "GetUserInfo",
        "PlayQueueWithIndex",
        "RemoveTracksInQueue",
        "ReplaceQueue",
        "SearchQueueOnline",
        "SetKeyMapping",
        "SetQueueLoopMode",
        "SetQueuePolicy",
        "SetQueueRecord",
        "SetSongsRecord",
        "SetSpotifyPreset",
        "SetUserFavorites",
        "UserLogin",
        "UserLogout",
        "UserRegister",
    )
    Q_PLAY = "urn:schemas-tencent-com:service:QPlay:1", (
        "GetMaxTracks",
        "GetTracksCount",
        "GetTracksInfo",
        "InsertTracks",
        "QPlayAuth",
        "RemoveAllTracks",
        "RemoveTracks",
        "SetNetwork",
        "SetTracksInfo",
    )
    RC = "urn:schemas-upnp-org:service:RenderingControl:1", (
        "DeleteAlarmQueue",
        "GetAlarmQueue",
        "GetChannel",
        "GetControlDeviceInfo",
        "GetEqualizer",
        "GetMute",
        "GetSimpleDeviceInfo",
        "GetVolume",
        "ListPresets",
        "MultiPlaySlaveMask",
        "SelectPreset",
        "SetAlarmQueue",
        "SetChannel",
        "SetDeviceName",
        "SetEqualizer",
        "SetMute",
        "SetVolume",
        "StreamServicesCapability",
    )

    def __init__(self, value: str, actions: Tuple[str]):
        self._value_ = value
        self.actions = actions


def needs_device(
    func: Callable[[YamahaYas209], Coroutine[Any, Any, None]]
) -> Callable[
    [Arg(YamahaYas209, "yas_209"), VarArg(Tuple[Any]), KwArg(Dict[str, Any])], Any
]:
    """This decorator is used when the DLNA device is needed and provides a clean way
     of instantiating it lazily

    Args:
        func (Callable): the function being wrapped

    Returns:
        Callable: the inner function
    """

    @wraps(func)
    def create_device(yas_209: YamahaYas209, *args: Any, **kwargs: Any) -> Any:
        """Inner function for creating the device before executing the wrapped function

        Args:
            yas_209 (YamahaYas209): the YamahaYas209 instance
            *args (Any): positional arguments
            **kwargs (Any): keyword arguments

        Returns:
            Any: the result of the wrapped function
        """
        if not hasattr(yas_209, "device"):
            requester = AiohttpRequester()
            factory = UpnpFactory(requester)

            async def _create() -> None:
                yas_209.device = await factory.async_create_device(
                    yas_209.description_url
                )

            # Listener loop can't be running without a device so this is fine to use
            new_event_loop().run_until_complete(_create())

        return func(yas_209, *args, **kwargs)

    return create_device


class YamahaYas209:
    """Class for consuming information from a YAS-209n in real time"""

    SUBSCRIPTION_SERVICES = {"AVTransport", "RenderingControl"}

    LAST_CHANGE_PAYLOAD_PARSERS = {
        "urn:upnp-org:serviceId:AVTransport": LastChangeAVTransport.parse,
        "urn:upnp-org:serviceId:RenderingControl": LastChangeRenderingControl.parse,
    }

    class EventPayloadInfo(TypedDict):
        """Info for the payload sent to the `on_event` callback"""

        timestamp: datetime
        service_id: str
        service_type: str
        last_change: LastChange
        other_xml_payloads: Dict[str, Any]

    def __init__(
        self,
        ip: str,
        *,
        on_event: Optional[Callable[[EventPayloadInfo], None]] = None,
        start_listener: bool = False,
        on_volume_update: Optional[Callable[[float], None]] = None,
        on_track_update: Optional[Callable[[CurrentTrack.Info], None]] = None,
        on_state_update: Optional[Callable[[str], None]] = None,
    ):
        self.ip = ip
        self.on_event = on_event

        # noinspection HttpUrlsUsage
        self.description_url = f"http://{ip}:49152/description.xml"

        self.on_volume_update = on_volume_update
        self.on_track_update = on_track_update
        self.on_state_update = on_state_update

        self._current_track: CurrentTrack
        self._state: Yas209State
        self._volume_level: float

        self._listener_thread: Thread
        self._listening = False

        self.device: UpnpDevice

        if start_listener:
            self.listen()

    def listen(self, blocking: bool = False) -> None:
        """Start the listener"""
        if blocking:
            get_event_loop().run_until_complete(self._subscribe())
        else:

            def _worker() -> None:
                loop = new_event_loop()
                loop.run_until_complete(self._subscribe())

            self._listener_thread = Thread(target=_worker)
            self._listener_thread.start()

    def on_event_wrapper(
        self, service: UpnpService, service_variables: Sequence[UpnpStateVariable[str]]
    ) -> None:
        """Wrapper function for the `on_event` callback, so that we can process the
        XML payload(s) first

        Args:
            service (UpnpService): the service which has sent an update
            service_variables (list): a list of state variables that have updated
        """

        xml_payloads: Dict[str, Union[str, Dict[str, Any], None]] = {
            sv.name: sv.value for sv in service_variables
        }

        # Convert any nested XML into JSON
        traverse_dict(
            xml_payloads,
            target_type=str,
            target_processor_func=lambda value: parse_xml(
                value, attr_prefix="", cdata_key="text"
            ),
            single_keys_to_remove=["val", "DIDL-Lite"],
        )

        last_change = self.LAST_CHANGE_PAYLOAD_PARSERS[service.service_id](
            xml_payloads.pop("LastChange")  # type: ignore[arg-type]
        )

        event_payload: YamahaYas209.EventPayloadInfo = {
            "timestamp": datetime.now(),
            "service_id": service.service_id,
            "service_type": service.service_type,
            "last_change": last_change,
            "other_xml_payloads": xml_payloads,
        }

        if event_payload["last_change"] is None:
            return

        if service.service_id == "urn:upnp-org:serviceId:AVTransport":
            if last_change.Event.InstanceID.TransportState != self.state.name:
                self.state = last_change.Event.InstanceID.TransportState
            if last_change.Event.InstanceID.CurrentTrackMetaData is not None:
                self.current_track = CurrentTrack.from_last_change(last_change)
        elif service.service_id == "urn:upnp-org:serviceId:RenderingControl":
            # The DLNA payload has volume as a string value between 0 and 100
            self.volume_level = float(last_change.Event.InstanceID.Volume.val) / 100

        if self.on_event is not None:
            self.on_event(event_payload)

    @needs_device
    async def _subscribe(self) -> None:
        """Subscribe to service(s) and output updates."""

        # start notify server/event handler
        source = (get_local_ip(self.device.device_url), 0)
        server = AiohttpNotifyServer(self.device.requester, source=source)
        await server.async_start_server()
        event_handler = server.event_handler

        # create service subscriptions
        services = []
        failed_subscriptions = []
        for service_name in self.device.services.keys():
            if not self.SUBSCRIPTION_SERVICES & set(service_name.split(":")):
                continue

            service = next(
                service
                for service in self.device.all_services
                if service_name == service.service_type
            )
            service.on_event = self.on_event_wrapper
            services.append(service)
            try:
                await event_handler.async_subscribe(service)
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception(
                    "Unable to subscribe to %s: %s - %s",
                    service_name,
                    type(exc).__name__,
                    str(exc),
                )
                failed_subscriptions.append(service)

        self._listening = True

        # keep the webservice running (force resubscribe)
        while self._listening:
            for _ in range(24):
                if self._listening is False:
                    return
                await async_sleep(5)
            await event_handler.async_resubscribe_all()

            for service in deepcopy(failed_subscriptions):
                try:
                    LOGGER.debug(
                        "Attempting to create subscription for %s", service.service_id
                    )
                    await event_handler.async_subscribe(service)
                    failed_subscriptions.remove(service)
                except Exception as exc:  # pylint: disable=broad-except
                    LOGGER.exception(
                        "Still unable to subscribe to %s: %s - %s",
                        service,
                        type(exc).__name__,
                        str(exc),
                    )

    def _call_service_action(
        self,
        service: Yas209Service,
        action: str,
        callback: Optional[Callable[[Mapping[str, Any]], Any]] = None,
        **call_kwargs: Union[str, int],
    ) -> None:
        @needs_device
        async def _worker(_self: YamahaYas209) -> None:
            res = (
                await _self.device.services[service.value]
                .action(action)
                .async_call(**call_kwargs)
            )

            if callback is not None:
                callback(res)

        if action not in service.actions:
            raise ValueError(
                f"Unknown action {action!r}, must be one of:"
                f" {', '.join(service.actions)}"
            )

        get_event_loop().run_until_complete(_worker(self))

    def pause(self) -> None:
        """Pause the current media"""
        self._call_service_action(Yas209Service.AVT, "Pause", InstanceID=0)

    def play(self) -> None:
        """Play the current media"""
        self._call_service_action(Yas209Service.AVT, "Play", InstanceID=0, Speed="1")

    def play_pause(self) -> None:
        """Toggle the playing/paused state"""
        if self.state == Yas209State.PAUSED_PLAYBACK:
            self.play()
        else:
            self.pause()

    def mute(self) -> None:
        """Mute"""
        self._call_service_action(
            Yas209Service.RC,
            "SetMute",
            InstanceID=0,
            Channel="Master",
            DesiredMute=True,
        )

    def next_track(self) -> None:
        """Skip to the next track"""
        self._call_service_action(Yas209Service.AVT, "Next", InstanceID=0)

    def previous_track(self) -> None:
        """Go to the previous track"""
        self._call_service_action(Yas209Service.AVT, "Previous", InstanceID=0)

    def stop_listening(self) -> None:
        """Stop the event listener"""
        self._listening = False

    def unmute(self) -> None:
        """Unmute"""
        self._call_service_action(
            Yas209Service.RC,
            "SetMute",
            InstanceID=0,
            Channel="Master",
            DesiredMute=False,
        )

    def volume_down(self) -> None:
        """Decrease the volume by 2 points"""
        self._call_service_action(
            Yas209Service.RC,
            "SetVolume",
            InstanceID=0,
            Channel="Master",
            DesiredVolume=int((100 * self.volume_level) - 2),
        )

    def volume_up(self) -> None:
        """Increase the volume by 2 points"""
        self._call_service_action(
            Yas209Service.RC,
            "SetVolume",
            InstanceID=0,
            Channel="Master",
            DesiredVolume=int((100 * self.volume_level) + 2),
        )

    @property
    def album_art_uri(self) -> Union[str, None]:
        """
        Returns:
            str: URL for the current album's artwork
        """
        if hasattr(self, "_current_track"):
            return self._current_track.album_art_uri

        return None

    @property
    def current_track(self) -> Union[CurrentTrack, None]:
        """
        Returns:
            dict: the current track's info
        """
        if hasattr(self, "_current_track"):
            return self._current_track

        return None

    @current_track.setter
    def current_track(self, value: CurrentTrack) -> None:
        self._current_track = value

        if self.on_track_update is not None:
            self.on_track_update(value.json)

    @property
    def media_album_name(self) -> Union[str, None]:
        """
        Returns:
            str: the current media_title
        """
        if hasattr(self, "_current_track"):
            return self._current_track.media_album_name

        return None

    @property
    def media_artist(self) -> Union[str, None]:
        """
        Returns:
            str: the current media_artist
        """
        if hasattr(self, "_current_track"):
            return self._current_track.media_artist

        return None

    @property
    def media_title(self) -> Union[str, None]:
        """
        Returns:
            str: the current media_album_name
        """
        if hasattr(self, "_current_track"):
            return self._current_track.media_title

        return None

    @property
    def state(self) -> Yas209State:
        """
        Returns:
            Yas209State: the current state of the YAS-209 (e.g. playing, stopped)
        """
        if hasattr(self, "_state"):
            return self._state

        return Yas209State.UNKNOWN

    @state.setter
    def state(self, value: str) -> None:
        self._state = Yas209State[value]

        if self.on_state_update is not None:
            self.on_state_update(self._state.value)

    @property
    def volume_level(self) -> float:
        """
        Returns:
            float: the current volume level
        """
        if not hasattr(self, "_volume_level"):

            def _set_volume_attr(response: Mapping[str, int]) -> None:
                self._volume_level = response["CurrentVolume"] / 100

            self._call_service_action(
                Yas209Service.RC,
                "GetVolume",
                InstanceID=0,
                Channel="Master",
                callback=_set_volume_attr,
            )

        while not hasattr(self, "_volume_level"):
            sleep(0.1)

        return float(self._volume_level)

    @volume_level.setter
    def volume_level(self, value: float) -> None:
        self._volume_level = value

        self._call_service_action(
            Yas209Service.RC,
            "SetVolume",
            InstanceID=0,
            Channel="Master",
            DesiredVolume=int(self._volume_level * 100),
        )

        if self.on_volume_update is not None:
            self.on_volume_update(self._volume_level)
