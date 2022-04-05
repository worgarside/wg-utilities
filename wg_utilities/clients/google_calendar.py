"""Custom client for interacting with Google's Drive API"""

from datetime import datetime, timedelta, date
from enum import Enum
from json import dumps
from typing import List  # pylint: disable=unused-import

from pytz import timezone, UTC
from tzlocal import get_localzone

from wg_utilities.clients._generic import GoogleClient


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

    def __init__(self, json=None, *, google_client=None):
        self._json = json or {}
        self.google_client = google_client

    @property
    def id(self):
        """
        Returns:
            str: identifier of the entity
        """
        return self._json.get("id")

    @property
    def kind(self):
        """
        Returns:
            str: type of the resource (e.g. "calendar#calendar", "calendar#event")
        """
        return self._json.get("kind")

    @property
    def etag(self):
        """
        Returns:
            str: ETag of the resource
        """
        return self._json.get("etag")

    @property
    def summary(self):
        """
        Returns:
            str: title of the entity
        """
        return self._json.get("summary")

    @property
    def description(self):
        """
        Returns:
            str: description of the calendar. Optional
        """
        return self._json.get("description")

    @property
    def location(self):
        """
        Returns:
            str: geographic location of the calendar as free-form text. Optional
        """
        return self._json.get("location")


class Event(_GoogleCalendarEntity):
    """Class for Google Calendar events"""

    def __init__(self, json=None, *, calendar, google_client=None):
        super().__init__(json, google_client=google_client)
        self._json = json or {}
        self.google_client = google_client
        self.calendar = calendar

    def delete(self):
        """Deletes the event from the host calendar"""

        res = self.google_client.session.delete(
            f"{self.google_client.BASE_URL}/calendars/"
            f"{self.calendar.id}/events/{self.id}"
        )

        res.raise_for_status()

    @property
    def attachments(self):
        """
        Returns:
            list: file attachments for the event (max 25)
        """
        return self._json.get("attachments")

    @property
    def attendees(self):
        """
        Returns:
            list: the attendees of the event
        """
        return self._json.get("attendees", [])

    @property
    def attendees_omitted(self):
        """
        Returns:
            bool: whether attendees may have been omitted from the event's
             representation. When retrieving an event, this may be due to a restriction
             specified by the maxAttendee query parameter
        """
        return self._json.get("attendeesOmitted")

    @property
    def color_id(self):
        """
        Returns:
            str:the color of the event. This is an ID referring to an entry in the
             event section of the colors definition
        """
        return self._json.get("colorId")

    @property
    def conference_data(self):
        """
        Returns:
            dict: the conference-related information, such as details of a Google Meet
             conference
        """
        return self._json.get("conferenceData")

    @property
    def created(self):
        """
        Returns:
            datetime: creation time of the event (as a RFC3339 timestamp)
        """
        return self._json.get("created")

    @property
    def creator(self):
        """
        Returns:
            dict: the creator of the event
        """
        return self._json.get("creator")

    @property
    def description(self):
        """
        Returns:
            str: description of the event; can contain HTML
        """
        return self._json.get("description")

    @property
    def end(self):
        """
        Returns:
            dict: the (exclusive) end time of the event. For a recurring event, this
             is the end time of the first instance
        """
        return self._json.get("end")

    @property
    def end_datetime(self):
        """
        Returns:
            datetime: the datetime at which this event ends/ed
        """
        end_datetime = None

        if end_datetime_str := self._json.get("end", {}).get("dateTime"):
            end_datetime = datetime.strptime(
                end_datetime_str,
                self.DATETIME_FORMAT,
            )

        if end_date_str := self._json.get("end", {}).get("date"):
            end_datetime = datetime.strptime(
                end_date_str,
                self.DATE_FORMAT,
            )

        if end_datetime and end_datetime.tzinfo is None:
            end_datetime = end_datetime.replace(
                tzinfo=timezone(self._json.get("end", {}).get("timeZone", "UTC"))
            )

        return end_datetime

    @property
    def end_time_unspecified(self):
        """
        Returns:
            bool: whether the end time is actually unspecified
        """
        return self._json.get("endTimeUnspecified")

    @property
    def event_type(self):
        """
        Returns:
            EventType: specific type of the event
        """
        return EventType(self._json.get("eventType", "default"))

    @property
    def extended_properties(self):
        """
        Returns:
            dict: extended properties of the event
        """
        return self._json.get("extendedProperties")

    @property
    def guests_can_invite_others(self):
        """
        Returns:
            bool: whether attendees other than the organizer can invite others to the
             event
        """
        return self._json.get("guestsCanInviteOthers")

    @property
    def guests_can_modify(self):
        """
        Returns:
            bool: whether attendees other than the organizer can modify the event
        """
        return self._json.get("guestsCanModify")

    @property
    def guests_can_see_other_guests(self):
        """
        Returns:
            bool: whether attendees other than the organizer can see who the event's
             attendees are
        """
        return self._json.get("guestsCanSeeOtherGuests")

    @property
    def hangout_link(self):
        """
        Returns:
            str: an absolute link to the Google Hangout associated with this event
        """
        return self._json.get("hangoutLink")

    @property
    def html_link(self):
        """
        Returns:
            str: an absolute link to this event in the Google Calendar Web UI
        """
        return self._json.get("htmlLink")

    @property
    def ical_uid(self):
        """
        Returns:
            str: event unique identifier as defined in RFC5545. It is used to uniquely
             identify events across calendaring systems
        """
        return self._json.get("iCalUID")

    @property
    def locked(self):
        """
        Returns:
            bool: whether this is a locked event copy where no changes can be made to
             the main event fields "summary", "description", "location", "start", "end"
             or "recurrence"
        """
        return self._json.get("locked")

    @property
    def organizer(self):
        """
        Returns:
            dict: the organizer of the event
        """
        return self._json.get("organizer")

    @property
    def original_start_time(self):
        """
        Returns:
            dict: for an instance of a recurring event, this is the time at which this
             event would start according to the recurrence data in the recurring event
             identified by recurringEventId
        """
        return self._json.get("originalStartTime")

    @property
    def private_copy(self):
        """
        Returns:
            bool: if set to True, Event propagation is disabled
        """
        return self._json.get("privateCopy")

    @property
    def recurrence(self):
        """
        Returns:
            list: list of RRULE, EXRULE, RDATE and EXDATE lines for a recurring event,
             as specified in RFC5545
        """
        return self._json.get("recurrence")

    @property
    def recurring_event_id(self):
        """
        Returns:
            str: for an instance of a recurring event, this is the id of the recurring
             event to which this instance belongs
        """
        return self._json.get("recurringEventId")

    @property
    def reminders(self):
        """
        Returns:
            dict: information about the event's reminders for the authenticated user
        """
        return self._json.get("reminders")

    @property
    def response_status(self):
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
    def sequence(self):
        """
        Returns:
            int: sequence number as per iCalendar
        """
        return self._json.get("sequence")

    @property
    def source(self):
        """
        Returns:
            dict: source from which the event was created
        """
        return self._json.get("source")

    @property
    def start(self):
        """
        Returns:
            dict: the (inclusive) start time of the event; for a recurring event, this
             is the start time of the first instance
        """
        return self._json.get("start")

    @property
    def start_datetime(self):
        """
        Returns:
            datetime: the datetime at which this event starts/ed
        """
        start_datetime = None

        if start_datetime_str := self._json.get("start", {}).get("dateTime"):
            start_datetime = datetime.strptime(
                start_datetime_str,
                self.DATETIME_FORMAT,
            )

        if start_date_str := self._json.get("start", {}).get("date"):
            start_datetime = datetime.strptime(
                start_date_str,
                self.DATE_FORMAT,
            )

        if start_datetime and start_datetime.tzinfo is None:
            start_datetime = start_datetime.replace(
                tzinfo=timezone(self._json.get("start", {}).get("timeZone", "UTC"))
            )

        return start_datetime

    @property
    def status(self):
        """
        Returns:
            str: status of the event
        """
        return self._json.get("status")

    @property
    def transparency(self):
        """
        Returns:
            str: whether the event blocks time on the calendar
        """
        return self._json.get("transparency")

    @property
    def updated(self):
        """
        Returns:
            datetime: last modification time of the event
        """
        if updated_str := self._json.get("updated"):
            return datetime.strptime(updated_str, self.DATETIME_FORMAT)

        return None

    @property
    def visibility(self):
        """
        Returns:
            str: visibility of the event
        """
        return self._json.get("visibility")

    def __lt__(self, other):
        if self.start_datetime == other.start_datetime:
            return self.summary.lower() < other.summary.lower()

        return self.start_datetime < other.start_datetime

    def __gt__(self, other):
        if self.start_datetime == other.start_datetime:
            return self.summary.lower() > other.summary.lower()

        return self.start_datetime > other.start_datetime

    def __str__(self):
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

    def get_events(
        self,
        page_size=2500,
        order_by="updated",
        from_datetime=None,
        to_datetime=None,
        combine_recurring_events=False,
    ):
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
            Event(item, calendar=self, google_client=self.google_client)
            for item in self.google_client.get_items(
                f"{self.google_client.BASE_URL}/calendars/{self.id}/events",
                params=params,
            )
        ]

    @property
    def time_zone(self):
        """
        Returns:
            str: the time zone of the calendar, formatted as an IANA Time Zone
             Database name, e.g. "Europe/Zurich". Optional
        """
        return self._json.get("timeZone")

    @property
    def conference_properties(self):
        """
        Returns:
            dict: Conferencing properties for this calendar, for example what types
             of conferences are allowed
        """
        return self._json.get("conferenceProperties")

    def __str__(self):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._primary_calendar = None

    def create_event(
        self,
        summary,
        start_datetime,
        end_datetime,
        tz=None,
        calendar=None,
        extra_params=None,
    ):
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

        return Event(res.json(), calendar=calendar, google_client=self)

    def delete_event(self, event_id, calendar=None):
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

    def get_event(self, event_id, calendar=None):
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

        return Event(res.json(), calendar=calendar, google_client=self)

    @property
    def calendar_list(self):
        """
        Returns:
            list: a list of Calendar instances that the user has access to
        """
        return [
            Calendar(cal_json, google_client=self)
            for cal_json in self.get_items(
                f"{self.BASE_URL}/users/me/calendarList",
            )
        ]

    @property
    def primary_calendar(self):
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
