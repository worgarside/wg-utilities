"""Unit tests for `wg_utilities.clients.google_calendar.GoogleCalendarEntity`."""
from __future__ import annotations

from datetime import datetime, tzinfo
from random import randint
from unittest.mock import patch

from pytest import mark

from wg_utilities.clients import GoogleCalendarClient
from wg_utilities.clients.google_calendar import GoogleCalendarEntity


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


@mark.parametrize(  # type: ignore[misc]
    "event_index",
    [randint(0, 1011) for _ in range(25)],
)
def test_json_encoder(
    event_index: int, google_calendar_client: GoogleCalendarClient
) -> None:
    """Test that the `json` method returns a correctly-encoded JSON string."""

    event = google_calendar_client.primary_calendar.get_events()[event_index]

    assert isinstance(event, GoogleCalendarEntity)

    with patch.object(
        GoogleCalendarEntity,
        "_json_encoder",
        wraps=GoogleCalendarEntity._json_encoder,  # pylint: disable=protected-access
    ) as mock_json_encoder:
        event_json = event.json()

    for call in mock_json_encoder.call_args_list:
        value = call.args[0]

        if isinstance(value, datetime):
            assert value.strftime(GoogleCalendarClient.DATETIME_FORMAT) in event_json
        elif isinstance(value, tzinfo):
            # The `str()` call below will convert `None` to `"None"`, which will cause
            # this to fail. It's intentional; I'm yet to see a missing timeZone field
            # in the JSON responses from the Google Calendar API.
            assert str(value.tzname(None)) in event_json
