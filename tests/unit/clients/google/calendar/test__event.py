"""Unit tests for `wg_utilities.clients.google_calendar.Event`."""
from __future__ import annotations

from datetime import datetime, timedelta
from http import HTTPStatus

from pytest import mark, raises
from pytz import timezone
from requests_mock import Mocker

from tests.conftest import read_json_file
from wg_utilities.clients import GoogleCalendarClient
from wg_utilities.clients.google_calendar import (
    Calendar,
    Event,
    ResponseStatus,
    _Attendee,
    _Creator,
    _StartEndDatetime,
)


def test_instantiation(
    google_calendar_client: GoogleCalendarClient, calendar: Calendar
) -> None:
    """Test that the `Event` class can be instantiated."""

    event_json = read_json_file(
        "v3/calendars/google-user@gmail.com/events/jt171go86rkonwwkyd5q7m84mm.json",
        host_name="google/calendar",
    )

    event = Event.from_json_response(
        event_json, google_client=google_calendar_client, calendar=calendar
    )

    assert isinstance(event, Event)
    assert event.id == "jt171go86rkonwwkyd5q7m84mm"
    assert event.start.datetime == datetime(
        2022, 12, 6, 10, 15, tzinfo=timezone("Europe/London")
    )
    assert event.google_client == google_calendar_client


def test_delete_method(
    google_calendar_client: GoogleCalendarClient,
    calendar: Calendar,
    event: Event,
    mock_requests: Mocker,
) -> None:
    """Test that the `delete` method sends the correct request."""

    mock_requests.delete(
        f"{google_calendar_client.base_url}/calendars/{calendar.id}/events/{event.id}",
        status_code=HTTPStatus.NO_CONTENT,
        reason=HTTPStatus.NO_CONTENT.phrase,
    )

    event.delete()

    assert mock_requests.last_request
    assert mock_requests.last_request.method == "DELETE"
    assert (
        mock_requests.last_request.headers["Authorization"]
        == f"Bearer {google_calendar_client.access_token}"
    )
    assert mock_requests.last_request.headers["Content-Type"] == "application/json"


@mark.parametrize(
    ("attendees", "creator", "expected_response_status"),
    (
        (
            [
                _Attendee(
                    email="google-user@gmail.com",
                    responseStatus=ResponseStatus.ACCEPTED,
                    self=True,
                )
            ],
            None,
            ResponseStatus.ACCEPTED,
        ),
        (
            [
                _Attendee(
                    email="google-user@gmail.com",
                    responseStatus=ResponseStatus.DECLINED,
                    self=True,
                )
            ],
            None,
            ResponseStatus.DECLINED,
        ),
        (
            [
                _Attendee(
                    email="google-user@gmail.com",
                    responseStatus=ResponseStatus.TENTATIVE,
                    self=True,
                )
            ],
            None,
            ResponseStatus.TENTATIVE,
        ),
        (
            [
                _Attendee(
                    email="google-user@gmail.com",
                    responseStatus=ResponseStatus.UNCONFIRMED,
                    self=True,
                )
            ],
            None,
            ResponseStatus.UNCONFIRMED,
        ),
        (
            [
                _Attendee(
                    email="google-user@gmail.com",
                    responseStatus=ResponseStatus.UNKNOWN,
                    self=True,
                )
            ],
            None,
            ResponseStatus.UNKNOWN,
        ),
        (
            [
                _Attendee(
                    email="google-user@gmail.com",
                    responseStatus=ResponseStatus.DECLINED,
                )
            ],
            _Creator(email="google-user@gmail.com", self=True),
            ResponseStatus.ACCEPTED,
        ),
        (
            [
                _Attendee(
                    email="google-user@gmail.com",
                    responseStatus=ResponseStatus.DECLINED,
                )
            ],
            _Creator(email="google-user-2@gmail.com"),
            ResponseStatus.UNKNOWN,
        ),
    ),
)
def test_response_status_property(
    event: Event,
    attendees: list[_Attendee],
    creator: _Creator,
    expected_response_status: ResponseStatus,
) -> None:
    """Test that the `response_status` property returns the correct value."""

    updates: dict[str, list[_Attendee] | _Creator] = {
        "attendees": attendees,
    }

    if creator:
        updates["creator"] = creator

    new_event = event.model_copy(update=updates)

    assert new_event.response_status == expected_response_status


def test_gt_method(event: Event) -> None:
    """Test that the `__gt__` method returns the correct value."""

    # Starts and ends a day later
    before_first = event.model_copy(
        update={
            "start": _StartEndDatetime.model_validate(
                {
                    "dateTime": (event.start.datetime + timedelta(days=1)).isoformat(),
                    "timeZone": "Europe/London",
                }
            ),
            "end": _StartEndDatetime.model_validate(
                {
                    "dateTime": (event.end.datetime + timedelta(days=1)).isoformat(),
                    "timeZone": "Europe/London",
                }
            ),
        }
    )

    # Ends 5 minutes later
    before_second = event.model_copy(
        update={
            "end": _StartEndDatetime.model_validate(
                {
                    "dateTime": (event.end.datetime + timedelta(minutes=5)).isoformat(),
                    "timeZone": "Europe/London",
                }
            )
        }
    )

    # Starts and ends at same time, but starts with a letter earlier in the alphabet
    before_third = event.model_copy(
        update={
            "summary": "Z test event",
        }
    )

    assert before_first > before_second > before_third > event

    with raises(TypeError):
        assert event > "test"  # type: ignore[operator]


def test_lt_method(event: Event) -> None:
    """Test that the `__lt__` method returns the correct value."""

    # Starts a day earlier
    before_first = event.model_copy(
        update={
            "start": _StartEndDatetime.model_validate(
                {
                    "dateTime": (event.start.datetime - timedelta(days=1)).isoformat(),
                    "timeZone": "Europe/London",
                }
            )
        }
    )

    # Ends 5 minutes earlier
    before_second = event.model_copy(
        update={
            "end": _StartEndDatetime.model_validate(
                {
                    "dateTime": (event.end.datetime - timedelta(minutes=5)).isoformat(),
                    "timeZone": "Europe/London",
                }
            ),
        }
    )

    # Starts and ends at same time, but starts with a letter earlier in the alphabet
    before_third = event.model_copy(
        update={
            "summary": "A test event",
        }
    )

    assert before_first < before_second < before_third < event

    with raises(TypeError):
        assert event < "test"  # type: ignore[operator]


def test_str_method(event: Event) -> None:
    """Test that the `__str__` method returns a string repr of the event."""

    assert str(event) == (
        f"{event.summary} ("
        f"{event.start.datetime.isoformat()} - "
        f"{event.end.datetime.isoformat()})"
    )
