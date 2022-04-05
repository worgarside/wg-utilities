"""Custom client for interacting with Google's Drive API"""

from datetime import datetime, timedelta
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
    UNCONFIRMED = "needsAction"
    UNKNOWN = "unknown"


class _GoogleCalendarEntity:
    """

    Args:
        json (dict): the JSON from Google's API
        google_client (GoogleCalendarClient): a Google client for use in other requests
    """

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
            str: title of the calendar
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
            datetime:
        """
        return self._json.get("created")

    @property
    def creator(self):
        """
        Returns:
            dict:
        """
        return self._json.get("creator")

    @property
    def description(self):
        """
        Returns:
            str:
        """
        return self._json.get("description")

    @property
    def end(self):
        """
        Returns:
            dict:
        """
        return self._json.get("end")

    @property
    def end_datetime(self):
        """
        Returns:
            datetime: the datetime at which this event ends/ed
        """
        if end_datetime_str := self._json.get("end", {}).get("dateTime"):
            return datetime.strptime(
                end_datetime_str,
                self.DATETIME_FORMAT,
            ).replace(tzinfo=timezone(self._json.get("end", {}).get("timeZone", "UTC")))

        return None

    @property
    def end_time_unspecified(self):
        """
        Returns:
            bool:
        """
        return self._json.get("endTimeUnspecified")

    @property
    def etag(self):
        """
        Returns:
            str:
        """
        return self._json.get("etag")

    @property
    def event_type(self):
        """
        Returns:
            str:
        """
        return self._json.get("eventType")

    @property
    def extended_properties(self):
        """
        Returns:
            dict:
        """
        return self._json.get("extendedProperties")

    @property
    def gadget(self):
        """
        Returns:
            dict:
        """
        return self._json.get("gadget")

    @property
    def guests_can_invite_others(self):
        """
        Returns:
            bool:
        """
        return self._json.get("guestsCanInviteOthers")

    @property
    def guests_can_modify(self):
        """
        Returns:
            bool:
        """
        return self._json.get("guestsCanModify")

    @property
    def guests_can_see_other_guests(self):
        """
        Returns:
            bool:
        """
        return self._json.get("guestsCanSeeOtherGuests")

    @property
    def hangout_link(self):
        """
        Returns:
            str:
        """
        return self._json.get("hangoutLink")

    @property
    def html_link(self):
        """
        Returns:
            str:
        """
        return self._json.get("htmlLink")

    @property
    def ical_uid(self):
        """
        Returns:
            str:
        """
        return self._json.get("iCalUID")

    @property
    def id(self):
        """
        Returns:
            str:
        """
        return self._json.get("id")

    @property
    def kind(self):
        """
        Returns:
            str:
        """
        return self._json.get("kind")

    @property
    def location(self):
        """
        Returns:
            str:
        """
        return self._json.get("location")

    @property
    def locked(self):
        """
        Returns:
            bool:
        """
        return self._json.get("locked")

    @property
    def organizer(self):
        """
        Returns:
            dict:
        """
        return self._json.get("organizer")

    @property
    def original_start_time(self):
        """
        Returns:
            dict:
        """
        return self._json.get("originalStartTime")

    @property
    def private_copy(self):
        """
        Returns:
            bool:
        """
        return self._json.get("privateCopy")

    @property
    def recurrence(self):
        """
        Returns:
            list:
        """
        return self._json.get("recurrence")

    @property
    def recurring_event_id(self):
        """
        Returns:
            str:
        """
        return self._json.get("recurringEventId")

    @property
    def reminders(self):
        """
        Returns:
            dict:
        """
        return self._json.get("reminders")

    @property
    def response_status(self):
        """
        Returns:
            ResponseStatus: the response status for the current user
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
            int:
        """
        return self._json.get("sequence")

    @property
    def source(self):
        """
        Returns:
            dict:
        """
        return self._json.get("source")

    @property
    def start(self):
        """
        Returns:
            dict:
        """
        return self._json.get("start")

    @property
    def start_datetime(self):
        """
        Returns:
            datetime: the datetime at which this event starts/ed
        """
        if start_datetime_str := self._json.get("start", {}).get("dateTime"):
            return datetime.strptime(start_datetime_str, self.DATETIME_FORMAT,).replace(
                tzinfo=timezone(self._json.get("start", {}).get("timeZone", "UTC"))
            )

        return None

    @property
    def status(self):
        """
        Returns:
            str:
        """
        return self._json.get("status")

    @property
    def summary(self):
        """
        Returns:
            str:
        """
        return self._json.get("summary")

    @property
    def transparency(self):
        """
        Returns:
            str:
        """
        return self._json.get("transparency")

    @property
    def updated(self):
        """
        Returns:
            datetime:
        """
        return self._json.get("updated")

    @property
    def visibility(self):
        """
        Returns:
            str:
        """
        return self._json.get("visibility")

    def __str__(self):
        return dumps(self._json, indent=4)


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
        tz=str(get_localzone()),
        calendar=None,
        extra_params=None,
    ):
        """Create an event

        Args:
            summary (str): the summary (title) of the event
            start_datetime (datetime): when the event starts
            end_datetime (datetime): when the event ends
            tz (str): the timezone which the event is in (IANA database name)
            calendar (Calendar): the calendar to add the event to
            extra_params (dict): any extra params to pass in the request

        Returns:
            Event: a new event instance, fresh out of the oven
        """

        calendar = calendar or self.primary_calendar

        res = self.session.post(
            f"{self.BASE_URL}/calendars/{calendar.id}/events",
            json={
                "summary": summary,
                "start": {
                    "dateTime": start_datetime.strftime(
                        _GoogleCalendarEntity.DATETIME_FORMAT
                    ),
                    "timeZone": tz,
                },
                "end": {
                    "dateTime": end_datetime.strftime(
                        _GoogleCalendarEntity.DATETIME_FORMAT
                    ),
                    "timeZone": tz,
                },
                **(extra_params or {}),
            },
        )

        res.raise_for_status()

        return Event(res.json(), calendar=calendar, google_client=self)

    def delete_event(self, calendar, event_id):
        """Deletes an event from a calendar

        Args:
            calendar (Calendar): the calendar being updated
            event_id (str): the ID of the event to delete
        """

        res = self.session.delete(
            f"{self.BASE_URL}/calendars/{calendar.id}/events/{event_id}"
        )

        res.raise_for_status()

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
