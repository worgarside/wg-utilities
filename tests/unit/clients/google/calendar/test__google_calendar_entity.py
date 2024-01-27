"""Unit tests for `wg_utilities.clients.google_calendar.GoogleCalendarEntity`."""
from __future__ import annotations

from copy import deepcopy
from json import loads
from pathlib import Path

from wg_utilities.clients import GoogleCalendarClient
from wg_utilities.clients.google_calendar import GoogleCalendarEntity

GoogleCalendarEntity.model_rebuild()


def test_from_json_response_instantiation(
    google_calendar_client: GoogleCalendarClient,
) -> None:
    """Test instantiation of the GoogleCalendarEntity class."""
    google_calendar_entity = GoogleCalendarEntity.from_json_response(
        {
            "etag": '"u2O-pzpMJslGoV7Iyoc4Zcqzpgb"',
            "id": "google-user@gmail.com",
            "summary": "Hbhboqhj Ahtuozm",
        },
        google_client=google_calendar_client,
    )
    assert isinstance(google_calendar_entity, GoogleCalendarEntity)

    assert google_calendar_entity.model_dump() == {
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
    Path(__file__).parents[5]
    / "tests/flat_files/json/google/calendar/v3/calendars/google-user@gmail.com/events"
).glob("*.json"):
    ALL_EVENTS.extend(loads(file.read_text()).get("items", []))


def test_eq(google_calendar_client: GoogleCalendarClient) -> None:
    """Test the __eq__ method of the `GoogleCalendarEntity` class."""

    google_calendar_entity = GoogleCalendarEntity.from_json_response(
        {
            "etag": '"u2O-pzpMJslGoV7Iyoc4Zcqzpgb"',
            "id": "google-user@gmail.com",
            "summary": "Hbhboqhj Ahtuozm",
        },
        google_client=google_calendar_client,
    )

    other_google_calendar_entity = GoogleCalendarEntity.from_json_response(
        {
            "etag": '"u2O-pzabcdefghijkoc4Zcqzpgb"',
            "id": "google-user-2@gmail.com",
            "summary": "Summary Thing",
        },
        google_client=google_calendar_client,
    )

    assert google_calendar_entity == deepcopy(google_calendar_entity)
    assert google_calendar_entity != other_google_calendar_entity
    assert google_calendar_entity != "something else"
