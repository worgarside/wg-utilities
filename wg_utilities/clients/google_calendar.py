"""Custom client for interacting with Google's Drive API"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import Enum
from json import dumps
from logging import Logger
from typing import Any, Iterable, Literal, cast

from pytz import UTC, timezone
from tzlocal import get_localzone

from wg_utilities.clients._google import GoogleClient, _GoogleEntityInfo


class _GoogleCalendarEntityInfo(_GoogleEntityInfo):
    description: str
    etag: str
    id: str
    location: str
    summary: str


class _CalendarInfo(_GoogleCalendarEntityInfo):
    kind: Literal["calendar#calendar"]
    timeZone: str
    conferenceProperties: dict[
        Literal["allowedConferenceSolutionTypes"],
        list[Literal["eventHangout", "eventNamedHangout", "hangoutsMeet"]],
    ]


class _EventInfo(_GoogleCalendarEntityInfo):
    attachments: list[dict[str, str]]
    attendees: list[dict[str, str | bool]]
    attendeesOmitted: bool | None
    colorId: str
    conferenceData: dict[str, str | dict[str, str]]
    created: str
    creator: dict[str, str | bool]
    end: dict[str, str]
    endTimeUnspecified: bool
    eventType: str
    extendedProperties: dict[str, dict[str, str]]
    guestsCanInviteOthers: bool | None
    guestsCanModify: bool | None
    guestsCanSeeOtherGuests: bool | None
    hangoutLink: str
    htmlLink: str
    iCalUID: str
    kind: Literal["calendar#event"]
    locked: bool
    organizer: dict[str, str | bool]
    originalStartTime: dict[str, str]
    privateCopy: bool | None
    recurrence: list[str]
    recurringEventId: str
    reminders: dict[str, bool | dict[str, str | int]]
    sequence: int
    source: dict[str, str]
    start: dict[str, str]
    status: Literal["cancelled", "confirmed", "tentative"] | None
    transparency: str | None
    updated: str
    visibility: Literal["default", "public", "private", "confidential"]


class ResponseStatus(Enum):
    """Enumeration for event attendee response statuses"""

    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    UNCONFIRMED = "needsAction"
    UNKNOWN = "unknown"


class EventType(Enum):
    """Enumeration for event types"""

    DEFAULT = "default"
    FOCUS_TIME = "focusTime"
    OUT_OF_OFFICE = "outOfOffice"


class _GoogleCalendarEntity:
    """

    Args:
        json (dict): the JSON from Google's API
        google_client (GoogleCalendarClient): a Google client for use in other requests
    """

    DATE_FORMAT = "%Y-%m-%d"
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

    def __init__(
        self,
        *,
        json: _CalendarInfo | _EventInfo,
        google_client: GoogleCalendarClient,
    ):
        self.json = json
        self.google_client = google_client

    @property
    def id(self) -> str:
        """
        Returns:
            str: identifier of the entity
        """
        return self.json["id"]

    @property
    def kind(self) -> str:
        """
        Returns:
            str: type of the resource (e.g. "calendar#calendar", "calendar#event")
        """
        return self.json["kind"]

    @property
    def etag(self) -> str:
        """
        Returns:
            str: ETag of the resource
        """
        return self.json["etag"]

    @property
    def summary(self) -> str:
        """
        Returns:
            str: title of the entity
        """
        return self.json.get("summary", "(No Title)")

    @property
    def description(self) -> str | None:
        """
        Returns:
            str: description of the calendar. Optional
        """
        return self.json.get("description")

    @property
    def location(self) -> str | None:
        """
        Returns:
            str: geographic location of the calendar as free-form text. Optional
        """
        return self.json.get("location")


class Event(_GoogleCalendarEntity):
    """Class for Google Calendar events"""

    json: _EventInfo

    def __init__(
        self,
        *,
        json: _EventInfo,
        google_client: GoogleCalendarClient,
        calendar: Calendar,
    ):
        super().__init__(json=json, google_client=google_client)
        self.calendar = calendar

    def delete(self) -> None:
        """Deletes the event from the host calendar"""

        res = self.google_client.session.delete(
            f"{self.google_client.BASE_URL}/calendars/"
            f"{self.calendar.id}/events/{self.id}"
        )

        res.raise_for_status()

    @property
    def attachments(self) -> list[dict[str, str]] | None:
        """
        Returns:
            list: file attachments for the event (max 25)
        """
        return self.json.get("attachments")

    @property
    def attendees(self) -> list[dict[str, Any]]:
        """
        Returns:
            list: the attendees of the event
        """
        return self.json.get("attendees", [])

    @property
    def attendees_omitted(self) -> bool | None:
        """
        Returns:
            bool: whether attendees may have been omitted from the event's
             representation. When retrieving an event, this may be due to a restriction
             specified by the maxAttendee query parameter
        """
        return self.json.get("attendeesOmitted")

    @property
    def color_id(self) -> str | None:
        """
        Returns:
            str:the color of the event. This is an ID referring to an entry in the
             event section of the colors definition
        """
        return self.json.get("colorId")

    @property
    def conference_data(self) -> dict[str, str | dict[str, str]] | None:
        """
        Returns:
            dict: the conference-related information, such as details of a Google Meet
             conference
        """
        return self.json.get("conferenceData")

    @property
    def created(self) -> str | None:
        """
        Returns:
            dtr: creation time of the event (as a RFC3339 timestamp)
        """
        return self.json.get("created")

    @property
    def creator(self) -> dict[str, str | bool]:
        """
        Returns:
            dict: the creator of the event
        """
        return self.json.get("creator")  # type: ignore[return-value]

    @property
    def description(self) -> str:
        """
        Returns:
            str: description of the event; can contain HTML
        """
        return self.json.get("description", "")

    @property
    def end(self) -> dict[str, str]:
        """
        Returns:
            dict: the (exclusive) end time of the event. For a recurring event, this
             is the end time of the first instance
        """
        return self.json.get("end")  # type: ignore[return-value]

    @property
    def end_datetime(self) -> datetime:
        """
        Returns:
            datetime: the datetime at which this event ends/ed

        Raises:
            ValueError: if no end datetime info found
        """
        if end_datetime_str := self.json.get("end", {}).get("dateTime"):
            end_datetime = datetime.strptime(
                end_datetime_str,
                self.DATETIME_FORMAT,
            )
        elif end_date_str := self.json.get("end", {}).get("date"):
            end_datetime = datetime.strptime(
                end_date_str,
                self.DATE_FORMAT,
            )
        else:
            raise ValueError("No end datetime info found for Event")

        if end_datetime.tzinfo is None:
            end_datetime = end_datetime.replace(
                tzinfo=timezone(self.json.get("end", {}).get("timeZone", "UTC"))
            )

        return end_datetime

    @property
    def end_time_unspecified(self) -> bool | None:
        """
        Returns:
            bool: whether the end time is actually unspecified
        """
        return self.json.get("endTimeUnspecified")

    @property
    def event_type(self) -> EventType:
        """
        Returns:
            EventType: specific type of the event
        """
        return EventType(self.json.get("eventType", "default"))

    @property
    def extended_properties(self) -> dict[str, dict[str, str]] | None:
        """
        Returns:
            dict: extended properties of the event
        """
        return self.json.get("extendedProperties")

    @property
    def guests_can_invite_others(self) -> bool | None:
        """
        Returns:
            bool: whether attendees other than the organizer can invite others to the
             event
        """
        return self.json.get("guestsCanInviteOthers")

    @property
    def guests_can_modify(self) -> bool | None:
        """
        Returns:
            bool: whether attendees other than the organizer can modify the event
        """
        return self.json.get("guestsCanModify")

    @property
    def guests_can_see_other_guests(self) -> bool | None:
        """
        Returns:
            bool: whether attendees other than the organizer can see who the event's
             attendees are
        """
        return self.json.get("guestsCanSeeOtherGuests")

    @property
    def hangout_link(self) -> str | None:
        """
        Returns:
            str: an absolute link to the Google Hangout associated with this event
        """
        return self.json.get("hangoutLink")

    @property
    def html_link(self) -> str | None:
        """
        Returns:
            str: an absolute link to this event in the Google Calendar Web UI
        """
        return self.json.get("htmlLink")

    @property
    def ical_uid(self) -> str | None:
        """
        Returns:
            str: event unique identifier as defined in RFC5545. It is used to uniquely
             identify events across calendaring systems
        """
        return self.json.get("iCalUID")

    @property
    def locked(self) -> bool | None:
        """
        Returns:
            bool: whether this is a locked event copy where no changes can be made to
             the main event fields "summary", "description", "location", "start", "end"
             or "recurrence"
        """
        return self.json.get("locked")

    @property
    def organizer(self) -> dict[str, str | bool] | None:
        """
        Returns:
            dict: the organizer of the event
        """
        return self.json.get("organizer")

    @property
    def original_start_time(self) -> dict[str, str] | None:
        """
        Returns:
            dict: for an instance of a recurring event, this is the time at which this
             event would start according to the recurrence data in the recurring event
             identified by recurringEventId
        """
        return self.json.get("originalStartTime")

    @property
    def private_copy(self) -> bool | None:
        """
        Returns:
            bool: if set to True, Event propagation is disabled
        """
        return self.json.get("privateCopy")

    @property
    def recurrence(self) -> list[str] | None:
        """
        Returns:
            list: list of RRULE, EXRULE, RDATE and EXDATE lines for a recurring event,
             as specified in RFC5545
        """
        return self.json.get("recurrence")

    @property
    def recurring_event_id(self) -> str | None:
        """
        Returns:
            str: for an instance of a recurring event, this is the id of the recurring
             event to which this instance belongs
        """
        return self.json.get("recurringEventId")

    @property
    def reminders(self) -> dict[str, bool | dict[str, str | int]] | None:
        """
        Returns:
            dict: information about the event's reminders for the authenticated user
        """
        return self.json.get("reminders")

    @property
    def response_status(self) -> ResponseStatus:
        """
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
    def sequence(self) -> int | None:
        """
        Returns:
            int: sequence number as per iCalendar
        """
        return self.json.get("sequence")

    @property
    def source(self) -> dict[str, str] | None:
        """
        Returns:
            dict: source from which the event was created
        """
        return self.json.get("source")

    @property
    def start(self) -> dict[str, str] | None:
        """
        Returns:
            dict: the (inclusive) start time of the event; for a recurring event, this
             is the start time of the first instance
        """
        return self.json.get("start")

    @property
    def start_datetime(self) -> datetime:
        """
        Returns:
            datetime: the datetime at which this event starts/ed

        Raises:
            ValueError: if no start datetime info is available
        """

        if start_datetime_str := self.json.get("start", {}).get("dateTime"):
            start_datetime = datetime.strptime(
                start_datetime_str,
                self.DATETIME_FORMAT,
            )
        elif start_date_str := self.json.get("start", {}).get("date"):
            start_datetime = datetime.strptime(
                start_date_str,
                self.DATE_FORMAT,
            )
        else:
            raise ValueError("No start datetime info found for Event")

        if start_datetime.tzinfo is None:
            start_datetime = start_datetime.replace(
                tzinfo=timezone(self.json.get("start", {}).get("timeZone", "UTC"))
            )

        return start_datetime

    @property
    def status(self) -> Literal["cancelled", "confirmed", "tentative"] | None:
        """
        Returns:
            str: status of the event (e.g. "confirmed")
        """
        return self.json.get("status")

    @property
    def transparency(self) -> bool:
        """
        Returns:
            bool: whether the event blocks time on the calendar
        """
        return self.json.get("transparency") != "transparent"

    @property
    def updated(self) -> datetime | None:
        """
        Returns:
            datetime: last modification time of the event
        """
        if updated_str := self.json.get("updated"):
            return datetime.strptime(updated_str, self.DATETIME_FORMAT)

        return None

    @property
    def visibility(self) -> str | None:
        """
        Returns:
            str: visibility of the event
        """
        return self.json.get("visibility")

    def __lt__(self, other: Event) -> bool:
        if self.start_datetime == other.start_datetime:
            return self.summary.lower() < other.summary.lower()

        return self.start_datetime < other.start_datetime

    def __gt__(self, other: Event) -> bool:
        if self.start_datetime == other.start_datetime:
            return self.summary.lower() > other.summary.lower()

        return self.start_datetime > other.start_datetime

    def __str__(self) -> str:
        try:
            return (
                f"{self.summary} ("
                f"{self.start_datetime.strftime('%Y-%m-%d %H:%M:%S')} - "
                f"{self.end_datetime.strftime('%Y-%m-%d %H:%M:%S')})"
            )
        except AttributeError:
            return self.summary + dumps(self.start)


class Calendar(_GoogleCalendarEntity):
    """Class for Google calendar instances"""

    json: _CalendarInfo

    def get_events(
        self,
        page_size: int = 2500,
        order_by: Literal["updated", "startTime"] = "updated",
        from_datetime: datetime | None = None,
        to_datetime: datetime | None = None,
        combine_recurring_events: bool = False,
    ) -> list[Event]:
        """Retrieve events from the calendar according to a set of criteria

        Args:
            page_size (int): the number of records to return on a single response page
            order_by (Literal["updated", "startTime"]): the order of the events
             returned within the result
            from_datetime (datetime): lower bound (exclusive) for an event's end time
             to filter by
            to_datetime (datetime): upper bound (exclusive) for an event's start time
             to filter by
            combine_recurring_events (bool): whether to expand recurring events into
             instances and only return single one-off events and instances of recurring
             events, but not the underlying recurring events themselves

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
        if from_datetime or to_datetime:
            from_datetime = from_datetime or datetime.utcnow() - timedelta(days=90)
            to_datetime = to_datetime or datetime.utcnow()

            if from_datetime >= to_datetime:
                raise ValueError(
                    "If timeMax is set, timeMin must be smaller than timeMax, and vice"
                    " versa"
                )

            if from_datetime.tzinfo is None:
                from_datetime = from_datetime.replace(tzinfo=UTC)

            if to_datetime.tzinfo is None:
                to_datetime = to_datetime.replace(tzinfo=UTC)

            params["timeMin"] = from_datetime.strftime(self.DATETIME_FORMAT)
            params["timeMax"] = to_datetime.strftime(self.DATETIME_FORMAT)

        return [
            Event(json=item, calendar=self, google_client=self.google_client)
            for item in cast(
                Iterable[_EventInfo],
                self.google_client.get_items(
                    f"{self.google_client.BASE_URL}/calendars/{self.id}/events",
                    params=params,
                ),
            )
        ]

    @property
    def time_zone(self) -> str | None:
        """
        Returns:
            str: the time zone of the calendar, formatted as an IANA Time Zone
             Database name, e.g. "Europe/Zurich". Optional
        """
        return self.json.get("timeZone")

    @property
    def conference_properties(
        self,
    ) -> None | (
        dict[
            Literal["allowedConferenceSolutionTypes"],
            list[Literal["eventHangout", "eventNamedHangout", "hangoutsMeet"]],
        ]
    ):
        """
        Returns:
            dict: Conferencing properties for this calendar, for example what types
             of conferences are allowed
        """
        return self.json.get("conferenceProperties")

    def __str__(self) -> str:
        return self.summary


class GoogleCalendarClient(GoogleClient):
    """Custom client specifically for Google's Drive API

    Args:
        project (str): the name of the project which this client is being used for
        scopes (list): a list of scopes the client can be given
        client_id_json_path (str): the path to the `client_id.json` file downloaded
         from Google's API Console
        creds_cache_path (str): file path for where to cache credentials
        access_token_expiry_threshold (int): the threshold for when the access token is
         considered expired
        logger (RootLogger): a logger to use throughout the client functions
    """

    BASE_URL = "https://www.googleapis.com/calendar/v3"

    def __init__(
        self,
        project: str,
        scopes: list[str] | None = None,
        client_id_json_path: str | None = None,
        creds_cache_path: str | None = None,
        access_token_expiry_threshold: int = 60,
        logger: Logger | None = None,
    ):
        super().__init__(
            project=project,
            scopes=scopes,
            client_id_json_path=client_id_json_path,
            creds_cache_path=creds_cache_path,
            access_token_expiry_threshold=access_token_expiry_threshold,
            logger=logger,
        )

        self._primary_calendar: Calendar | None = None

    def create_event(
        self,
        summary: str,
        start_datetime: datetime | date,
        end_datetime: datetime | date,
        tz: str | None = None,
        calendar: Calendar | None = None,
        extra_params: dict[str, str] | None = None,
    ) -> Event:
        """Create an event

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

        if isinstance(start_datetime, datetime):
            start_params["dateTime"] = start_datetime.strftime(
                _GoogleCalendarEntity.DATETIME_FORMAT
            )
        elif isinstance(start_datetime, date):
            start_params["date"] = start_datetime.strftime(
                _GoogleCalendarEntity.DATE_FORMAT
            )
        else:
            raise TypeError("`start_datetime` must be either a date or a datetime")

        end_params = {
            "timeZone": tz,
        }

        if isinstance(end_datetime, datetime):
            end_params["dateTime"] = end_datetime.strftime(
                _GoogleCalendarEntity.DATETIME_FORMAT
            )
        elif isinstance(end_datetime, date):
            end_params["date"] = end_datetime.strftime(
                _GoogleCalendarEntity.DATE_FORMAT
            )
        else:
            raise TypeError("`end_datetime` must be either a date or a datetime")

        res = self.session.post(
            f"{self.BASE_URL}/calendars/{calendar.id}/events",
            json={
                "summary": summary,
                "start": start_params,
                "end": end_params,
                **(extra_params or {}),
            },
        )

        res.raise_for_status()

        return Event(json=res.json(), calendar=calendar, google_client=self)

    def delete_event(self, event_id: str, calendar: Calendar | None = None) -> None:
        """Deletes an event from a calendar

        Args:
            event_id (str): the ID of the event to delete
            calendar (Calendar): the calendar being updated
        """
        calendar = calendar or self.primary_calendar

        res = self.session.delete(
            f"{self.BASE_URL}/calendars/{calendar.id}/events/{event_id}"
        )

        res.raise_for_status()

    def get_event(self, event_id: str, calendar: Calendar | None = None) -> Event:
        """Get a specific event by ID

        Args:
            event_id (str): the ID of the event to delete
            calendar (Calendar): the calendar being updated

        Returns:
            Event: an Event instance with all relevant attributes
        """
        calendar = calendar or self.primary_calendar
        res = self.session.get(
            f"{self.BASE_URL}/calendars/{calendar.id}/events/{event_id}"
        )

        res.raise_for_status()

        return Event(json=res.json(), calendar=calendar, google_client=self)

    @property
    def calendar_list(self) -> list[Calendar]:
        """
        Returns:
            list: a list of Calendar instances that the user has access to
        """
        return [
            Calendar(json=cal_json, google_client=self)
            for cal_json in cast(
                Iterable[_CalendarInfo],
                self.get_items(
                    f"{self.BASE_URL}/users/me/calendarList",
                ),
            )
        ]

    @property
    def primary_calendar(self) -> Calendar:
        """
        Returns:
            Calendar: the current user's primary calendar
        """
        if not self._primary_calendar:
            self._primary_calendar = Calendar(
                json=self.session.get(f"{self.BASE_URL}/calendars/primary").json(),
                google_client=self,
            )

        return self._primary_calendar
