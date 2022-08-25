"""This module has classes etc. for subscribing to YAS-209 updates"""
from __future__ import annotations

from asyncio import new_event_loop, run
from asyncio import sleep as async_sleep
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from logging import DEBUG, getLogger
from textwrap import dedent
from threading import Thread
from time import sleep, strptime
from typing import (
    Any,
    Callable,
    Coroutine,
    Literal,
    Mapping,
    Sequence,
    TypedDict,
    TypeVar,
)

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpRequester
from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpActionResponseError, UpnpResponseError
from async_upnp_client.utils import get_local_ip
from pydantic import BaseModel, Extra, Field
from xmltodict import parse as parse_xml

from wg_utilities.functions import traverse_dict
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


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
    text: str | None


# pylint: disable=too-few-public-methods
class TrackMetaDataItem(BaseModel, extra=Extra.forbid):
    """BaseModel for part of the DLNA payload"""

    id: str
    song_subid: str | None = Field(..., alias="song:subid")
    song_description: str | None = Field(..., alias="song:description")
    song_skiplimit: str = Field(..., alias="song:skiplimit")
    song_id: str | None = Field(..., alias="song:id")
    song_like: str = Field(..., alias="song:like")
    song_singerid: str = Field(..., alias="song:singerid")
    song_albumid: str = Field(..., alias="song:albumid")
    res: CurrentTrackMetaDataItemRes
    dc_title: str | None = Field(..., alias="dc:title")
    dc_creator: str | None = Field(..., alias="dc:creator")
    upnp_artist: str | None = Field(..., alias="upnp:artist")
    upnp_album: str | None = Field(..., alias="upnp:album")
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
    TransportStatus: str | None
    NumberOfTracks: str | None
    CurrentTrack: str | None
    CurrentTrackDuration: str | None
    CurrentMediaDuration: str | None
    CurrentTrackURI: str | None
    AVTransportURI: str | None
    TrackSource: str | None
    CurrentTrackMetaData: TrackMetaData | None
    AVTransportURIMetaData: TrackMetaData | None
    PlaybackStorageMedium: str | None
    PossiblePlaybackStorageMedia: str | None
    PossibleRecordStorageMedia: str | None
    RecordStorageMedium: str | None
    CurrentPlayMode: str | None
    TransportPlaySpeed: str | None
    RecordMediumWriteStatus: str | None
    CurrentRecordQualityMode: str | None
    PossibleRecordQualityModes: str | None
    RelativeTimePosition: str | None
    AbsoluteTimePosition: str | None
    RelativeCounterPosition: str | None
    AbsoluteCounterPosition: str | None
    CurrentTransportActions: str | None


class InstanceIDRenderingControl(BaseModel, extra=Extra.forbid):
    """BaseModel for part of the DLNA payload"""

    val: str
    Mute: StateVariable
    Channel: StateVariable | None
    Equalizer: StateVariable | None
    # There's a typo in the schema, this is correct for some payloads -.-
    Equaluzer: StateVariable | None
    Volume: StateVariable
    PresetNameList: str | None
    TimeStamp: str | None


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
    def parse(cls, payload: dict[Literal["Event"], Any]) -> LastChange:
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


class GetMediaInfoResponse(BaseModel):
    """BaseModel for the response from a GetMediaInfo request"""

    NrTracks: int
    MediaDuration: str
    CurrentURI: str
    CurrentURIMetaData: TrackMetaData
    NextURI: str
    NextURIMetaData: str
    TrackSource: str
    PlayMedium: str
    RecordMedium: str
    WriteStatus: str


class CurrentTrack:
    """Class for easy processing/passing of track metadata

    Attributes:
        album_art_uri (str): URL for album artwork
        media_album_name (str): album name
        media_artist (str): track's artist(s)
        media_title (str): track's title
    """

    DURATION_FORMAT = "%H:%M:%S.%f"

    NULL_TRACK_STR = "NULL"

    class Info(TypedDict):
        """Info for the attributes of this class"""

        album_art_uri: str | None
        media_album_name: str | None
        media_artist: str | None
        media_duration: float
        media_title: str | None

    def __init__(
        self,
        *,
        album_art_uri: str | None,
        media_album_name: str | None,
        media_artist: str | None,
        media_duration: float,
        media_title: str | None,
    ):
        self.album_art_uri = album_art_uri
        self.media_album_name = media_album_name
        self.media_artist = media_artist
        self.media_duration = media_duration
        self.media_title = media_title

    @classmethod
    def _create_from_metadata_item(
        cls, metadata_item: TrackMetaDataItem
    ) -> CurrentTrack:
        """Create a CurrentTrack instance from a response metadata item

        Args:
            metadata_item (TrackMetaDataItem): the metadata pulled from the response

        Returns:
            CurrentTrack: instance containing relevant info
        """
        duration_time = strptime(metadata_item.res.duration, cls.DURATION_FORMAT)

        duration_delta = timedelta(
            hours=duration_time.tm_hour,
            minutes=duration_time.tm_min,
            seconds=duration_time.tm_sec,
        )

        return CurrentTrack(
            album_art_uri=metadata_item.upnp_albumArtURI
            if metadata_item.upnp_albumArtURI != "un_known"
            else None,
            media_album_name=metadata_item.upnp_album,
            media_artist=metadata_item.dc_creator,
            media_duration=duration_delta.total_seconds(),
            media_title=metadata_item.dc_title,
        )

    @classmethod
    def from_get_media_info(cls, response: GetMediaInfoResponse) -> CurrentTrack:
        """
        Args:
            response (GetMediaInfoResponse): the response from a GetMediaInfo request

        Returns:
            CurrentTrack: a CurrentTrack instance with relevant info
        """
        return cls._create_from_metadata_item(response.CurrentURIMetaData.item)

    @classmethod
    def from_last_change(cls, last_change: LastChangeTypeVar) -> CurrentTrack:
        """
        Args:
            last_change (LastChangeAVTransport): the payload from the last DLNA change

        Returns:
            CurrentTrack: a CurrentTrack instance with relevant info
        """
        return cls._create_from_metadata_item(
            last_change.Event.InstanceID.CurrentTrackMetaData.item
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

    def __str__(self) -> str:
        if self.media_title is None and self.media_artist is None:
            return self.NULL_TRACK_STR

        return f"{self.media_title!r} by {self.media_artist}"


class Yas209State(Enum):
    """Enumeration for states as they come in the DLNA payload"""

    PLAYING = "playing", "Play"
    PAUSED_PLAYBACK = "paused", "Pause"
    STOPPED = "off", "Stop"
    NO_MEDIA_PRESENT = "idle", None
    UNKNOWN = "unknown", None

    def __init__(self, value: str, action: str | None):
        self._value_ = value
        self.action = action


class Yas209Service(Enum):
    """Enumeration for available YAS-209 services"""

    AVT = (
        "AVTransport",
        "urn:upnp-org:serviceId:AVTransport",
        "urn:schemas-upnp-org:service:AVTransport:1",
        (
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
        ),
    )
    CM = (
        "ConnectionManager",
        "urn:upnp-org:serviceId:ConnectionManager",
        "urn:schemas-upnp-org:service:ConnectionManager:1",
        (
            "GetCurrentConnectionIDs",
            "GetCurrentConnectionInfo",
            "GetProtocolInfo",
        ),
    )
    PQ = (
        "PlayQueue",
        "urn:wiimu-com:serviceId:PlayQueue",
        "urn:schemas-wiimu-com:service:PlayQueue:1",
        (
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
        ),
    )
    Q_PLAY = (
        "QPlay",
        "urn:tencent-com:serviceId:QPlay",
        "urn:schemas-tencent-com:service:QPlay:1",
        (
            "GetMaxTracks",
            "GetTracksCount",
            "GetTracksInfo",
            "InsertTracks",
            "QPlayAuth",
            "RemoveAllTracks",
            "RemoveTracks",
            "SetNetwork",
            "SetTracksInfo",
        ),
    )
    RC = (
        "RenderingControl",
        "urn:upnp-org:serviceId:RenderingControl",
        "urn:schemas-upnp-org:service:RenderingControl:1",
        (
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
        ),
    )

    def __init__(
        self, value: str, service_id: str, service_name: str, actions: tuple[str]
    ):
        self._value_ = value
        self.service_id = service_id
        self.service_name = service_name
        self.actions = actions


def _needs_device(
    func: Callable[[YamahaYas209], Coroutine[Any, Any, Mapping[str, Any] | None]]
) -> Callable[[YamahaYas209], Any]:
    """This decorator is used when the DLNA device is needed and provides a clean
     way of instantiating it lazily

    Args:
        func (Callable): the function being wrapped

    Returns:
        Callable: the inner function
    """

    @wraps(func)
    def create_device(yas_209: YamahaYas209) -> Any:
        """Inner function for creating the device before executing the wrapped
         method

        Args:
            yas_209 (YamahaYas209): the YamahaYas209 instance

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

            run(_create())

        return func(yas_209)

    return create_device


class YamahaYas209:
    """Class for consuming information from a YAS-209 in real time"""

    SUBSCRIPTION_SERVICES = (
        Yas209Service.AVT.service_id,
        Yas209Service.RC.service_id,
    )

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
        other_xml_payloads: dict[str, Any]

    def __init__(
        self,
        ip: str,
        *,
        on_event: Callable[[EventPayloadInfo], None] | None = None,
        start_listener: bool = False,
        on_volume_update: Callable[[float], None] | None = None,
        on_track_update: Callable[[CurrentTrack.Info], None] | None = None,
        on_state_update: Callable[[str], None] | None = None,
        logging: bool = True,
        listen_ip: str | None = None,
        listen_port: int | None = None,
        source_port: int | None = None,
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

        self._listening = False

        self.device: UpnpDevice

        self._logging = logging
        self._listen_ip = listen_ip
        self._listen_port = listen_port
        self._source_port = source_port or 0

        self._active_service_ids: list[str] = []

        if self._listen_ip is not None and self._listen_port is None:
            raise TypeError(
                "Argument `listen_port` cannot be None when `listen_ip` is not None:"
                f" {self._listen_ip!r}"
            )

        if start_listener:
            self.listen()

    def listen(self) -> None:
        """Start the listener"""

        if self._logging:
            LOGGER.info("Starting listener")

        if self._listening:
            if self._logging:
                LOGGER.debug(
                    "Already listening to '%s', returning immediately",
                    "', '".join(self._active_service_ids),
                )
            return

        worker_exception: Exception | None = None

        def _worker() -> None:
            nonlocal worker_exception
            try:
                new_event_loop().run_until_complete(self._subscribe())
            except Exception as exc:  # pylint: disable=broad-except
                worker_exception = exc

        listener_thread = Thread(target=_worker)
        listener_thread.start()

        while not self._listening and worker_exception is None:
            sleep(0.01)

        if worker_exception is not None:
            raise worker_exception  # pylint: disable=raising-bad-type

        if self._logging:
            LOGGER.debug(
                "Listen action complete, now subscribed to '%s'",
                "', '".join(self._active_service_ids),
            )

    def on_event_wrapper(
        self, service: UpnpService, service_variables: Sequence[UpnpStateVariable[str]]
    ) -> None:
        """Wrapper function for the `on_event` callback, so that we can process the
        XML payload(s) first

        Args:
            service (UpnpService): the service which has sent an update
            service_variables (list): a list of state variables that have updated
        """

        xml_payloads: dict[str, str | dict[str, Any] | None] = {
            sv.name: sv.value for sv in service_variables
        }

        # Convert any nested XML into JSON
        self._parse_xml_dict(xml_payloads)

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
                self.set_state(
                    Yas209State[last_change.Event.InstanceID.TransportState],
                    local_only=True,
                )
            if last_change.Event.InstanceID.CurrentTrackMetaData is not None:
                self.current_track = CurrentTrack.from_last_change(last_change)
        elif service.service_id == "urn:upnp-org:serviceId:RenderingControl":
            # The DLNA payload has volume as a string value between 0 and 100
            self.set_volume_level(
                float(last_change.Event.InstanceID.Volume.val) / 100, local_only=True
            )

        if self.on_event is not None:
            self.on_event(event_payload)

    # noinspection PyArgumentList
    @_needs_device
    async def _subscribe(self) -> None:
        # pylint: disable=too-many-branches
        """Subscribe to service(s) and output updates."""

        # start notify server/event handler
        local_ip = get_local_ip(self.device.device_url)
        source = (local_ip, self._source_port)

        callback_url = (
            None
            if self._listen_port is None
            else f"http://{self._listen_ip or local_ip}:{self._listen_port}/notify"
        )
        server = AiohttpNotifyServer(
            self.device.requester, source=source, callback_url=callback_url
        )
        await server.async_start_server()

        if self._logging:
            LOGGER.debug(
                dedent(
                    """
            Listen IP:          %s
            Listen Port:        %s
            Source IP:          %s
            Source Port:        %s
            Callback URL:       %s
            Server Listen IP:   %s
            Server Listen Port: %s
            """
                ),
                self._listen_ip,
                str(self._listen_port),
                local_ip,
                str(self._source_port),
                str(callback_url),
                server.listen_ip,
                server.listen_port,
            )

        # create service subscriptions
        services = []
        failed_subscriptions = []
        for service in self.device.services.values():
            if service.service_id not in self.SUBSCRIPTION_SERVICES:
                continue

            service.on_event = self.on_event_wrapper
            services.append(service)
            try:
                await server.event_handler.async_subscribe(service)
                self._active_service_ids.append(service.service_id)
                LOGGER.debug("Subscribed to %s", service.service_id)
            except UpnpResponseError as exc:
                if self._logging:
                    LOGGER.exception(
                        "Unable to subscribe to %s: %s - %s",
                        service.service_id,
                        type(exc).__name__,
                        str(exc),
                    )
                failed_subscriptions.append(service)

        self._listening = True

        # keep the webservice running (force resubscribe)
        while self._listening:
            for _ in range(120):
                if self._listening is False:
                    if self._logging:
                        LOGGER.debug("Exiting listener loop")
                    return
                await async_sleep(1)

            LOGGER.debug("Resubscribing to all services")
            await server.event_handler.async_resubscribe_all()

            services_to_remove = []
            for service in failed_subscriptions:
                try:
                    if self._logging:
                        LOGGER.debug(
                            "Attempting to create originally failed subscription for"
                            " %s",
                            service.service_id,
                        )
                    await server.event_handler.async_subscribe(service)
                    self._active_service_ids.append(service.service_id)
                    services_to_remove.append(service)
                except UpnpResponseError as exc:
                    log_message = (
                        f"Still unable to subscribe to {service.service_id}:"
                        f" {exc!r}"
                    )

                    if self._logging:
                        LOGGER.exception(log_message)
                    else:
                        # Should still log this exception, regardless
                        LOGGER.warning(log_message)

            # This needs to be separate because `.remove` is the cleanest way to remove
            # the items, but can't be done within the loop, and I can't `deepcopy`
            # `failed_subscriptions` and it's threaded content
            for service in services_to_remove:
                failed_subscriptions.remove(service)

        if self._logging:
            LOGGER.debug(
                "Exiting subscription loop, `self._listening` is `%s`", self._listening
            )

    def _call_service_action(
        self,
        service: Yas209Service,
        action: str,
        callback: Callable[[Mapping[str, Any]], Any] | None = None,
        **call_kwargs: str | int,
    ) -> dict[str, Any] | None:

        if action not in service.actions:
            raise ValueError(
                f"Unexpected action {action!r} for service {service.value!r}. "
                f"""Must be one of {"', '".join(service.actions)!r}"""
            )

        @_needs_device
        async def _worker(_: YamahaYas209) -> Mapping[str, Any]:
            res: Mapping[str, Any] = (
                await self.device.services[service.service_name]
                .action(action)
                .async_call(**call_kwargs)
            )

            if callback is not None:
                callback(res)

            return res

        if action not in service.actions:
            raise ValueError(
                f"Unknown action {action!r}, must be one of:"
                f" {', '.join(service.actions)}"
            )
        try:
            return run(_worker(self))  # type: ignore[no-any-return]
        except UpnpActionResponseError:
            # if not trying to transition to the current state (and current state is
            # known)
            if self.state != Yas209State.UNKNOWN and self.state.action != action:
                raise

            return None

    @staticmethod
    def _parse_xml_dict(xml_dict: dict[str, Any]) -> None:
        """Parse a dictionary where some values are/could be XML strings, and unpack
        the XML into JSON within the dict

        Args:
            xml_dict (dict): the dictionary to parse
        """
        traverse_dict(
            xml_dict,
            target_type=str,
            target_processor_func=lambda value: parse_xml(
                value, attr_prefix="", cdata_key="text"
            ),
            single_keys_to_remove=["val", "DIDL-Lite"],
        )

    def pause(self) -> None:
        """Pause the current media"""
        self._call_service_action(Yas209Service.AVT, "Pause", InstanceID=0)

    def play(self) -> None:
        """Play the current media"""
        self._call_service_action(Yas209Service.AVT, "Play", InstanceID=0, Speed="1")

    def play_pause(self) -> None:
        """Toggle the playing/paused state"""
        if self.state == Yas209State.PLAYING:
            self.pause()
        else:
            self.play()

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

    def set_state(self, value: Yas209State, local_only: bool = False) -> None:
        """Sets the state to the given value

        Args:
            value (Yas209State): the new state of the YAS-209
            local_only (bool): only change the local value of the state (i.e. don't
             update the soundbar)
        """
        self._state = value

        if not local_only:
            func = {
                Yas209State.PLAYING: self.play,
                Yas209State.PAUSED_PLAYBACK: self.pause,
                Yas209State.STOPPED: self.stop,
            }.get(value)

            if func is not None:
                func()

        if self.on_state_update is not None:
            self.on_state_update(self._state.value)

    def set_volume_level(self, value: float, local_only: bool = False) -> None:
        """Set's the soundbar's volume level

        Args:
            value (float): the new volume level, as a float between 0 and 1
            local_only (bool): only change the local value of the volume level (i.e.
             don't update the soundbar)
        """
        self._volume_level = round(value, 2)

        if not local_only:
            self._call_service_action(
                Yas209Service.RC,
                "SetVolume",
                InstanceID=0,
                Channel="Master",
                DesiredVolume=int(self._volume_level * 100),
            )

        if self.on_volume_update is not None:
            self.on_volume_update(self._volume_level)

    def stop(self) -> None:
        """Stop whatever is currently playing"""
        self._call_service_action(Yas209Service.AVT, "Stop", InstanceID=0, Speed="1")

    def stop_listening(self) -> None:
        """Stop the event listener"""
        if self._logging:
            LOGGER.debug("Stopping event listener (will take <= 2 minutes)")

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
        self.set_volume_level(self.volume_level - 0.02)

    def volume_up(self) -> None:
        """Increase the volume by 2 points"""
        self.set_volume_level(self.volume_level + 0.02)

    @property
    def album_art_uri(self) -> str | None:
        """
        Returns:
            str: URL for the current album's artwork
        """
        if self.current_track is not None:
            return self._current_track.album_art_uri

        return None

    @property
    def current_track(self) -> CurrentTrack | None:
        """
        Returns:
            dict: the current track's info
        """
        if not hasattr(self, "_current_track"):
            media_info = self.get_media_info()
            self._parse_xml_dict(media_info)
            self._current_track = CurrentTrack.from_get_media_info(
                GetMediaInfoResponse.parse_obj(media_info)
            )

        return self._current_track

    @current_track.setter
    def current_track(self, value: CurrentTrack) -> None:
        self._current_track = value

        if self.on_track_update is not None:
            self.on_track_update(value.json)

    @property
    def media_album_name(self) -> str | None:
        """
        Returns:
            str: the current media_title
        """
        if self.current_track is not None:
            return self._current_track.media_album_name

        return None

    @property
    def media_artist(self) -> str | None:
        """
        Returns:
            str: the current media_artist
        """
        if self.current_track is not None:
            return self._current_track.media_artist

        return None

    @property
    def media_duration(self) -> float | None:
        """
        Returns:
            str: the current media_duration
        """
        if self.current_track is not None:
            return self._current_track.media_duration

        return None

    def get_media_info(self) -> dict[str, Any]:
        """Get the current media info from the soundbar

        Returns:
            dict: the response in JSON form
        """

        media_info = (
            self._call_service_action(Yas209Service.AVT, "GetMediaInfo", InstanceID=0)
            or {}
        )

        self._parse_xml_dict(media_info)

        return media_info

    @property
    def media_title(self) -> str | None:
        """
        Returns:
            str: the current media_album_name
        """
        if self.current_track is not None:
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

    @property
    def volume_level(self) -> float:
        """
        Returns:
            float: the current volume level
        """
        if not hasattr(self, "_volume_level"):

            res = (
                self._call_service_action(
                    Yas209Service.RC,
                    "GetVolume",
                    InstanceID=0,
                    Channel="Master",
                )
                or {}
            )

            self._volume_level = float(res.get("CurrentVolume", 0) / 100)

        return self._volume_level
