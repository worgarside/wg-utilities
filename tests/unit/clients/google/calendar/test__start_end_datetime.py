"""Unit tests for `wg_utilities.clients.google_calendar._StartEndDatetime`."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError
from pytz import timezone

from wg_utilities.clients.google_calendar import _StartEndDatetime


@pytest.mark.parametrize(
    ("obj_json", "expected_datetime"),
    [
        (
            {
                "date": "2021-01-01",
                "timeZone": "Europe/London",
            },
            datetime(2021, 1, 1, tzinfo=timezone("Europe/London")),
        ),
        (
            {
                "dateTime": "2021-01-01T10:30:00Z",
                "timeZone": "Europe/London",
            },
            datetime(2021, 1, 1, 10, 30, tzinfo=timezone("Europe/London")),
        ),
    ],
)
def test_instantiation(obj_json: dict[str, str], expected_datetime: datetime) -> None:
    """Test `StartEndDatetime` can be instantiated with a date and timezone."""

    sed = _StartEndDatetime.model_validate(obj_json)

    assert sed.date == date(2021, 1, 1)
    assert sed.datetime == expected_datetime
    assert sed.timezone == timezone("Europe/London")


def test_bad_instantiation() -> None:
    """Test an error is raised if neither date nor datetime is provided."""

    with pytest.raises(ValidationError) as exc_info:
        _StartEndDatetime(timeZone="Europe/London")  # type: ignore[arg-type,call-arg]

    assert "Either `date` or `dateTime` must be provided." in str(exc_info.value)
