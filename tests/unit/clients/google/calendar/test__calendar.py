"""Unit Tests for `wg_utilities.clients.google_calendar.Calendar`."""
from __future__ import annotations

from datetime import datetime, tzinfo
from json import loads
from unittest.mock import patch

from freezegun import freeze_time
from pytest import mark
from pytz import timezone

from conftest import read_json_file
from wg_utilities.clients.google_calendar import Calendar, Event, GoogleCalendarClient


def test_instantiation(google_calendar_client: GoogleCalendarClient) -> None:
    """Test that the `Calendar` class can be instantiated."""

    calendar_json = read_json_file(
        "v3/calendars/primary.json", host_name="google/calendar"
    )

    calendar = Calendar.from_json_response(
        calendar_json,
        google_client=google_calendar_client,
    )

    assert isinstance(calendar, Calendar)
    # the `loads` is to convert tzinfo objects to strings
    assert loads(calendar.json()) == calendar_json
    assert calendar.google_client == google_calendar_client


def test_timezone_tzinfo_conversion(
    google_calendar_client: GoogleCalendarClient,
) -> None:
    """Test that the `timeZone` field validator successfully converts str to tzinfo."""

    calendar_json = read_json_file(
        "v3/calendars/primary.json", host_name="google/calendar"
    )

    assert calendar_json["timeZone"] == "Europe/London"

    calendar = Calendar.from_json_response(
        calendar_json,
        google_client=google_calendar_client,
    )

    assert calendar.timezone == timezone("Europe/London")
    assert isinstance(calendar.timezone, tzinfo)
    assert calendar.dict()["timeZone"] == timezone("Europe/London")
    assert "timezone" not in calendar.dict()


def test_get_event_by_id(calendar: Calendar) -> None:
    """Test that the `get_event_by_id` method returns an `Event` object."""

    event = calendar.get_event_by_id("jt171go86rkonwwkyd5q7m84mm")

    assert isinstance(event, Event)
    assert event.id == "jt171go86rkonwwkyd5q7m84mm"
    assert event.calendar == calendar


def test_get_events_method(calendar: Calendar) -> None:
    """Test that the `get_events` method returns a list of `Event` objects."""

    events = calendar.get_events()

    assert isinstance(events, list)
    assert all(isinstance(event, Event) for event in events)
    assert all(event.calendar == calendar for event in events)
    assert len(events) == 1011


@mark.parametrize(  # type: ignore[misc]
    ["from_datetime", "to_datetime", "day_limit", "expected_params"],
    (
        (
            datetime(1996, 4, 20, 12, 30, 45),
            datetime(1997, 11, 15, 12, 30, 45),
            None,
            {
                "maxResults": 500,
                "orderBy": "updated",
                "singleEvents": "True",
                "timeMin": "1996-04-20T12:30:45+00:00",
                "timeMax": "1997-11-15T12:30:45+00:00",
            },
        ),
        (
            datetime(1996, 4, 20, 12, 30, 45),
            None,
            None,
            {
                "maxResults": 500,
                "orderBy": "updated",
                "singleEvents": "True",
                "timeMin": "1996-04-20T12:30:45+00:00",
                "timeMax": "2022-01-01T00:00:00+00:00",
            },
        ),
        (
            None,
            datetime(1997, 11, 15, 12, 30, 45),
            None,
            {
                "maxResults": 500,
                "orderBy": "updated",
                "singleEvents": "True",
                "timeMin": "1997-08-17T12:30:45+00:00",
                "timeMax": "1997-11-15T12:30:45+00:00",
            },
        ),
        (
            None,
            None,
            None,
            {
                "maxResults": 500,
                "orderBy": "updated",
                "singleEvents": "True",
            },
        ),
        (
            datetime(1996, 4, 20, 12, 30, 45),
            datetime(1997, 11, 15, 12, 30, 45),
            14,
            {
                "maxResults": 500,
                "orderBy": "updated",
                "singleEvents": "True",
                "timeMin": "1996-04-20T12:30:45+00:00",
                "timeMax": "1996-05-04T12:30:45+00:00",
            },
        ),
        (
            datetime(1996, 4, 20, 12, 30, 45),
            None,
            14,
            {
                "maxResults": 500,
                "orderBy": "updated",
                "singleEvents": "True",
                "timeMin": "1996-04-20T12:30:45+00:00",
                "timeMax": "1996-05-04T12:30:45+00:00",
            },
        ),
        (
            None,
            datetime(1997, 11, 15, 12, 30, 45),
            14,
            {
                "maxResults": 500,
                "orderBy": "updated",
                "singleEvents": "True",
                "timeMin": "1997-11-01T12:30:45+00:00",
                "timeMax": "1997-11-15T12:30:45+00:00",
            },
        ),
        (
            None,
            None,
            14,
            {
                "maxResults": 500,
                "orderBy": "updated",
                "singleEvents": "True",
                "timeMin": "2021-12-18T00:00:00+00:00",
                "timeMax": "2022-01-01T00:00:00+00:00",
            },
        ),
    ),
)
def test_get_events_datetime_parameters(
    calendar: Calendar,
    from_datetime: datetime | None,
    day_limit: int | None,
    to_datetime: datetime | None,
    expected_params: dict[str, str],
) -> None:
    """Test that various to/from datetime parameters are handled correctly."""

    with freeze_time("2022-01-01T00:00:00"), patch.object(
        calendar.google_client, "get_items"
    ) as mock_get_items:
        calendar.get_events(
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            day_limit=day_limit,
        )

    mock_get_items.assert_called_once_with(
        "https://www.googleapis.com/calendar/v3/calendars/google-user@gmail.com/events",
        params=expected_params,
    )


def test_str_method(calendar: Calendar) -> None:
    """Test that the `__str__` method returns a string repr of the calendar."""

    assert str(calendar) == calendar.summary
