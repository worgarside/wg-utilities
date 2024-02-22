"""Custom client for interacting with Google's Calendar API."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, timedelta, tzinfo
from datetime import date as date_
from datetime import datetime as datetime_
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, TypeAlias

from pydantic import Field, field_serializer, field_validator, model_validator
from requests import delete
from typing_extensions import NotRequired, TypedDict
from tzlocal import get_localzone
from zoneinfo import ZoneInfo

from wg_utilities.clients._google import GoogleClient
from wg_utilities.clients.oauth_client import BaseModelWithConfig

if TYPE_CHECKING:
    from collections.abc import Iterable

    from wg_utilities.clients.json_api_client import StrBytIntFlt


class ResponseStatus(StrEnum):
    """Enumeration for event attendee response statuses."""

    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    UNCONFIRMED = "needsAction"
    UNKNOWN = "unknown"


class EventType(StrEnum):
    """Enumeration for event types."""

    DEFAULT = "default"
    FOCUS_TIME = "focusTime"
    OUT_OF_OFFICE = "outOfOffice"


class _Attendee(BaseModelWithConfig):
    additionalGuests: int | None = None  # noqa: N815
    comment: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    email: str
    id: str | None = None
    optional: bool = False
    organizer: bool = False
    resource: bool = False
    response_status: ResponseStatus = Field(
        alias="responseStatus",
        default=ResponseStatus.UNKNOWN,
    )
    self: bool = False


class _ConferenceDataCreateRequest(TypedDict):
    requestId: str
    conferenceSolutionKey: dict[Literal["type"], Literal["hangoutsMeet"]]
    status: dict[Literal["statusCode"], Literal["success"]]


class _ConferenceDataEntryPoints(TypedDict, total=False):
    entryPointType: str
    uri: str
    label: str
    pin: str | None
    accessCode: str | None
    meetingCode: str | None
    passcode: str | None
    password: str | None
    regionCode: str | None


class _ConferenceDataConferenceSolution(TypedDict):
    key: dict[Literal["type"], Literal["hangoutsMeet", "addOn"]]
    name: str
    iconUri: str


class _ConferenceData(TypedDict, total=False):
    createRequest: _ConferenceDataCreateRequest
    entryPoints: list[_ConferenceDataEntryPoints]
    conferenceSolution: _ConferenceDataConferenceSolution
    conferenceId: str
    signature: str | None
    notes: str | None
    parameters: dict[str, object] | None


class _Creator(BaseModelWithConfig):
    display_name: str | None = Field(alias="displayName", default=None)
    email: str
    self: bool = False


class _StartEndDatetime(BaseModelWithConfig):
    """Model for `start` and `end` datetime objects."""

    datetime: datetime_ = Field(alias="dateTime")
    date: date_
    timezone: tzinfo = Field(alias="timeZone", default_factory=get_localzone)

    @model_validator(mode="before")
    @classmethod
    def validate_datetime_or_date(
        cls,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate that either `datetime` or `date` is provided."""

        values["timeZone"] = (
            ZoneInfo(values["timeZone"]) if "timeZone" in values else get_localzone()
        )

        dt: date_ | None = values.get("date")
        dttm: datetime_ | None = values.get("dateTime")

        if dt is None and dttm is None:
            raise ValueError("Either `date` or `dateTime` must be provided.")

        if dt is None:
            dttm = datetime_.strptime(
                dttm,  # type: ignore[arg-type]
                "%Y-%m-%dT%H:%M:%S%z",
            ).replace(tzinfo=values["timeZone"])
            dt = dttm.date()
        else:
            dt = date_.fromisoformat(dt)  # type: ignore[arg-type]
            dttm = datetime_(dt.year, dt.month, dt.day, tzinfo=values["timeZone"])

        values["date"] = dt
        values["dateTime"] = dttm

        return values

    @field_serializer("timezone", mode="plain", when_used="json", check_fields=True)
    def serialize_timezone(self, tz: tzinfo) -> str:
        """Serialize the timezone to a string."""

        return str(tz)


class CalendarJson(TypedDict):
    """JSON representation of a Calendar."""

    description: str | None
    etag: str
    id: str
    location: str | None
    summary: str

    kind: Literal["calendar#calendar"]
    timeZone: str
    conferenceProperties: dict[
        Literal["allowedConferenceSolutionTypes"],
        list[Literal["eventHangout", "eventNamedHangout", "hangoutsMeet"]],
    ]


class GoogleCalendarEntity(BaseModelWithConfig):
    """Base class for Google Calendar entities."""

    description: str | None = None
    etag: str
    id: str
    location: str | None = None
    summary: str

    google_client: GoogleCalendarClient = Field(exclude=True)

    @classmethod
    def from_json_response(
        cls,
        value: GoogleCalendarEntityJson,
        google_client: GoogleCalendarClient,
        calendar: Calendar | None = None,
    ) -> Self:
        """Create a Calendar/Event from a JSON response."""

        value_data: dict[str, Any] = {
            "google_client": google_client,
            **value,
        }

        if cls == Event:
            value_data["calendar"] = calendar

        return cls.model_validate(value_data)

    def __eq__(self, other: Any) -> bool:
        """Compare two GoogleCalendarEntity objects by ID."""
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.id == other.id


class _Reminder(BaseModelWithConfig):
    """Base class for Event reminders."""

    method: Literal["email", "popup"]
    minutes: int


class _Notification(BaseModelWithConfig):
    """Base class for Event notifications."""

    method: Literal["email", "sms"]
    type: Literal[
        "eventCreation",
        "eventChange",
        "eventCancellation",
        "eventResponse",
        "agenda",
    ]


class Calendar(GoogleCalendarEntity):
    """Class for Google calendar instances."""

    access_role: Literal["freeBusyReader", "reader", "writer", "owner"] | None = Field(
        None,
        alias="accessRole",
    )
    background_color: str | None = Field(None, alias="backgroundColor")
    color_id: str | None = Field(None, alias="colorId")
    conference_properties: dict[
        Literal["allowedConferenceSolutionTypes"],
        list[Literal["eventHangout", "eventNamedHangout", "hangoutsMeet"]],
    ] = Field(alias="conferenceProperties")
    default_reminders: list[_Reminder] = Field(
        alias="defaultReminders",
        default_factory=list,
    )
    deleted: bool = False
    foreground_color: str | None = Field(None, alias="foregroundColor")
    hidden: bool = False
    kind: Literal["calendar#calendar", "calendar#calendarListEntry"]
    notification_settings: dict[
        Literal["notifications"],
        list[_Notification],
    ] = Field(
        alias="notificationSettings",
        default_factory=list,  # type: ignore[assignment]
    )
    primary: bool = False
    selected: bool = False
    summary_override: str | None = Field(None, alias="summaryOverride")
    timezone: tzinfo = Field(alias="timeZone")

    # mypy can't get this type from the parent class for some reason...
    google_client: GoogleCalendarClient = Field(exclude=True)

    @field_validator("timezone", mode="before")
    @classmethod
    def validate_timezone(cls, value: str) -> tzinfo:
        """Convert the timezone string into a tzinfo object."""
        if isinstance(value, tzinfo):
            return value

        return ZoneInfo(value)

    @field_serializer("timezone", mode="plain", when_used="json", check_fields=True)
    def serialize_timezone(self, tz: tzinfo) -> str:
        """Serialize the timezone to a string."""

        return str(tz)

    def get_event_by_id(self, event_id: str) -> Event:
        """Get an event by its ID.

        Args:
            event_id (str): ID of the event to get

        Returns:
            Event: Event object
        """

        return self.google_client.get_event_by_id(event_id, calendar=self)

    def get_events(
        self,
        page_size: int = 500,
        order_by: Literal["updated", "startTime"] = "updated",
        from_datetime: datetime_ | None = None,
        to_datetime: datetime_ | None = None,
        day_limit: int | None = None,
        *,
        combine_recurring_events: bool = False,
    ) -> list[Event]:
        """Retrieve events from the calendar according to a set of criteria.

        Args:
            page_size (int): the number of records to return on a single response page
            order_by (Literal["updated", "startTime"]): the order of the events
                returned within the result
            from_datetime (datetime): lower bound (exclusive) for an event's end time
                to filter by. Defaults to 90 days ago.
            to_datetime (datetime): upper bound (exclusive) for an event's start time
                to filter by. Defaults to now.
            combine_recurring_events (bool): whether to expand recurring events into
                instances and only return single one-off events and instances of recurring
                events, but not the underlying recurring events themselves
            day_limit (int): the maximum number of days to return events for.

        Returns:
            List[Event]: a list of Event instances

        Raises:
            ValueError: if the time parameters are invalid
        """
        params = {
            "maxResults": page_size,
            "orderBy": order_by,
            "singleEvents": str(not combine_recurring_events),
        }
        if from_datetime or to_datetime or day_limit:
            to_datetime = to_datetime or datetime_.utcnow()
            from_datetime = from_datetime or to_datetime - timedelta(days=day_limit or 90)

            if day_limit is not None:
                # Force the to_datetime to be within the day_limit
                to_datetime = min(to_datetime, from_datetime + timedelta(days=day_limit))

            if from_datetime.tzinfo is None:
                from_datetime = from_datetime.replace(tzinfo=UTC)

            if to_datetime.tzinfo is None:
                to_datetime = to_datetime.replace(tzinfo=UTC)

            params["timeMin"] = from_datetime.isoformat()
            params["timeMax"] = to_datetime.isoformat()

        return [
            Event.from_json_response(
                item,
                calendar=self,
                google_client=self.google_client,
            )
            for item in self.google_client.get_items(
                f"{self.google_client.base_url}/calendars/{self.id}/events",
                params=params,  # type: ignore[arg-type]
            )
        ]

    def __str__(self) -> str:
        """Return the calendar name."""
        return self.summary


class _EventReminders(TypedDict):
    useDefault: bool
    overrides: NotRequired[list[_Reminder]]


class EventJson(TypedDict, total=False):
    """JSON representation of an Event."""

    description: str | None
    etag: str
    id: str
    location: str | None
    summary: str | None

    attachments: list[dict[str, str]] | None
    attendees: list[_Attendee] | None
    attendeesOmitted: bool | None
    created: datetime_
    colorId: str | None
    conferenceData: _ConferenceData | None
    creator: _Creator
    end: _StartEndDatetime
    endTimeUnspecified: bool | None
    eventType: EventType  # "default"
    extendedProperties: dict[str, dict[str, str]] | None
    guestsCanInviteOthers: bool | None
    guestsCanModify: bool | None
    guestsCanSeeOtherGuests: bool | None
    hangoutLink: str | None
    htmlLink: str
    iCalUID: str
    kind: Literal["calendar#event"]
    locked: bool | None
    organizer: dict[str, bool | str]
    original_start_time: dict[str, str] | None
    privateCopy: bool | None
    recurrence: list[str] | None
    recurringEventId: str | None
    reminders: _EventReminders | None
    sequence: int
    source: dict[str, str] | None
    start: _StartEndDatetime
    status: Literal["cancelled", "confirmed", "tentative"] | None
    transparency: str | None
    updated: datetime_
    visibility: Literal["default", "public", "private", "confidential"] | None


class Event(GoogleCalendarEntity):
    """Class for Google Calendar events."""

    summary: str = "(No Title)"

    attachments: list[dict[str, str]] | None = None
    attendees: list[_Attendee] = Field(default_factory=list)
    attendees_omitted: bool | None = Field(None, alias="attendeesOmitted")
    created: datetime_
    color_id: str | None = Field(None, alias="colorId")
    conference_data: _ConferenceData | None = Field(None, alias="conferenceData")
    creator: _Creator
    end: _StartEndDatetime
    end_time_unspecified: bool | None = Field(None, alias="endTimeUnspecified")
    event_type: EventType = Field(alias="eventType")
    extended_properties: dict[str, dict[str, str]] | None = Field(
        None,
        alias="extendedProperties",
    )
    guests_can_invite_others: bool | None = Field(None, alias="guestsCanInviteOthers")
    guests_can_modify: bool | None = Field(None, alias="guestsCanModify")
    guests_can_see_other_guests: bool | None = Field(
        None,
        alias="guestsCanSeeOtherGuests",
    )
    hangout_link: str | None = Field(None, alias="hangoutLink")
    html_link: str = Field(alias="htmlLink")
    ical_uid: str = Field(alias="iCalUID")
    kind: Literal["calendar#event"]
    locked: bool | None = None
    organizer: dict[str, bool | str]
    original_start_time: dict[str, str] | None = Field(None, alias="originalStartTime")
    private_copy: bool | None = Field(None, alias="privateCopy")
    recurrence: list[str] | None = None
    recurring_event_id: str | None = Field(None, alias="recurringEventId")
    reminders: _EventReminders | None = None
    sequence: int
    source: dict[str, str] | None = None
    start: _StartEndDatetime
    status: Literal["cancelled", "confirmed", "tentative"] | None = None
    transparency: str | None = None  # != transparent
    updated: datetime_
    visibility: Literal["default", "public", "private", "confidential"] | None = None

    calendar: Calendar

    def delete(self) -> None:
        """Delete the event from the host calendar."""
        self.google_client.delete_event_by_id(event_id=self.id, calendar=self.calendar)

    @property
    def response_status(self) -> ResponseStatus:
        """User's response status.

        Returns:
            ResponseStatus: the response status for the authenticated user
        """
        for attendee in self.attendees:
            if attendee.self is True:
                return attendee.response_status

        # Own events don't always have attendees
        if self.creator.self:
            return ResponseStatus.ACCEPTED

        return ResponseStatus.UNKNOWN

    def __gt__(self, other: Event) -> bool:
        """Compare two events by their start time, end time, or name."""

        if not isinstance(other, Event):
            return NotImplemented

        return (self.start.datetime, self.end.datetime, self.summary) > (
            other.start.datetime,
            other.end.datetime,
            other.summary,
        )

    def __lt__(self, other: Event) -> bool:
        """Compare two events by their start time, end time, or name."""

        if not isinstance(other, Event):
            return NotImplemented

        return (self.start.datetime, self.end.datetime, self.summary) < (
            other.start.datetime,
            other.end.datetime,
            other.summary,
        )

    def __str__(self) -> str:
        """Return the event's summary and start/end datetimes."""
        return (
            f"{self.summary} ("
            f"{self.start.datetime.isoformat()} - "
            f"{self.end.datetime.isoformat()})"
        )


GoogleCalendarEntityJson: TypeAlias = CalendarJson | EventJson


class GoogleCalendarClient(GoogleClient[GoogleCalendarEntityJson]):
    """Custom client specifically for Google's Calendar API."""

    BASE_URL = "https://www.googleapis.com/calendar/v3"

    DEFAULT_PARAMS: ClassVar[
        dict[StrBytIntFlt, StrBytIntFlt | Iterable[StrBytIntFlt] | None]
    ] = {
        "maxResults": "250",
    }

    DEFAULT_SCOPES: ClassVar[list[str]] = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    _primary_calendar: Calendar

    def create_event(
        self,
        summary: str,
        start_datetime: datetime_ | date_,
        end_datetime: datetime_ | date_,
        tz: str | None = None,
        calendar: Calendar | None = None,
        extra_params: dict[str, str] | None = None,
    ) -> Event:
        """Create an event.

        Args:
            summary (str): the summary (title) of the event
            start_datetime (Union[datetime, date]): when the event starts
            end_datetime (Union[datetime, date]): when the event ends
            tz (str): the timezone which the event is in (IANA database name)
            calendar (Calendar): the calendar to add the event to
            extra_params (dict): any extra params to pass in the request

        Returns:
            Event: a new event instance, fresh out of the oven

        Raises:
            TypeError: if the start/end datetime params are not the correct type
        """

        calendar = calendar or self.primary_calendar
        tz = tz or str(get_localzone())

        start_params = {
            "timeZone": tz,
        }

        if isinstance(start_datetime, datetime_):
            start_params["dateTime"] = start_datetime.isoformat()
        elif isinstance(start_datetime, date_):
            start_params["date"] = start_datetime.isoformat()
        else:
            raise TypeError("`start_datetime` must be either a date or a datetime")

        end_params = {
            "timeZone": tz,
        }

        if isinstance(end_datetime, datetime_):
            end_params["dateTime"] = end_datetime.isoformat()
        elif isinstance(end_datetime, date_):
            end_params["date"] = end_datetime.isoformat()
        else:
            raise TypeError("`end_datetime` must be either a date or a datetime")

        event_json = self.post_json_response(
            f"/calendars/{calendar.id}/events",
            json={
                "summary": summary,
                "start": start_params,
                "end": end_params,
                **(extra_params or {}),
            },
            params={"maxResults": None},
        )

        return Event.from_json_response(event_json, calendar=calendar, google_client=self)

    def delete_event_by_id(self, event_id: str, calendar: Calendar | None = None) -> None:
        """Delete an event from a calendar.

        Args:
            event_id (str): the ID of the event to delete
            calendar (Calendar): the calendar being updated
        """
        calendar = calendar or self.primary_calendar

        res = delete(
            f"{self.base_url}/calendars/{calendar.id}/events/{event_id}",
            headers=self.request_headers,
            timeout=10,
        )

        res.raise_for_status()

    def get_event_by_id(
        self,
        event_id: str,
        *,
        calendar: Calendar | None = None,
    ) -> Event:
        """Get a specific event by ID.

        Args:
            event_id (str): the ID of the event to delete
            calendar (Calendar): the calendar being updated

        Returns:
            Event: an Event instance with all relevant attributes
        """
        calendar = calendar or self.primary_calendar

        return Event.from_json_response(
            self.get_json_response(
                f"/calendars/{calendar.id}/events/{event_id}",
                params={"maxResults": None},
            ),
            calendar=calendar,
            google_client=self,
        )

    @property
    def calendar_list(self) -> list[Calendar]:
        """List of calendars.

        Returns:
            list: a list of Calendar instances that the user has access to
        """
        return [
            Calendar.from_json_response(cal_json, google_client=self)
            for cal_json in self.get_items(
                "/users/me/calendarList",
                params={"maxResults": None},
            )
        ]

    @property
    def primary_calendar(self) -> Calendar:
        """Primary calendar for the user.

        Returns:
            Calendar: the current user's primary calendar
        """
        if not hasattr(self, "_primary_calendar"):
            self._primary_calendar = Calendar.from_json_response(
                self.get_json_response("/calendars/primary", params={"maxResults": None}),
                google_client=self,
            )

        return self._primary_calendar


Calendar.model_rebuild()
Event.model_rebuild()
