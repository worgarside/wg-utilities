"""Unit Tests for the `ListHandler` class and its methods."""
# pylint: disable=protected-access
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from logging import Logger, LogRecord, getLevelName
from unittest.mock import MagicMock, patch

from freezegun import freeze_time
from pytest import mark

from wg_utilities.loggers import ListHandler

BASE_TIME = datetime(2000, 1, 1)


def test_list_handler_instantiation() -> None:
    """Test that the ListHandler can be instantiated."""
    record_list: list[LogRecord] = []

    def on_record(_: LogRecord) -> None:
        """Do something with the record."""

    l_handler = ListHandler(
        record_list, log_ttl=60, on_record=on_record, on_expiry=on_record
    )

    assert l_handler is not None
    assert l_handler._records_list is record_list
    assert l_handler.ttl == 60
    assert l_handler.on_record is on_record
    assert l_handler.on_expiry is on_record


def test_emit_calls_expire_records(
    list_handler: ListHandler, sample_log_record: LogRecord
) -> None:
    """Test that `expire_records` is called on `emit`."""

    with patch("wg_utilities.loggers.ListHandler.expire_records") as mock_expire:

        list_handler.emit(sample_log_record)

        assert mock_expire.called


def test_emit_appends_to_record_list(
    list_handler: ListHandler, sample_log_record: LogRecord
) -> None:
    """Test that `emit` appends to the record list."""

    list_handler.emit(sample_log_record)

    assert list_handler._records_list == [sample_log_record]


def test_emit_calls_on_record(
    list_handler: ListHandler, sample_log_record: LogRecord
) -> None:
    """Test that `on_record` is called on `emit`."""

    called = False

    def _cb(record: LogRecord) -> None:
        nonlocal called
        assert record is sample_log_record
        called = True

    list_handler.on_record = _cb

    list_handler.emit(sample_log_record)

    assert called


def test_expire_records_does_nothing_if_ttl_is_none(list_handler: ListHandler) -> None:
    """Test that `expire_records` does nothing if `ttl` is None."""

    list_handler.ttl = None

    with patch("wg_utilities.loggers.datetime") as mock_datetime:

        list_handler.expire_records()

        assert not mock_datetime.now.called

    assert list_handler._records_list == []


def test_expire_records_remove_records_correctly(
    list_handler: ListHandler, logger: Logger
) -> None:
    """Test that `expire_records` only removes old records."""

    list_handler.ttl = 60

    logger.addHandler(list_handler)

    for i in range(-1, 25):
        with freeze_time(BASE_TIME + timedelta(seconds=i * 5)):
            message = f"Created at {datetime.now()}. Valid: {i >= 12}"
            logger.info(message)

    with freeze_time(BASE_TIME):
        list_handler.expire_records()

    for record in list_handler._records_list:
        assert record.created >= (BASE_TIME.timestamp() + 60)
        assert (
            record.msg
            == f"Created at {datetime.fromtimestamp(record.created)}. Valid: True"
        )


def test_expire_records_calls_on_expiry(list_handler_prepopulated: ListHandler) -> None:
    """Test that `on_expiry` is called by `expire_records` per-record."""

    recorded_logs = deepcopy(list_handler_prepopulated._records_list)

    expired_records: list[LogRecord] = []

    def _cb(record: LogRecord) -> None:
        assert repr(record) == repr(recorded_logs[len(expired_records)])

        expired_records.append(record)

    list_handler_prepopulated.on_expiry = _cb
    list_handler_prepopulated.ttl = -10
    list_handler_prepopulated.expire_records()

    assert list(map(repr, expired_records)) == list(map(repr, recorded_logs))


@mark.parametrize(  # type: ignore[misc]
    "level_name",
    ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", None],  # Used for "all records"
)
def test_record_properties_return_correct_items(
    level_name: str, list_handler_prepopulated: ListHandler
) -> None:
    """Test that each of the level-specific properties return only the expected records.

    This test is parametrized to test each of the level-specific properties, including
    a special case for testing the `ListHandler.records` property.
    """

    property_name = f"{level_name.lower()}_records" if level_name else "records"

    # Check all records are present
    assert len(list_handler_prepopulated._records_list) == 25

    level_specific_logs = getattr(list_handler_prepopulated, property_name)

    if level_name is not None:
        assert len(level_specific_logs) == 5 if level_name else 25

        for log in level_specific_logs:
            assert getLevelName(log.levelno) == level_name
    else:
        assert level_specific_logs is list_handler_prepopulated._records_list


@mark.parametrize(  # type: ignore[misc]
    "level_name",
    ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", None],  # Used for "all records"
)
def test_record_properties_call_expire_records(
    level_name: str | None, list_handler_prepopulated: ListHandler
) -> None:
    """Test that each of the level-specific properties expires old records."""

    property_name = f"{level_name.lower()}_records" if level_name else "records"

    # Check all records are present
    assert len(list_handler_prepopulated._records_list) == 25

    with patch("wg_utilities.loggers.ListHandler.expire_records") as mock_expire:
        getattr(list_handler_prepopulated, property_name)
        assert mock_expire.called


@patch("wg_utilities.loggers.ListHandler.emit")
def test_logging_with_logger_calls_emit_method(
    mock_emit: MagicMock,
    logger: Logger,
    list_handler: ListHandler,
    sample_log_record_messages_with_level: list[tuple[int, str]],
) -> None:
    """Test that logging calls the `emit` method of the handler."""
    print(type(mock_emit))
    logger.addHandler(list_handler)

    for level, message in sample_log_record_messages_with_level:
        logger.log(level, message)

    assert mock_emit.call_count == len(sample_log_record_messages_with_level)

    for i, call in enumerate(mock_emit.call_args_list):
        assert call.args[0].levelno == sample_log_record_messages_with_level[i][0]
        assert call.args[0].msg == sample_log_record_messages_with_level[i][1]
