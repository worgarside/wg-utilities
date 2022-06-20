"""Helper functions for all things date and time related"""
from datetime import datetime
from enum import Enum
from typing import Optional, Union


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


def utcnow(unit: Optional[DatetimeFixedUnit] = None) -> Union[datetime, int]:
    """Gets the current UTC time and returns it in a chosen unit. If no unit is
     provided then it is just returned as a datetime

    Args:
        unit (DatetimeFixedUnit): the unit in which to provide the current datetime

    Returns:
        Union([datetime, float, int]): the current UTC datetime in the chosen unit
    """

    if not unit:
        return datetime.utcnow()

    return int(datetime.utcnow().timestamp() / unit.value)
