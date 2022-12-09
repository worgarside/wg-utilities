"""Unit tests for `wg_utilities.clients.google_calendar.GoogleCalendarEntity`."""
from __future__ import annotations

from datetime import datetime, tzinfo
from json import loads
from pathlib import Path
from random import choice
from unittest.mock import patch

from pytest import mark

from wg_utilities.clients import GoogleCalendarClient
from wg_utilities.clients.google_calendar import (
    Calendar,
    Event,
    EventJson,
    GoogleCalendarEntity,
)


def test_from_json_response_instantiation(
    google_calendar_client: GoogleCalendarClient,
) -> None:
    """Test instantiation of the GoogleCalendarEntity class."""
    google_calendar_entity = GoogleCalendarEntity.from_json_response(
        {  # type: ignore[arg-type]
            "etag": '"u2O-pzpMJslGoV7Iyoc4Zcqzpgb"',
            "id": "google-user@gmail.com",
            "summary": "Hbhboqhj Ahtuozm",
        },
        google_client=google_calendar_client,
    )
    assert isinstance(google_calendar_entity, GoogleCalendarEntity)

    assert google_calendar_entity.dict() == {
        "etag": '"u2O-pzpMJslGoV7Iyoc4Zcqzpgb"',
        "id": "google-user@gmail.com",
        "summary": "Hbhboqhj Ahtuozm",
    }

    assert google_calendar_entity.description is None
    assert google_calendar_entity.etag == '"u2O-pzpMJslGoV7Iyoc4Zcqzpgb"'
    assert google_calendar_entity.id == "google-user@gmail.com"
    assert google_calendar_entity.location is None
    assert google_calendar_entity.summary == "Hbhboqhj Ahtuozm"

    assert google_calendar_entity.google_client == google_calendar_client


ALL_EVENTS = []

for file in (
    Path(__file__).parents[4]
    / "tests/flat_files/json/google/calendar/v3/calendars/google-user@gmail.com/events"
).glob("*.json"):
    ALL_EVENTS.extend(loads(file.read_text()).get("items", []))


@mark.parametrize(  # type: ignore[misc]
    "event_json",
    (choice(ALL_EVENTS) for _ in range(100)),
)
def test_json_encoder(
    event_json: EventJson,
    google_calendar_client: GoogleCalendarClient,
    calendar: Calendar,
) -> None:
    """Test that the `json` method returns a correctly-encoded JSON string."""

    event = Event.from_json_response(
        event_json, google_client=google_calendar_client, calendar=calendar
    )

    assert isinstance(event, GoogleCalendarEntity)

    with patch.object(
        GoogleCalendarEntity,
        "_json_encoder",
        wraps=GoogleCalendarEntity._json_encoder,  # pylint: disable=protected-access
    ) as mock_json_encoder:
        returned_json = event.json()

    for call in mock_json_encoder.call_args_list:
        value = call.args[0]

        if isinstance(value, datetime):
            assert value.isoformat() in returned_json
        elif isinstance(value, tzinfo):
            # The `str()` call below will convert `None` to `"None"`, which will cause
            # this to fail. It's intentional; I'm yet to see a missing timeZone field
            # in the JSON responses from the Google Calendar API.
            assert str(value.tzname(None)) in returned_json


def test_eq(google_calendar_client: GoogleCalendarClient) -> None:
    """Test the __eq__ method of the `GoogleCalendarEntity` class."""

    google_calendar_entity = GoogleCalendarEntity.from_json_response(
        {  # type: ignore[arg-type]
            "etag": '"u2O-pzpMJslGoV7Iyoc4Zcqzpgb"',
            "id": "google-user@gmail.com",
            "summary": "Hbhboqhj Ahtuozm",
        },
        google_client=google_calendar_client,
    )

    other_google_calendar_entity = GoogleCalendarEntity.from_json_response(
        {  # type: ignore[arg-type]
            "etag": '"u2O-pzabcdefghijkoc4Zcqzpgb"',
            "id": "google-user-2@gmail.com",
            "summary": "Summary Thing",
        },
        google_client=google_calendar_client,
    )

    assert (
        google_calendar_entity  # pylint: disable=comparison-with-itself
        == google_calendar_entity
    )
    assert google_calendar_entity != other_google_calendar_entity
    assert google_calendar_entity != "something else"
