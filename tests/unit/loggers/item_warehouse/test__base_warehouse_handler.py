"""Unit tests for the BaseWarehouseHandler class."""

from __future__ import annotations

from logging import Handler, LogRecord
from socket import gethostname
from traceback import format_exception

import pytest

from tests.conftest import TestError
from tests.unit.loggers.conftest import SAMPLE_LOG_RECORDS
from wg_utilities.clients.json_api_client import JsonApiClient
from wg_utilities.loggers.item_warehouse.base_handler import (
    BaseWarehouseHandler,
    LogPayload,
)


def test_instantiation() -> None:
    """Test that the BaseWarehouseHandler class can be instantiated."""

    bwh_handler = BaseWarehouseHandler()

    assert isinstance(bwh_handler, BaseWarehouseHandler)
    assert isinstance(bwh_handler, Handler)
    assert isinstance(bwh_handler, JsonApiClient)


@pytest.mark.parametrize(
    ("log_record", "expected_hash"),
    tuple(
        zip(
            SAMPLE_LOG_RECORDS,
            (
                "1e05cd0ed066d50b1a0802789fadee56",
                "86c198e652158bd68f41d82975800377",
                "70e883e4c5ce4a578d29234911966b42",
                "a7a101ea5bf832a39490df7a3f139c86",
                "045d016612faee5da40656706f6145fb",
                "1fe2cbaaabdf9245d87a78bc7c0fe3bf",
                "a65a1ab074fc98617c7738e5dd651ad4",
                "a2f9bddc9196b43f414b191294103300",
                "ec83769b693de73001cfd7151dc05d00",
                "e7952fd7d16df1e52eafbc1614136234",
                "d9de655c92a41e55550eccc098400e23",
                "8d5e977944ee6c814ed959b898a3e7d6",
                "8e248ec9bba275d283bec6b46ff837b6",
                "1afd92270041f67a6ba3bb7660a5c8f8",
                "babbcfc4e59dffdeb903b188f0549d72",
                "a9643698bd19c7ddd4d040702e30ac92",
                "1ad218249f2e2a115aebfd0aa17867f9",
                "5b336519ff0f081025e7db88ff82cd70",
                "c213821a31d071ba4b73f7c91cb39cd8",
                "14964924a99d81b87f37b41d1a286618",
                "81034992bac8ad040352253a9df6163e",
                "cb2761c9be3acd1fae0816bcf97c0bd6",
                "50f3edd190b2d395d68c9606383d954d",
                "3d309702a096c3fa6620cb001ec90e05",
                "9e821dc5cb3cc36a2c5c91ec9b18a3bd",
            ),
            strict=False,
        )
    ),
)
def test_get_log_hash(log_record: LogRecord, expected_hash: str) -> None:
    """Test that the get_log_hash method returns consistent results."""

    assert BaseWarehouseHandler.get_log_hash(log_record) == expected_hash


def test_emit() -> None:
    """Test that the emit method raises a NotImplementedError."""

    with pytest.raises(NotImplementedError):
        BaseWarehouseHandler(
            warehouse_host="item-warehouse.com",
            warehouse_port=443,
        ).emit(SAMPLE_LOG_RECORDS[0])


@pytest.mark.parametrize(
    ("host", "port", "expected_url"),
    [
        ("item-warehouse.com", 443, "item-warehouse.com:443/v1"),
        ("item-warehouse.com", None, "item-warehouse.com:8002/v1"),
        ("item-warehouse.com", 0, "item-warehouse.com/v1"),
        (None, 443, "http://homeassistant.local:443/v1"),
        (None, None, "http://homeassistant.local:8002/v1"),
    ],
)
def test_get_base_url(host: str | None, port: int | None, expected_url: str) -> None:
    """Test that the get_base_url method returns the expected value."""

    assert BaseWarehouseHandler.get_base_url(host, port) == expected_url


_STANDARD_SAMPLE_LOG_RECORD_KWARGS = {
    "created_at": 0,
    "exception_message": None,
    "exception_type": None,
    "exception_traceback": None,
    "file": "test",
    "line": 1,
    "log_host": gethostname(),
    "logger": "test",
    "module": "test",
    "process": "MainProcess",
    "thread": "MainThread",
}


@pytest.mark.parametrize(
    ("log_record", "expected_payload"),
    list(
        zip(
            SAMPLE_LOG_RECORDS,
            [
                {
                    **_STANDARD_SAMPLE_LOG_RECORD_KWARGS,
                    "level": 10,
                    "log_hash": "1e05cd0ed066d50b1a0802789fadee56",
                    "message": "Test log message #0 at level DEBUG",
                },
                {
                    **_STANDARD_SAMPLE_LOG_RECORD_KWARGS,
                    "level": 20,
                    "log_hash": "86c198e652158bd68f41d82975800377",
                    "message": "Test log message #1 at level INFO",
                },
                {
                    **_STANDARD_SAMPLE_LOG_RECORD_KWARGS,
                    "level": 30,
                    "log_hash": "70e883e4c5ce4a578d29234911966b42",
                    "message": "Test log message #2 at level WARNING",
                },
            ],
            strict=False,
        ),
    ),
)
def test_get_log_payload(
    log_record: LogRecord, expected_payload: LogPayload | None
) -> None:
    """Test that the get_log_payload method returns the expected value."""

    if expected_payload:
        assert BaseWarehouseHandler.get_log_payload(log_record) == expected_payload


def test_get_log_payload_exception() -> None:
    """Test an exception log is processed correctly."""

    exc = TestError("Test error message")

    log_record = LogRecord(
        name="test",
        level=40,
        pathname="test",
        lineno=1,
        msg="Test log message",
        args=(),
        exc_info=(TestError, exc, None),
    )

    payload = BaseWarehouseHandler.get_log_payload(log_record)

    assert payload["exception_message"] == "Test error message"
    assert payload["exception_type"] == "TestError"
    assert payload["exception_traceback"] == "".join(format_exception(exc))
