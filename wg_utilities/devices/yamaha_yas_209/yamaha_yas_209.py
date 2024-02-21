"""Classes etc. for subscribing to YAS-209 updates."""

from __future__ import annotations

from asyncio import new_event_loop, run
from asyncio import sleep as async_sleep
from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import wraps
from logging import DEBUG, getLogger
from re import compile as re_compile
from textwrap import dedent
from threading import Thread
from time import sleep, strptime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeVar

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpCommunicationError
from async_upnp_client.utils import get_local_ip
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from xmltodict import parse as parse_xml

from wg_utilities.functions import traverse_dict
from wg_utilities.loggers import add_stream_handler

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping, MutableMapping, Sequence

    from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


class StateVariable(BaseModel, extra="allow"):
    """BaseModel for state variables in DLNA payload."""

    channel: str
    val: str


class CurrentTrackMetaDataItemRes(BaseModel, extra="allow"):
    """BaseModel for part of the DLNA payload."""

    protocolInfo: str  # noqa: N815
    duration: str
    text: str | None = None


class TrackMetaDataItem(BaseModel, extra="allow"):
    """BaseModel for part of the DLNA payload."""

    id: str
    song_subid: str | None = Field(None, alias="song:subid")
    song_description: str | None = Field(None, alias="song:description")
    song_skiplimit: str | None = Field(None, alias="song:skiplimit")
    song_id: str | None = Field(None, alias="song:id")
    song_like: str | None = Field(None, alias="song:like")
    song_singerid: str | None = Field(None, alias="song:singerid")
    song_albumid: str | None = Field(None, alias="song:albumid")
    res: CurrentTrackMetaDataItemRes
    dc_title: str | None = Field(None, alias="dc:title")
    dc_creator: str | None = Field(None, alias="dc:creator")
    upnp_artist: str | None = Field(None, alias="upnp:artist")
    upnp_album: str | None = Field(None, alias="upnp:album")
    upnp_albumArtURI: str | None = Field(None, alias="upnp:albumArtURI")  # noqa: N815


class TrackMetaData(BaseModel, extra="allow"):
    """BaseModel for part of the DLNA payload."""

    item: TrackMetaDataItem


class InstanceIDAVTransport(BaseModel, extra="allow"):
    """BaseModel for part of the DLNA payload."""

    val: str
    TransportState: str
    TransportStatus: str | None = None
    NumberOfTracks: str | None = None
    CurrentTrack: str | None = None
    CurrentTrackDuration: str | None = None
    CurrentMediaDuration: str | None = None
    CurrentTrackURI: str | None = None
    AVTransportURI: str | None = None
    TrackSource: str | None = None
    CurrentTrackMetaData: TrackMetaData | None = None
    AVTransportURIMetaData: TrackMetaData | None = None
    PlaybackStorageMedium: str | None = None
    PossiblePlaybackStorageMedia: str | None = None
    PossibleRecordStorageMedia: str | None = None
    RecordStorageMedium: str | None = None
    CurrentPlayMode: str | None = None
    TransportPlaySpeed: str | None = None
    RecordMediumWriteStatus: str | None = None
    CurrentRecordQualityMode: str | None = None
    PossibleRecordQualityModes: str | None = None
    RelativeTimePosition: str | None = None
    AbsoluteTimePosition: str | None = None
    RelativeCounterPosition: str | None = None
    AbsoluteCounterPosition: str | None = None
    CurrentTransportActions: str | None = None


class InstanceIDRenderingControl(BaseModel, extra="allow"):
    """BaseModel for part of the DLNA payload."""

    val: str
    Mute: StateVariable
    Channel: StateVariable | None = None
    Equalizer: StateVariable | None = None
    # There's a typo in the schema, this is correct for some payloads -.-
    Equaluzer: StateVariable | None = None
    Volume: StateVariable
    PresetNameList: str | None = None
    TimeStamp: str | None = None


class EventAVTransport(BaseModel, extra="allow"):
    """BaseModel for part of the DLNA payload."""

    xmlns: Literal["urn:schemas-upnp-org:metadata-1-0/AVT/"]
    InstanceID: InstanceIDAVTransport


class EventRenderingControl(BaseModel, extra="allow"):
    """BaseModel for part of the DLNA payload."""

    xmlns: Literal["urn:schemas-upnp-org:metadata-1-0/RCS/"]
    InstanceID: InstanceIDRenderingControl


class LastChange(BaseModel, extra="allow"):
    """BaseModel for the DLNA payload."""

    Event: Any

    @classmethod
    def parse(cls, payload: dict[Literal["Event"], object]) -> LastChange:
        """Parse a `LastChange` model from the payload dictionary.

        Args:
            payload (Dict[str, Any]): the DLNA DMR payload

        Returns:
            LastChange: The parsed `Case`.

        Raises:
            TypeError: if the payload isn't a dict
            ValueError: if more than just "Event" is in the payload
        """
        if not isinstance(payload, dict):
            raise TypeError(f"Expected a dict, got {type(payload)!r}")

        payload = payload.copy()

        event = payload.pop("Event")

        if payload:
            raise ValueError(
                f"Extra fields not permitted: {list(payload.keys())!r}",
            )

        return cls(Event=event)


class LastChangeAVTransport(LastChange):
    """BaseModel for an AVTransport DLNA payload."""

    Event: EventAVTransport


class LastChangeRenderingControl(LastChange):
    """BaseModel for a RenderingControl DLNA payload."""

    Event: EventRenderingControl


LastChangeTypeVar = TypeVar("LastChangeTypeVar", bound=LastChange)


class GetMediaInfoResponse(BaseModel):
    """BaseModel for the response from a GetMediaInfo request."""

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
    """Class for easy processing/passing of track metadata.

    Attributes:
        album_art_uri (str): URL for album artwork
        media_album_name (str): album name
        media_artist (str): track's artist(s)
        media_title (str): track's title
    """

    DURATION_FORMAT = "%H:%M:%S.%f"

    NULL_TRACK_STR = "NULL"

    class Info(TypedDict):
        """Info for the attributes of this class."""

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
    def _create_from_metadata_item(cls, metadata_item: TrackMetaDataItem) -> CurrentTrack:
        """Create a CurrentTrack instance from a response metadata item.

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
            album_art_uri=(
                metadata_item.upnp_albumArtURI
                if metadata_item.upnp_albumArtURI != "un_known"
                else None
            ),
            media_album_name=metadata_item.upnp_album,
            media_artist=metadata_item.dc_creator,
            media_duration=duration_delta.total_seconds(),
            media_title=metadata_item.dc_title,
        )

    @classmethod
    def from_get_media_info(cls, response: GetMediaInfoResponse) -> CurrentTrack:
        """Create a CurrentTrack instance from a GetMediaInfo response.

        Args:
            response (GetMediaInfoResponse): the response from a GetMediaInfo request

        Returns:
            CurrentTrack: a CurrentTrack instance with relevant info
        """
        return cls._create_from_metadata_item(response.CurrentURIMetaData.item)

    @classmethod
    def from_last_change(cls, last_change: LastChangeTypeVar) -> CurrentTrack:
        """Create a CurrentTrack instance from a LastChange response.

        Args:
            last_change (LastChangeAVTransport): the payload from the last DLNA change

        Returns:
            CurrentTrack: a CurrentTrack instance with relevant info
        """
        return cls._create_from_metadata_item(
            last_change.Event.InstanceID.CurrentTrackMetaData.item,
        )

    @classmethod
    def null_track(cls) -> CurrentTrack:
        """Create a null track.

        Returns:
            CurrentTrack: a CurrentTrack instance with all attributes set to None
        """
        return cls(
            album_art_uri=None,
            media_album_name=None,
            media_artist=None,
            media_duration=0.0,
            media_title=None,
        )

    @property
    def json(self) -> CurrentTrack.Info:
        """JSON representation of the current track.

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

    def __eq__(self, other: object) -> bool:
        """Check equality of this instance with another object.

        Args:
            other (object): the object to compare to

        Returns:
            bool: True if the objects are equal, False otherwise
        """
        if not isinstance(other, CurrentTrack):
            return NotImplemented

        return self.json == other.json

    def __repr__(self) -> str:
        """Get a string representation of this instance."""
        return f"{self.__class__.__name__}({self.__str__()!r})"

    def __str__(self) -> str:
        """Return a string representation of the current track."""

        if self.media_title is None and self.media_artist is None:
            return self.NULL_TRACK_STR

        return f"{self.media_title!r} by {self.media_artist}"


class Yas209State(Enum):
    """Enumeration for states as they come in the DLNA payload."""

    PLAYING = "playing", "Play"
    PAUSED_PLAYBACK = "paused", "Pause"
    STOPPED = "off", "Stop"
    NO_MEDIA_PRESENT = "idle", None
    UNKNOWN = "unknown", None

    def __init__(self, value: str, action: str | None):
        self._value_ = value
        self.action = action


class Yas209Service(Enum):
    """Enumeration for available YAS-209 services."""

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
        self,
        value: str,
        service_id: str,
        service_name: str,
        actions: tuple[str],
    ):
        self._value_ = value
        self.service_id = service_id
        self.service_name = service_name
        self.actions = actions


def _needs_device(
    func: Callable[[YamahaYas209], Coroutine[Any, Any, Mapping[str, Any] | None]],
) -> Callable[[YamahaYas209], Any]:
    """Use as a decorator to ensure the device is available.

    This decorator is used when the DLNA device is needed and provides a clean
    way of instantiating it lazily

    Args:
        func (Callable): the function being wrapped

    Returns:
        Callable: the inner function
    """

    @wraps(func)
    def create_device(yas_209: YamahaYas209) -> Any:
        """Create the device before executing the wrapped method.

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
                    yas_209.description_url,
                )

            run(_create())

        return func(yas_209)

    return create_device


class YamahaYas209:
    """Class for consuming information from a YAS-209 in real time.

    Callback functions can be provided, as well as the option to start the
    listener immediately.

    Args:
        ip (str): the IP address of the YAS-209
        on_event (Callable[[YamahaYas209, Event], None], optional): a callback
            function to be called when an event is received. Defaults to None.
        start_listener (bool, optional): whether to start the listener
        on_volume_update (Callable[[YamahaYas209, int], None], optional): a
            callback function to be called when the volume is updated. Defaults
            to None.
        on_track_update (Callable[[YamahaYas209, Track], None], optional): a
            callback function to be called when the track is updated. Defaults
            to None.
        on_state_update (Callable[[YamahaYas209, State], None], optional): a
            callback function to be called when the state is updated. Defaults
            to None.
        logging (bool, optional): whether to log events. Defaults to False.
        listen_ip (str, optional): the IP address to listen on. Defaults to
            None.
        listen_port (int, optional): the port to listen on. Defaults to None.
        source_port (int, optional): the port to use for the source. Defaults
            to None.
        resubscribe_seconds (int, optional): the number of seconds between each
            resubscription. Defaults to 2 minutes.
    """

    SUBSCRIPTION_SERVICES = (
        Yas209Service.AVT.service_id,
        Yas209Service.RC.service_id,
    )

    LAST_CHANGE_PAYLOAD_PARSERS: ClassVar[
        dict[str, Callable[[dict[Literal["Event"], object]], LastChange]]
    ] = {
        Yas209Service.AVT.service_id: LastChangeAVTransport.parse,
        Yas209Service.RC.service_id: LastChangeRenderingControl.parse,
    }

    class EventPayloadInfo(TypedDict):
        """Info for the payload sent to the `on_event` callback."""

        timestamp: datetime
        service_id: str
        service_type: str
        last_change: LastChange
        other_xml_payloads: dict[str, Any]

    def __init__(  # noqa: PLR0913
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
        resubscribe_seconds: int = 120,
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

        self.resubscribe_seconds = resubscribe_seconds

        self._active_service_ids: list[str] = []

        if self._listen_ip is not None and self._listen_port is None:
            raise ValueError(
                "Argument `listen_port` cannot be None when `listen_ip` is not None:"
                f" {self._listen_ip!r}",
            )

        if start_listener:
            self.listen()

    def listen(self) -> None:
        """Start the listener."""
        if self._logging:
            LOGGER.info("Starting listener")

        if self._listening:
            if self._logging:
                LOGGER.debug(
                    "Already listening to '%s', returning immediately",
                    "', '".join(self._active_service_ids),
                )
            return

        worker_exception: BaseException | None = None

        def _worker() -> None:
            nonlocal worker_exception
            try:
                new_event_loop().run_until_complete(self._subscribe())
            except Exception as exc:
                worker_exception = exc

        listener_thread = Thread(target=_worker)
        listener_thread.start()

        while not self._listening and worker_exception is None:
            sleep(0.01)

        if isinstance(worker_exception, BaseException):
            raise worker_exception

        if self._logging:
            LOGGER.debug(
                "Listen action complete, now subscribed to '%s'",
                "', '".join(self._active_service_ids),
            )

    def on_event_wrapper(
        self,
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable[str]],
    ) -> None:
        """Wrap the `on_event` callback to process the XML payload(s) first.

        Args:
            service (UpnpService): the service which has sent an update
            service_variables (list): a list of state variables that have updated
        """

        xml_payloads: dict[str, object] = {sv.name: sv.value for sv in service_variables}

        # Convert any nested XML into JSON
        self._parse_xml_dict(xml_payloads)

        last_change = self.LAST_CHANGE_PAYLOAD_PARSERS[service.service_id](
            xml_payloads.pop("LastChange"),  # type: ignore[arg-type]
        )

        event_payload: YamahaYas209.EventPayloadInfo = {
            "timestamp": datetime.now(UTC),
            "service_id": service.service_id,
            "service_type": service.service_type,
            "last_change": last_change,
            "other_xml_payloads": xml_payloads,
        }

        if service.service_id == "urn:upnp-org:serviceId:AVTransport":
            if last_change.Event.InstanceID.TransportState != self.state.name:
                self.set_state(
                    Yas209State[last_change.Event.InstanceID.TransportState],
                    local_only=True,
                )
            if last_change.Event.InstanceID.CurrentTrackMetaData is None:
                self.current_track = CurrentTrack.null_track()
            else:
                self.current_track = CurrentTrack.from_last_change(last_change)
        elif service.service_id == "urn:upnp-org:serviceId:RenderingControl":
            # The DLNA payload has volume as a string value between 0 and 100
            self.set_volume_level(
                float(last_change.Event.InstanceID.Volume.val) / 100,
                local_only=True,
            )

        if self.on_event is not None:
            self.on_event(event_payload)

    @_needs_device
    async def _subscribe(self) -> None:  # noqa: PLR0912
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
            self.device.requester,
            source=source,
            callback_url=callback_url,
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
            """,
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
        failed_subscriptions = []
        for service in self.device.services.values():
            if service.service_id not in self.SUBSCRIPTION_SERVICES:
                continue

            service.on_event = self.on_event_wrapper
            try:
                await server.event_handler.async_subscribe(service)
                self._active_service_ids.append(service.service_id)
                LOGGER.info("Subscribed to %s", service.service_id)
            except UpnpCommunicationError:
                if self._logging:
                    LOGGER.exception(
                        "Unable to subscribe to %s",
                        service.service_id,
                    )
                failed_subscriptions.append(service)

        self._listening = True

        # keep the webservice running (force resubscribe)
        while self._listening:
            for _ in range(self.resubscribe_seconds):
                if not self._listening:
                    if self._logging:
                        LOGGER.debug("Exiting listener loop")
                    break
                await async_sleep(1)

            # The break above only covers the for loop, this is for the while loop
            if not self._listening:
                break

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
                except UpnpCommunicationError as exc:  # noqa: PERF203
                    log_message = (
                        f"Still unable to subscribe to {service.service_id}: {exc!r}"
                    )

                    if self._logging:
                        LOGGER.exception(log_message)
                    else:
                        # Should still log this exception, regardless
                        LOGGER.warning(log_message)

            # This needs to be separate because `.remove` is the cleanest way to remove
            # the items, but can't be done within the loop, and I can't `deepcopy`
            # `failed_subscriptions` and its threaded content
            for service in services_to_remove:
                failed_subscriptions.remove(service)

        if self._logging:
            LOGGER.debug(
                "Exiting subscription loop, `self._listening` is `%s`",
                str(self._listening),
            )

    def _call_service_action(
        self,
        service: Yas209Service,
        action: str,
        callback: Callable[[Mapping[str, object]], None] | None = None,
        **call_kwargs: str | int,
    ) -> dict[str, Any] | None:
        if action not in service.actions:
            raise ValueError(
                f"Unexpected action {action!r} for service {service.value!r}. "
                f"""Must be one of '{"', '".join(service.actions)}'""",
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

        return run(_worker(self))  # type: ignore[no-any-return]

    @staticmethod
    def _parse_xml_dict(xml_dict: MutableMapping[str, object]) -> None:
        """Convert XML to JSON within dict in place.

        Parse a dictionary where some values are/could be XML strings, and unpack
        the XML into JSON within the dict

        Args:
            xml_dict (dict): the dictionary to parse
        """

        pattern = re_compile(r"&(?!(amp|apos|lt|gt|quot);)")

        traverse_dict(
            xml_dict,
            target_type=str,
            target_processor_func=lambda val, **_: parse_xml(  # type: ignore[arg-type]
                pattern.sub("&amp;", val),
                attr_prefix="",
                cdata_key="text",
            ),
            single_keys_to_remove=["val", "DIDL-Lite"],
        )

    # TODO: @on_exception()
    def pause(self) -> None:
        """Pause the current media."""
        self._call_service_action(Yas209Service.AVT, "Pause", InstanceID=0)

    def play(self) -> None:
        """Play the current media."""
        self._call_service_action(Yas209Service.AVT, "Play", InstanceID=0, Speed="1")

    def play_pause(self) -> None:
        """Toggle the playing/paused state."""
        if self.state == Yas209State.PLAYING:
            self.pause()
        else:
            self.play()

    def mute(self) -> None:
        """Mute."""
        self._call_service_action(
            Yas209Service.RC,
            "SetMute",
            InstanceID=0,
            Channel="Master",
            DesiredMute=True,
        )

    def next_track(self) -> None:
        """Skip to the next track."""
        self._call_service_action(Yas209Service.AVT, "Next", InstanceID=0)

    def previous_track(self) -> None:
        """Go to the previous track."""
        self._call_service_action(Yas209Service.AVT, "Previous", InstanceID=0)

    def set_state(self, value: Yas209State, *, local_only: bool = False) -> None:
        """Set the state to the given value.

        Args:
            value (Yas209State): the new state of the YAS-209
            local_only (bool): only change the local value of the state (i.e. don't
                update the soundbar)

        Raises:
            TypeError: if the value is not a valid state
        """
        if not isinstance(value, Yas209State):
            raise TypeError("Expected a Yas209State instance.")

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

    def set_volume_level(self, value: float, *, local_only: bool = False) -> None:
        """Set the soundbar's volume level.

        Args:
            value (float): the new volume level, as a float between 0 and 1
            local_only (bool): only change the local value of the volume level (i.e.
                don't update the soundbar)

        Raises:
            ValueError: if the value is not between 0 and 1
        """

        if not 0 <= value <= 1:
            raise ValueError("Volume level must be between 0 and 1")

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
        """Stop whatever is currently playing."""
        self._call_service_action(Yas209Service.AVT, "Stop", InstanceID=0, Speed="1")

    def stop_listening(self) -> None:
        """Stop the event listener."""
        if self._logging:
            LOGGER.debug(
                "Stopping event listener (will take <= %i seconds)",
                self.resubscribe_seconds,
            )

        self._listening = False

    def unmute(self) -> None:
        """Unmute."""
        self._call_service_action(
            Yas209Service.RC,
            "SetMute",
            InstanceID=0,
            Channel="Master",
            DesiredMute=False,
        )

    def volume_down(self) -> None:
        """Decrease the volume by 2 points."""
        self.set_volume_level(round(self.volume_level - 0.02, 2))

    def volume_up(self) -> None:
        """Increase the volume by 2 points."""
        self.set_volume_level(round(self.volume_level + 0.02, 2))

    @property
    def album_art_uri(self) -> str | None:
        """Album art URI for the currently playing media.

        Returns:
            str: URL for the current album's artwork
        """
        return self.current_track.album_art_uri

    @property
    def current_track(self) -> CurrentTrack:
        """Currently playing track.

        Returns:
            dict: the current track's info
        """
        if not hasattr(self, "_current_track"):
            media_info = self.get_media_info()
            self._current_track = CurrentTrack.from_get_media_info(
                GetMediaInfoResponse.model_validate(media_info),
            )

        return self._current_track

    @current_track.setter
    def current_track(self, value: CurrentTrack) -> None:
        """Set the current track.

        Args:
            value (CurrentTrack): the new current track

        Raises:
            TypeError: if the value is not a CurrentTrack instance
        """

        if not isinstance(value, CurrentTrack):
            raise TypeError("Expected a CurrentTrack instance.")

        self._current_track = value

        if self.on_track_update is not None:
            self.on_track_update(value.json)

    @property
    def is_listening(self) -> bool:
        """Whether the event listener is running.

        Returns:
            bool: whether the event listener is running
        """
        return self._listening

    @property
    def media_album_name(self) -> str | None:
        """Name of the current album.

        Returns:
            str: the current media_title
        """
        return self.current_track.media_album_name

    @property
    def media_artist(self) -> str | None:
        """Currently playing artist.

        Returns:
            str: the current media_artist
        """
        return self.current_track.media_artist

    @property
    def media_duration(self) -> float | None:
        """Duration of current playing media in seconds.

        Returns:
            str: the current media_duration
        """
        return self.current_track.media_duration

    def get_media_info(self) -> dict[str, Any]:
        """Get the current media info from the soundbar.

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
        """Currently playing media title.

        Returns:
            str: the current media_album_name
        """
        return self.current_track.media_title

    @property
    def state(self) -> Yas209State:
        """Current state of the soundbar.

        Returns:
            Yas209State: the current state of the YAS-209 (e.g. playing, stopped)
        """
        if hasattr(self, "_state"):
            return self._state

        return Yas209State.UNKNOWN

    @property
    def volume_level(self) -> float:
        """Current volume level.

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
