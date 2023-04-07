"""Helper functions for all things date and time related."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import overload

from pytz import utc


class DatetimeFixedUnit(Enum):
    """Enum for fixed units of time (i.e. not a month or a year).

    Values are in seconds.
    """

    WEEK = 604800
    DAY = 86400
    HOUR = 3600
    MINUTE = 60
    SECOND = 1
    MILLISECOND = 1e-3
    MICROSECOND = 1e-6
    NANOSECOND = 1e-9


DTU = DatetimeFixedUnit


@overload
def utcnow() -> datetime:
    ...


@overload
def utcnow(unit: DatetimeFixedUnit) -> int:
    ...


def utcnow(unit: DatetimeFixedUnit | None = None) -> datetime | int:
    """`datetime.utcnow` with optional unit conversion.

    Gets the current UTC time and returns it in a chosen unit. If no unit is
    provided then it is just returned as a datetime

    Args:
        unit (DatetimeFixedUnit): the unit in which to provide the current datetime

    Returns:
        Union([datetime, int]): the current UTC datetime in the chosen unit
    """

    if not unit:
        return datetime.utcnow().replace(tzinfo=utc)

    return int(datetime.utcnow().replace(tzinfo=utc).timestamp() / unit.value)


__all__ = [
    "DatetimeFixedUnit",
    "DTU",
    "utcnow",
]
