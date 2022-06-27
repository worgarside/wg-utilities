"""This module has classes etc. for subscribing to YAS-209 updates"""
from __future__ import annotations

from asyncio import get_event_loop, sleep
from copy import deepcopy
from datetime import datetime, timedelta
from enum import Enum
from logging import DEBUG, getLogger
from time import strptime
from typing import (
    Any,
    Callable,
    Dict,
    Literal,
    Optional,
    Sequence,
    TypedDict,
    TypeVar,
    Union,
)

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpRequester
from async_upnp_client.client import UpnpService, UpnpStateVariable
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.utils import get_local_ip
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
    dc_title: str = Field(..., alias="dc:title")
    dc_creator: str = Field(..., alias="dc:creator")
    upnp_artist: str = Field(..., alias="upnp:artist")
    upnp_album: str = Field(..., alias="upnp:album")
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
        self.loop = get_event_loop()

        # noinspection HttpUrlsUsage
        self.description_url = f"http://{ip}:49152/description.xml"

        self.on_volume_update = on_volume_update
        self.on_track_update = on_track_update
        self.on_state_update = on_state_update

        self._current_track: CurrentTrack
        self._state: Yas209State
        self._volume_level: float

        if start_listener:
            self.listen()

    def listen(self) -> None:
        """Start the listener"""
        self.loop.run_until_complete(self.subscribe())

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
            self.volume_level = last_change.Event.InstanceID.Volume.val

        if self.on_event is not None:
            self.on_event(event_payload)

    async def subscribe(self) -> None:
        """Subscribe to service(s) and output updates."""

        requester = AiohttpRequester()
        factory = UpnpFactory(requester)

        # create a device
        device = await factory.async_create_device(self.description_url)

        # start notify server/event handler
        source = (get_local_ip(device.device_url), 0)
        server = AiohttpNotifyServer(device.requester, source=source)
        await server.async_start_server()
        event_handler = server.event_handler

        # create service subscriptions
        services = []
        failed_subscriptions = []
        for service_name in device.services.keys():
            if not self.SUBSCRIPTION_SERVICES & set(service_name.split(":")):
                continue

            service = next(
                service
                for service in device.all_services
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

        # keep the webservice running (force resubscribe)
        while True:
            await sleep(120)
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
    def volume_level(self) -> Union[float, None]:
        """
        Returns:
            float: the current volume level
        """
        if hasattr(self, "_volume_level"):
            return self._volume_level

        return None

    @volume_level.setter
    def volume_level(self, value: str) -> None:
        # The DLNA payload has volume as a string value between 0 and 100

        self._volume_level = float(value) / 100

        if self.on_volume_update is not None:
            self.on_volume_update(self._volume_level)
