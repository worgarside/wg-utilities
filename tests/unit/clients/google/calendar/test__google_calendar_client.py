"""Unit tests for `wg_utilities.clients.google_calendar.GoogleCalendarClient`."""
from __future__ import annotations

from datetime import date, datetime, tzinfo
from http import HTTPStatus
from json import loads
from typing import Any
from unittest.mock import patch

from pytest import mark, raises
from pytz import timezone
from requests import HTTPError
from requests_mock import Mocker

from wg_utilities.clients import GoogleCalendarClient
from wg_utilities.clients.google_calendar import Calendar, Event, _StartEndDatetime
from wg_utilities.clients.oauth_client import OAuthCredentials


def test_instantiation(fake_oauth_credentials: OAuthCredentials) -> None:
    """Test that the `GoogleCalendarClient` class can be instantiated."""

    client = GoogleCalendarClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
        scopes=[
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
        ],
    )

    assert isinstance(client, GoogleCalendarClient)
    assert not hasattr(client, "_primary_calendar")


@mark.parametrize(
    (
        "summary",
        "start_datetime",
        "end_datetime",
        "tz",
        "calendar_arg",  # Not `calendar` as that's a fixture
        "extra_params",
    ),
    (
        (
            "Test Event 1",
            date(2021, 1, 1),
            date(2021, 1, 2),
            timezone("America/New_York"),
            None,
            {},
        ),
        (
            "Test Event 2",
            datetime(2021, 1, 1, 10, 30),
            date(2021, 1, 2),
            timezone("Europe/London"),
            None,
            {},
        ),
        (
            "Test Event 3",
            date(2021, 1, 2),
            datetime(2021, 1, 1, 10, 30),
            timezone("Africa/Johannesburg"),
            None,
            {},
        ),
        (
            "Test Event 4",
            date(2021, 1, 2),
            date(2021, 1, 2),
            timezone("Africa/Johannesburg"),
            Calendar.parse_obj(
                {
                    "id": "test-calendar-id",
                    "etag": "",
                    "summary": "",
                    "google_client": GoogleCalendarClient(
                        client_id="", client_secret=""
                    ),
                    "kind": "calendar#calendar",
                    "timeZone": "Africa/Johannesburg",
                    "conferenceProperties": {},
                }
            ),
            {},
        ),
        (
            "Test Event 5",
            date(2021, 1, 2),
            date(2021, 1, 2),
            timezone("Africa/Johannesburg"),
            Calendar.parse_obj(
                {
                    "id": "test-calendar-id",
                    "etag": "",
                    "summary": "",
                    "google_client": GoogleCalendarClient(
                        client_id="", client_secret=""
                    ),
                    "kind": "calendar#calendar",
                    "timeZone": "Africa/Johannesburg",
                    "conferenceProperties": {},
                }
            ),
            {
                "one": "one",
                "two": "two",
                "three": "three",
            },
        ),
    ),
)
def test_create_event_request(
    google_calendar_client: GoogleCalendarClient,
    event: Event,
    summary: str,
    start_datetime: datetime | date,
    end_datetime: datetime | date,
    tz: tzinfo,
    calendar_arg: Calendar | None,
    extra_params: dict[str, Any],
) -> None:
    """Test the `create_event` method makes the correct request."""

    if isinstance(start_datetime, datetime):
        start_params = {
            "timeZone": tz.tzname(None),
            "dateTime": start_datetime.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
    else:
        start_params = {
            "timeZone": tz.tzname(None),
            "date": start_datetime.isoformat(),
        }

    if isinstance(end_datetime, datetime):
        end_params = {
            "timeZone": tz.tzname(None),
            "dateTime": end_datetime.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
    else:
        end_params = {
            "timeZone": tz.tzname(None),
            "date": end_datetime.isoformat(),
        }

    # Preload the primary calendar so that the `create_event` doesn't log the wrong
    # call under `mock_post_json_response`
    _ = google_calendar_client.primary_calendar

    with patch.object(
        google_calendar_client, "post_json_response"
    ) as mock_post_json_response:
        mock_post_json_response.return_value = loads(event.json())

        google_calendar_client.create_event(
            summary=summary,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            tz=str(tz),
            calendar=calendar_arg,
            extra_params=extra_params,
        )

    mock_post_json_response.assert_called_once_with(
        "/".join(
            [
                "",
                "calendars",
                (calendar_arg or google_calendar_client.primary_calendar).id,
                "events",
            ]
        ),
        json={
            "summary": summary,
            "start": start_params,
            "end": end_params,
            **extra_params,
        },
        params={"maxResults": None},
    )


@mark.parametrize(
    (
        "summary",
        "start_datetime",
        "end_datetime",
        "tz",
        "calendar_arg",  # Not `calendar` as that's a fixture
        "extra_params",
    ),
    (
        (
            "Test Event 1",
            date(2021, 1, 1),
            date(2021, 1, 2),
            timezone("America/New_York"),
            None,
            {},
        ),
        (
            "Test Event 2",
            datetime(2021, 1, 1, 10, 30),
            date(2021, 1, 2),
            timezone("Europe/London"),
            None,
            {},
        ),
        (
            "Test Event 3",
            date(2021, 1, 2),
            datetime(2021, 1, 1, 10, 30),
            timezone("Africa/Johannesburg"),
            None,
            {},
        ),
        (
            "Test Event 4",
            date(2021, 1, 2),
            date(2021, 1, 2),
            timezone("Africa/Johannesburg"),
            Calendar.parse_obj(
                {
                    "id": "test-calendar-id",
                    "etag": "",
                    "summary": "",
                    "google_client": GoogleCalendarClient(
                        client_id="", client_secret=""
                    ),
                    "kind": "calendar#calendar",
                    "timeZone": "Africa/Johannesburg",
                    "conferenceProperties": {},
                }
            ),
            {},
        ),
        (
            "Test Event 5",
            date(2021, 1, 2),
            date(2021, 1, 2),
            timezone("Africa/Johannesburg"),
            Calendar.parse_obj(
                {
                    "id": "test-calendar-id",
                    "etag": "",
                    "summary": "",
                    "google_client": GoogleCalendarClient(
                        client_id="", client_secret=""
                    ),
                    "kind": "calendar#calendar",
                    "timeZone": "Africa/Johannesburg",
                    "conferenceProperties": {},
                }
            ),
            {
                "one": "one",
                "two": "two",
                "three": "three",
            },
        ),
    ),
)
def test_create_event_response(
    google_calendar_client: GoogleCalendarClient,
    event: Event,
    mock_requests: Mocker,
    summary: str,
    start_datetime: datetime | date,
    end_datetime: datetime | date,
    tz: tzinfo,
    calendar_arg: Calendar | None,
    extra_params: dict[str, Any],
) -> None:
    """Test the `create_event` method returns an Event instance."""

    if isinstance(start_datetime, datetime):
        start = _StartEndDatetime.parse_obj(
            {
                "timeZone": tz.tzname(None),
                "dateTime": start_datetime.replace(tzinfo=tz).strftime(
                    "%Y-%m-%dT%H:%M:%S%z"
                ),
            }
        )
    else:
        start = _StartEndDatetime.parse_obj(
            {
                "timeZone": tz.tzname(None),
                "date": start_datetime.isoformat(),
            }
        )

    if isinstance(end_datetime, datetime):
        end = _StartEndDatetime.parse_obj(
            {
                "timeZone": tz.tzname(None),
                "dateTime": end_datetime.replace(tzinfo=tz).strftime(
                    "%Y-%m-%dT%H:%M:%S%z"
                ),
            }
        )
    else:
        end = _StartEndDatetime.parse_obj(
            {
                "timeZone": tz.tzname(None),
                "date": end_datetime.isoformat(),
            }
        )

    expected_event = event.copy(
        update={
            "summary": summary,
            "start": start,
            "end": end,
            "calendar": calendar_arg or google_calendar_client.primary_calendar,
        }
    )

    mock_requests.post(
        "/".join(
            [
                google_calendar_client.base_url,
                "calendars",
                expected_event.calendar.id,
                "events",
            ]
        ),
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json=loads(expected_event.json()),
    )

    assert (
        google_calendar_client.create_event(
            summary=summary,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            tz=str(tz),
            calendar=calendar_arg,
            extra_params=extra_params,
        )
        == expected_event
    )


@mark.parametrize(
    ("start_datetime", "end_datetime", "expected_exception_message"),
    (
        (date(2021, 1, 1), date(2021, 1, 2), None),
        (date(2021, 1, 1), datetime(2021, 1, 2), None),
        (datetime(2021, 1, 1), date(2021, 1, 2), None),
        (
            "2021-01-01",
            date(2021, 1, 2),
            "^`start_datetime` must be either a date or a datetime$",
        ),
        (
            date(2021, 1, 2),
            "2021-01-02",
            "^`end_datetime` must be either a date or a datetime$",
        ),
    ),
)
def test_create_event_type_validation(
    start_datetime: datetime | date,
    end_datetime: datetime | date,
    expected_exception_message: str | None,
    google_calendar_client: GoogleCalendarClient,
    event: Event,
) -> None:
    """Test `create_event` raises a `TypeError` if either datetime param is invalid."""

    with patch.object(
        google_calendar_client, "post_json_response"
    ) as mock_post_json_response:
        mock_post_json_response.return_value = loads(event.json())

        if expected_exception_message:
            with raises(TypeError, match=expected_exception_message):
                google_calendar_client.create_event(
                    summary="Test Event",
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    tz="America/New_York",
                )
        else:
            google_calendar_client.create_event(
                summary="Test Event",
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                tz="America/New_York",
            )


def test_delete_event_by_id(
    google_calendar_client: GoogleCalendarClient,
    event: Event,
    calendar: Calendar,
    mock_requests: Mocker,
) -> None:
    """Test the `delete_event_by_id` method sends the correct request."""

    mock_requests.delete(
        f"{google_calendar_client.base_url}/calendars/{calendar.id}/events/{event.id}",
        status_code=HTTPStatus.NO_CONTENT,
        reason=HTTPStatus.NO_CONTENT.phrase,
    )

    google_calendar_client.delete_event_by_id(event_id=event.id, calendar=calendar)

    assert mock_requests.last_request
    assert (
        mock_requests.last_request.url == f"{google_calendar_client.base_url}/calendars"
        f"/{calendar.id}/events/{event.id}"
    )
    assert mock_requests.last_request.method == "DELETE"
    assert (
        mock_requests.last_request.headers["Authorization"]
        == f"Bearer {google_calendar_client.access_token}"
    )
    assert mock_requests.last_request.headers["Content-Type"] == "application/json"


def test_delete_event_by_id_raises_exception(
    google_calendar_client: GoogleCalendarClient,
    event: Event,
    calendar: Calendar,
    mock_requests: Mocker,
) -> None:
    """Test the `delete_event_by_id` method raises an exception if the request fails."""

    mock_requests.delete(
        f"{google_calendar_client.base_url}/calendars/{calendar.id}/events/{event.id}",
        status_code=HTTPStatus.NOT_FOUND,
        reason=HTTPStatus.NOT_FOUND.phrase,
    )

    with raises(HTTPError) as exc_info:
        google_calendar_client.delete_event_by_id(event_id=event.id, calendar=calendar)

    assert exc_info.value.response.status_code == HTTPStatus.NOT_FOUND


def test_get_event_by_id(
    google_calendar_client: GoogleCalendarClient, calendar: Calendar
) -> None:
    """Test that the `get_event_by_id` method returns an `Event` object."""
    with patch.object(
        google_calendar_client,
        "get_json_response",
        wraps=google_calendar_client.get_json_response,
    ) as mock_get_json_response:
        event = google_calendar_client.get_event_by_id(
            "jt171go86rkonwwkyd5q7m84mm", calendar=calendar
        )

    mock_get_json_response.assert_called_once_with(
        f"/calendars/{calendar.id}/events/jt171go86rkonwwkyd5q7m84mm",
        params={"maxResults": None},
    )

    assert isinstance(event, Event)
    assert event.id == "jt171go86rkonwwkyd5q7m84mm"
    assert event.calendar == calendar


def test_calendar_list(google_calendar_client: GoogleCalendarClient) -> None:
    """Test that the `calendar_list` method returns a list of `Calendar` objects."""
    with patch.object(
        google_calendar_client, "get_items", wraps=google_calendar_client.get_items
    ) as mock_get_items:
        calendars = google_calendar_client.calendar_list

    mock_get_items.assert_called_once_with(
        "/users/me/calendarList", params={"maxResults": None}
    )

    assert isinstance(calendars, list)
    assert all(isinstance(calendar, Calendar) for calendar in calendars)
    assert len(calendars) == 7

    assert google_calendar_client.primary_calendar in calendars


def test_primary_calendar(google_calendar_client: GoogleCalendarClient) -> None:
    """Test that the `primary_calendar` method returns a `Calendar` object."""
    with patch.object(
        google_calendar_client,
        "get_json_response",
        wraps=google_calendar_client.get_json_response,
    ) as mock_get_json_response:
        _ = google_calendar_client.primary_calendar
        primary_calendar = google_calendar_client.primary_calendar

    mock_get_json_response.assert_called_once_with(
        "/calendars/primary", params={"maxResults": None}
    )

    assert isinstance(primary_calendar, Calendar)
    assert primary_calendar.id == "google-user@gmail.com"
