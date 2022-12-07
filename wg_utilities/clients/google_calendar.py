"""Custom client for interacting with Google's Calendar API."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date as date_
from datetime import datetime as datetime_
from datetime import timedelta, tzinfo
from enum import Enum
from json import dumps
from pathlib import Path
from typing import AbstractSet, Any, Literal, TypeAlias, TypedDict, TypeVar

from pydantic import Field, validator
from pytz import UTC, timezone
from requests import delete
from tzlocal import get_localzone

from wg_utilities.clients._google import GoogleClient
from wg_utilities.clients.oauth_client import (
    BaseModelWithConfig,
    GenericModelWithConfig,
)


class ResponseStatus(str, Enum):
    """Enumeration for event attendee response statuses."""

    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    UNCONFIRMED = "needsAction"
    UNKNOWN = "unknown"


class EventType(str, Enum):
    """Enumeration for event types."""

    DEFAULT = "default"
    FOCUS_TIME = "focusTime"
    OUT_OF_OFFICE = "outOfOffice"


class _ConferenceDataCreateRequest(TypedDict):
    requestId: str  # noqa: N815
    conferenceSolutionKey: dict[Literal["type"], Literal["hangoutsMeet"]]  # noqa: N815
    status: dict[Literal["statusCode"], Literal["success"]]


class _ConferenceDataEntryPoints(TypedDict, total=False):
    entryPointType: str  # noqa: N815
    uri: str
    label: str
    pin: str | None
    accessCode: str | None  # noqa: N815
    meetingCode: str | None  # noqa: N815
    passcode: str | None
    password: str | None
    regionCode: str | None  # noqa: N815


class _ConferenceDataConferenceSolution(TypedDict):
    key: dict[Literal["type"], Literal["hangoutsMeet", "addOn"]]
    name: str
    iconUri: str  # noqa: N815


class _ConferenceData(TypedDict, total=False):
    createRequest: _ConferenceDataCreateRequest  # noqa: N815
    entryPoints: list[_ConferenceDataEntryPoints]  # noqa: N815
    conferenceSolution: _ConferenceDataConferenceSolution  # noqa: N815
    conferenceId: str  # noqa: N815
    signature: str | None
    notes: str | None
    parameters: dict[str, object] | None


class _StartEndDatetime(BaseModelWithConfig):
    """Model for `start` and `end` datetime objects."""

    datetime: datetime_ | None = Field(alias="dateTime")
    date: date_ = None  # type: ignore[assignment]
    timezone: tzinfo = Field(alias="timeZone", default_factory=get_localzone)

    @validator("datetime", pre=True, always=True)
    def validate_datetime(  # pylint: disable=no-self-argument
        cls,  # noqa: N805
        value: str,
        values: dict[str, Any],
    ) -> datetime_ | None:
        """Validate the `datetime` field.

        Args:
            value (str): The value to validate.
            values (dict[str, Any]): The values of the model.

        Returns:
            datetime_: The validated value.
        """
        if value is None:
            return value

        return_value = datetime_.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
        values["date"] = return_value.date()

        return return_value

    @validator("date", pre=True, always=True)
    def validate_date(  # pylint: disable=no-self-argument
        cls,  # noqa: N805
        value: str,
        values: dict[Literal["date"], date_],
    ) -> date_:
        """Validate the `date` field.

        Args:
            value (str): The value to validate.
            values (dict[str, Any]): The values of the model.

        Returns:
            date_: The validated value.
        """
        return date_.fromisoformat(value) if value else values["date"]

    @validator("timezone", pre=True)
    def validate_timezone(  # pylint: disable=no-self-argument
        cls, value: str  # noqa: N805
    ) -> tzinfo:
        """Validates the timezone."""
        return timezone(value)


class CalendarJson(TypedDict):
    """JSON representation of a Calendar."""

    description: str | None
    etag: str
    id: str
    location: str | None
    summary: str

    kind: Literal["calendar#calendar"]
    timeZone: str  # noqa: N815
    conferenceProperties: dict[  # noqa: N815
        Literal["allowedConferenceSolutionTypes"],
        list[Literal["eventHangout", "eventNamedHangout", "hangoutsMeet"]],
    ]


FJR = TypeVar("FJR", bound="GoogleCalendarEntity")


class GoogleCalendarEntity(GenericModelWithConfig):
    """Base class for Google Calendar entities."""

    description: str | None
    etag: str
    id: str
    location: str | None
    summary: str

    google_client: GoogleCalendarClient = Field(exclude=True)

    @classmethod
    def from_json_response(
        cls: type[FJR],
        value: GoogleCalendarEntityJson,
        google_client: GoogleCalendarClient,
        calendar: Calendar | None = None,
    ) -> FJR:
        """Creates a Calendar/Event from a JSON response."""

        value_data: dict[str, Any] = {
            "google_client": google_client,
            **value,
        }

        if cls == Event:
            value_data["calendar"] = calendar

        return cls.parse_obj(value_data)

    def dict(
        self,
        *,
        include: AbstractSet[int | str] | Mapping[int | str, Any] | None = None,
        exclude: AbstractSet[int | str] | Mapping[int | str, Any] | None = None,
        by_alias: bool = True,
        skip_defaults: bool | None = None,
        exclude_unset: bool = True,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> dict[str, Any]:
        # pylint: disable=useless-parent-delegation
        """Overrides the standard `BaseModel.dict` method.

        Allows us to consistently return the dict with the same field names it came in
        with, and exclude any null values that have been added when parsing.

        Original documentation is here:
          - https://pydantic-docs.helpmanual.io/usage/exporting_models/#modeldict

        Overridden Parameters:
            by_alias: False -> True
            exclude_unset: False -> True
        """

        return super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

    @staticmethod
    def _json_encoder(o: Any) -> str:
        """Custom encoder for GoogleCalendarEntity JSON serialization.

        Args:
            o (Any): object to encode

        Returns:
            str: encoded object
        """

        if isinstance(o, datetime_):
            return o.strftime(GoogleCalendarClient.DATETIME_FORMAT)

        if isinstance(o, tzinfo):
            return o.tzname(None) or ""

        return str(o)

    def json(
        self,
        *,
        include: AbstractSet[int | str] | Mapping[int | str, Any] | None = None,
        exclude: AbstractSet[int | str] | Mapping[int | str, Any] | None = None,
        by_alias: bool = True,
        skip_defaults: bool | None = None,
        exclude_unset: bool = True,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        encoder: Callable[[Any], Any] | None = None,
        models_as_dict: bool = True,
        **dumps_kwargs: Any,
    ) -> str:
        # pylint: disable=useless-parent-delegation
        """Overrides the standard `BaseModel.json` method.

        Allows us to consistently return the dict with the same field names it came in
        with, and exclude any null values that have been added when parsing.

        Original documentation is here:
          - https://pydantic-docs.helpmanual.io/usage/exporting_models/#modeljson

        Overridden Parameters:
            by_alias: False -> True
            exclude_unset: False -> True
            encoder: None -> self._json_encoder
        """

        return super().json(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            encoder=encoder or self._json_encoder,
            models_as_dict=models_as_dict,
            **dumps_kwargs,
        )


class Calendar(GoogleCalendarEntity):
    """Class for Google calendar instances."""

    kind: Literal["calendar#calendar"]
    timezone: tzinfo = Field(alias="timeZone")
    conference_properties: dict[
        Literal["allowedConferenceSolutionTypes"],
        list[Literal["eventHangout", "eventNamedHangout", "hangoutsMeet"]],
    ] = Field(alias="conferenceProperties")

    @validator("timezone", pre=True)
    def validate_timezone(  # pylint: disable=no-self-argument
        cls, value: str  # noqa: N805
    ) -> tzinfo:
        """Converts the timezone string into a tzinfo object."""
        return timezone(value)

    def get_events(
        self,
        page_size: int = 500,
        order_by: Literal["updated", "startTime"] = "updated",
        from_datetime: datetime_ | None = None,
        to_datetime: datetime_ | None = None,
        combine_recurring_events: bool = False,
        day_limit: int | None = None,
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
            from_datetime = from_datetime or to_datetime - timedelta(
                days=day_limit or 90
            )

            if day_limit is not None:
                # Force the to_datetime to be within the day_limit
                to_datetime = min(
                    to_datetime, from_datetime + timedelta(days=day_limit)
                )

            if from_datetime.tzinfo is None:
                from_datetime = from_datetime.replace(tzinfo=UTC)

            if to_datetime.tzinfo is None:
                to_datetime = to_datetime.replace(tzinfo=UTC)

            params["timeMin"] = from_datetime.strftime(
                GoogleCalendarClient.DATETIME_FORMAT
            )
            params["timeMax"] = to_datetime.strftime(
                GoogleCalendarClient.DATETIME_FORMAT
            )

        return [
            Event.from_json_response(
                item, calendar=self, google_client=self.google_client
            )
            for item in self.google_client.get_items(
                f"{self.google_client.base_url}/calendars/{self.id}/events",
                params=params,
            )
        ]

    def __str__(self) -> str:
        """Returns the calendar name."""
        return self.summary


class EventJson(TypedDict):
    """JSON representation of an Event."""

    description: str | None
    etag: str
    id: str
    location: str | None
    summary: str | None

    attachments: list[dict[str, str]] | None
    attendees: list[dict[str, str | bool]] | None
    attendeesOmitted: bool | None  # noqa: N815
    created: datetime_
    colorId: str | None  # noqa: N815
    conferenceData: _ConferenceData | None  # noqa: N815
    creator: dict[str, str | bool]
    end: _StartEndDatetime
    endTimeUnspecified: bool | None  # noqa: N815
    eventType: EventType  # "default"  # noqa: N815
    extendedProperties: dict[str, dict[str, str]] | None  # noqa: N815
    guestsCanInviteOthers: bool | None  # noqa: N815
    guestsCanModify: bool | None  # noqa: N815
    guestsCanSeeOtherGuests: bool | None  # noqa: N815
    hangoutLink: str | None  # noqa: N815
    htmlLink: str  # noqa: N815
    iCalUID: str  # noqa: N815
    kind: Literal["calendar#event"]
    locked: bool | None
    organizer: dict[str, str | bool]
    original_start_time: dict[str, str] | None
    privateCopy: bool | None  # noqa: N815
    recurrence: list[str] | None
    recurringEventId: str | None  # noqa: N815
    reminders: dict[str, bool | dict[str, str | int]]
    sequence: int
    source: dict[str, str] | None
    start: _StartEndDatetime
    status: Literal["cancelled", "confirmed", "tentative"] | None
    transparency: str | bool | None  # != transparent
    updated: datetime_
    visibility: Literal["default", "public", "private", "confidential"] | None


class Event(GoogleCalendarEntity):
    """Class for Google Calendar events."""

    summary: str = "(No Title)"

    attachments: list[dict[str, str]] | None
    attendees: list[dict[str, str | bool]] = Field(default_factory=list)
    attendees_omitted: bool | None = Field(alias="attendeesOmitted")
    created: datetime_
    color_id: str | None = Field(alias="colorId")
    conference_data: _ConferenceData | None = Field(alias="conferenceData")
    creator: dict[str, str | bool]
    end: _StartEndDatetime
    end_time_unspecified: bool | None = Field(alias="endTimeUnspecified")
    event_type: EventType = Field(alias="eventType")  # "default"
    extended_properties: dict[str, dict[str, str]] | None = Field(
        alias="extendedProperties"
    )
    guests_can_invite_others: bool | None = Field(alias="guestsCanInviteOthers")
    guests_can_modify: bool | None = Field(alias="guestsCanModify")
    guests_can_see_other_guests: bool | None = Field(alias="guestsCanSeeOtherGuests")
    hangout_link: str | None = Field(alias="hangoutLink")
    html_link: str = Field(alias="htmlLink")
    ical_uid: str = Field(alias="iCalUID")
    kind: Literal["calendar#event"]
    locked: bool | None
    organizer: dict[str, str | bool]
    original_start_time: dict[str, str] | None = Field(alias="originalStartTime")
    private_copy: bool | None = Field(alias="privateCopy")
    recurrence: list[str] | None
    recurring_event_id: str | None = Field(alias="recurringEventId")
    reminders: dict[str, bool | dict[str, str | int]]
    sequence: int
    source: dict[str, str] | None
    start: _StartEndDatetime
    status: Literal["cancelled", "confirmed", "tentative"] | None
    transparency: str | bool | None  # != transparent
    updated: datetime_
    visibility: Literal["default", "public", "private", "confidential"] | None

    calendar: Calendar

    def delete(self) -> None:
        """Deletes the event from the host calendar."""
        res = delete(
            f"{self.google_client.base_url}/calendars/"
            f"{self.calendar.id}/events/{self.id}",
            headers=self.google_client.request_headers,
        )

        res.raise_for_status()

    @property
    def end_datetime(self) -> datetime_:
        """End time of the event as a datetime object.

        Returns:
            datetime: the datetime at which this event ends/ed
        """
        end_datetime = self.end.datetime or datetime_.combine(
            self.end.date, datetime_.min.time()
        )

        if end_datetime.tzinfo is None:
            end_datetime = end_datetime.replace(tzinfo=self.end.timezone)

        return end_datetime

    @property
    def response_status(self) -> ResponseStatus:
        """User's response status.

        Returns:
            ResponseStatus: the response status for the authenticated user
        """
        for attendee in self.attendees:
            if attendee.get("self") is True:
                return ResponseStatus(attendee.get("responseStatus", "unknown"))

        # Own events don't always have attendees
        if self.creator.get("self") is True:
            return ResponseStatus.ACCEPTED

        return ResponseStatus("unknown")

    @property
    def start_datetime(self) -> datetime_:
        """Start time of the event as a datetime object.

        Returns:
            datetime: the datetime at which this event starts/ed
        """
        start_datetime = self.start.datetime or datetime_.combine(
            self.start.date, datetime_.min.time()
        )

        if start_datetime.tzinfo is None:
            start_datetime = start_datetime.replace(tzinfo=self.start.timezone)

        return start_datetime

    def __lt__(self, other: Event) -> bool:
        """Compares two events by their start time (or name)."""
        if self.start_datetime == other.start_datetime:
            return self.summary.lower() < other.summary.lower()

        return self.start_datetime < other.start_datetime

    def __gt__(self, other: Event) -> bool:
        """Compares two events by their start time (or name)."""
        if self.start_datetime == other.start_datetime:
            return self.summary.lower() > other.summary.lower()

        return self.start_datetime > other.start_datetime

    def __str__(self) -> str:
        """Returns the event's summary."""
        try:
            return (
                f"{self.summary} ("
                f"{self.start_datetime.strftime('%Y-%m-%d %H:%M:%S')} - "
                f"{self.end_datetime.strftime('%Y-%m-%d %H:%M:%S')})"
            )
        except AttributeError:
            return self.summary + dumps(self.start)


GoogleCalendarEntityJson: TypeAlias = CalendarJson | EventJson


class GoogleCalendarClient(GoogleClient[GoogleCalendarEntityJson]):
    """Custom client specifically for Google's Calendar API."""

    BASE_URL = "https://www.googleapis.com/calendar/v3"

    DATE_FORMAT = "%Y-%m-%d"
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%Z"

    DEFAULT_SCOPE = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        scopes: list[str] | None = None,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
    ):
        super().__init__(
            base_url=self.BASE_URL,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes or self.DEFAULT_SCOPE,
            log_requests=log_requests,
            creds_cache_path=creds_cache_path,
        )

        self._primary_calendar: Calendar | None = None

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
            start_params["dateTime"] = start_datetime.strftime(
                GoogleCalendarClient.DATETIME_FORMAT
            )
        elif isinstance(start_datetime, date_):
            start_params["date"] = start_datetime.strftime(
                GoogleCalendarClient.DATE_FORMAT
            )
        else:
            raise TypeError("`start_datetime` must be either a date or a datetime")

        end_params = {
            "timeZone": tz,
        }

        if isinstance(end_datetime, datetime_):
            end_params["dateTime"] = end_datetime.strftime(
                GoogleCalendarClient.DATETIME_FORMAT
            )
        elif isinstance(end_datetime, date_):
            end_params["date"] = end_datetime.strftime(GoogleCalendarClient.DATE_FORMAT)
        else:
            raise TypeError("`end_datetime` must be either a date or a datetime")

        res = self._post(
            f"/calendars/{calendar.id}/events",
            json={
                "summary": summary,
                "start": start_params,
                "end": end_params,
                **(extra_params or {}),
            },
        )

        return Event.from_json_response(
            res.json(), calendar=calendar, google_client=self
        )

    def delete_event(self, event_id: str, calendar: Calendar | None = None) -> None:
        """Deletes an event from a calendar.

        Args:
            event_id (str): the ID of the event to delete
            calendar (Calendar): the calendar being updated
        """
        calendar = calendar or self.primary_calendar

        res = delete(
            f"{self.base_url}/calendars/{calendar.id}/events/{event_id}",
            headers=self.request_headers,
        )

        res.raise_for_status()

    def get_event_by_id(self, event_id: str, calendar: Calendar | None = None) -> Event:
        """Get a specific event by ID.

        Args:
            event_id (str): the ID of the event to delete
            calendar (Calendar): the calendar being updated

        Returns:
            Event: an Event instance with all relevant attributes
        """
        calendar = calendar or self.primary_calendar

        return Event.from_json_response(
            self.get_json_response(f"/calendars/{calendar.id}/events/{event_id}"),
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
                f"{self.base_url}/users/me/calendarList",
            )
        ]

    @property
    def primary_calendar(self) -> Calendar:
        """Primary calendar for the user.

        Returns:
            Calendar: the current user's primary calendar
        """
        if not self._primary_calendar:
            self._primary_calendar = Calendar.from_json_response(
                self.get_json_response("/calendars/primary", params={"pageSize": None}),
                google_client=self,
            )

        return self._primary_calendar


GoogleCalendarEntity.update_forward_refs()
Calendar.update_forward_refs()
Event.update_forward_refs()
