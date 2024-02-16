"""Unit Tests for `wg_utilities.functions.datetime_helpers.utcnow`."""

from __future__ import annotations

from datetime import datetime

import pytest
from freezegun import freeze_time
from pytz import utc

from wg_utilities.functions import DTU, utcnow


def test_utcnow_no_unit() -> None:
    """Test that the utcnow function returns a datetime if no unit is provided."""
    assert isinstance(utcnow(), datetime)

    with freeze_time("2021-01-01 00:00:00"):
        assert utcnow() == datetime(2021, 1, 1, 0, 0, 0, tzinfo=utc)


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (DTU.WEEK, datetime(2021, 1, 1).timestamp() / (60 * 60 * 24 * 7)),
        (DTU.DAY, datetime(2021, 1, 1).timestamp() / (60 * 60 * 24)),
        (DTU.HOUR, datetime(2021, 1, 1).timestamp() / (60 * 60)),
        (DTU.MINUTE, datetime(2021, 1, 1).timestamp() / 60),
        (DTU.SECOND, datetime(2021, 1, 1).timestamp()),
        (DTU.MILLISECOND, datetime(2021, 1, 1).timestamp() * 1e3),
        (DTU.MICROSECOND, datetime(2021, 1, 1).timestamp() * 1e6),
        (DTU.NANOSECOND, datetime(2021, 1, 1).timestamp() * 1e9),
    ],
)
def test_utcnow_with_unit(unit: DTU, expected: int) -> None:
    """Test that the utcnow function returns a float if a unit is provided."""
    assert isinstance(utcnow(unit), int)

    with freeze_time("2021-01-01 00:00:00"):
        assert utcnow(unit) == round(expected)
