# pylint: disable=protected-access
"""Unit tests for the WarehouseHandler class."""


from __future__ import annotations

from hashlib import md5
from http import HTTPStatus
from logging import ERROR, Handler, Logger, LogRecord
from socket import gethostname
from unittest.mock import ANY, Mock, call, patch

from freezegun import freeze_time
from pytest import LogCaptureFixture, mark, raises
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import RequestException
from requests_mock import ANY as REQUESTS_MOCK_ANY
from requests_mock import Mocker

from tests.unit.loggers.conftest import (
    SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL,
    SAMPLE_LOG_RECORDS,
    WAREHOUSE_SCHEMA,
)
from wg_utilities.clients.json_api_client import JsonApiClient
from wg_utilities.loggers.warehouse_handler import WarehouseHandler


def test_instantiation() -> None:
    """Test that the WarehouseHandler class can be instantiated."""

    with patch.object(
        WarehouseHandler, "_initialize_warehouse"
    ) as mock_initialize_warehouse:
        wh_handler = WarehouseHandler()

    mock_initialize_warehouse.assert_called_once()

    assert isinstance(wh_handler, WarehouseHandler)
    assert isinstance(wh_handler, Handler)
    assert isinstance(wh_handler, JsonApiClient)


def test_initialize_warehouse_new_warehouse(mock_requests: Mocker) -> None:
    """Test that the _initialize_warehouse method works correctly."""

    mock_requests.get(
        "https://item-warehouse.com/v1/warehouses/lumberyard",
        status_code=HTTPStatus.NOT_FOUND,
        reason=HTTPStatus.NOT_FOUND.phrase,
    )

    with patch.object(
        WarehouseHandler, "post_json_response", return_value=WAREHOUSE_SCHEMA
    ) as mock_post_json_response:
        _ = WarehouseHandler(warehouse_host="https://item-warehouse.com")

    mock_post_json_response.assert_called_once_with(
        "/warehouses", json=WarehouseHandler._WAREHOUSE_SCHEMA, timeout=5
    )


def test_initialize_warehouse_already_exists() -> None:
    """Test that the _initialize_warehouse method works correctly."""

    with patch.object(
        WarehouseHandler, "get_json_response", return_value=WAREHOUSE_SCHEMA
    ) as mock_get_json_response:
        _ = WarehouseHandler()

    mock_get_json_response.assert_called_once_with("/warehouses/lumberyard", timeout=5)


def test_initialize_warehouse_already_exists_but_wrong_schema() -> None:
    """Test that the _initialize_warehouse method works correctly."""

    with patch.object(
        WarehouseHandler, "get_json_response", return_value={"invalid": "schema"}
    ) as mock_get_json_response, raises(ValueError) as exc_info:
        _ = WarehouseHandler()

    mock_get_json_response.assert_called_once_with("/warehouses/lumberyard", timeout=5)

    assert (
        str(exc_info.value)
        == 'Warehouse schema does not match expected schema: {"invalid": "schema"}'
    )


@mark.parametrize(
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

    assert WarehouseHandler._get_log_hash(log_record) == expected_hash


@mark.add_handler("warehouse_handler")
@mark.parametrize(("level", "message"), SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL)
def test_emit(level: int, message: str, logger: Logger) -> None:
    """Test that the emit method sends the correct payload to the warehouse."""

    with patch.object(
        WarehouseHandler, "post_json_response"
    ) as mock_post_json_response:
        logger.log(level, message)

    expected_log_payload = {
        "created_at": ANY,
        "file": __file__,
        "level": level,
        "line": 140,
        "log_hash": md5(message.encode()).hexdigest(),
        "log_host": gethostname(),
        "logger": logger.name,
        "message": message,
        "module": "test__warehouse_handler",
        "process": "MainProcess",
        "thread": "MainThread",
    }

    mock_post_json_response.assert_called_once_with(
        "/warehouses/lumberyard/items", json=expected_log_payload
    )


@mark.add_handler("warehouse_handler")
def test_emit_duplicate_record(
    caplog: LogCaptureFixture, logger: Logger, mock_requests: Mocker
) -> None:
    """Test that the emit method doesn't throw an error for duplicate records."""

    caplog.set_level(ERROR)

    mock_requests.post(
        "https://item-warehouse.com/v1/warehouses/lumberyard/items",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        reason=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
        json={"detail": {"type": "ItemExistsError"}},
    )

    logger.info("Info log")
    logger.info("Info log")
    logger.info("Info log")
    logger.info("Info log")
    logger.info("Info log")

    assert not caplog.records


@mark.add_handler("warehouse_handler")
def test_emit_http_error(
    caplog: LogCaptureFixture, logger: Logger, mock_requests: Mocker
) -> None:
    """Test that the emit method logs other HTTP errors."""

    caplog.set_level(ERROR)

    mock_requests.post(
        "https://item-warehouse.com/v1/warehouses/lumberyard/items",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        reason=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
        json={"detail": {"type": "OtherError"}},
    )

    logger.info("Info log")

    assert caplog.records[
        0
    ].message == "Error posting log to Warehouse: 500 Internal Server Error; " + str(
        {"detail": {"type": "OtherError"}}
    )


@mark.add_handler("warehouse_handler")
def test_get_records_parsing(warehouse_handler: WarehouseHandler) -> None:
    """Test that the get_records method returns the correct records."""

    assert len(warehouse_handler.debug_records) == 1

    record = warehouse_handler.debug_records[0]
    assert record.getMessage() == "test message @ level 10"
    assert record.levelno == 10


@mark.parametrize(
    ("level_name", "expected_level_arg"),
    (
        ("critical", 50),
        ("error", 40),
        ("warning", 30),
        ("info", 20),
        ("debug", 10),
    ),
)
def test_records_properties(
    warehouse_handler: WarehouseHandler, level_name: str, expected_level_arg: int
) -> None:
    """Test that each of the record properties make the correct call."""

    records = getattr(warehouse_handler, f"{level_name}_records")

    assert len(records) == 1
    record = records[0]
    assert record.getMessage() == f"test message @ level {expected_level_arg}"
    assert record.levelno == expected_level_arg


@mark.add_handler("warehouse_handler")
@mark.parametrize("allow_connection_errors", (True, False))
def test_allow_connection_errors(
    allow_connection_errors: bool,
    mock_requests: Mocker,
    warehouse_handler: WarehouseHandler,
    logger: Logger,
) -> None:
    """Test that the allow_connection_errors property works correctly."""

    mock_requests.reset_mock()

    mock_requests.get(
        REQUESTS_MOCK_ANY,
        exc=RequestsConnectionError(connection_str := "Connection Error: ¯\\_(ツ)_/¯"),
    )

    mock_requests.post(
        REQUESTS_MOCK_ANY,
        exc=RequestException(request_exc_str := "Request Exception: ︵(ಥ_ಥ)︵"),
    )

    if allow_connection_errors:
        wh_handler = WarehouseHandler(allow_connection_errors=allow_connection_errors)

        assert wh_handler._allow_connection_errors is allow_connection_errors

        warehouse_handler._allow_connection_errors = allow_connection_errors

        logger.info("Info log")
    else:
        with raises(RequestsConnectionError) as conn_exc_info:
            _ = WarehouseHandler(allow_connection_errors=allow_connection_errors)

        assert str(conn_exc_info.value) == connection_str

        warehouse_handler._allow_connection_errors = allow_connection_errors

        with raises(RequestException) as req_exc_info:
            logger.error("Info log")

        assert str(req_exc_info.value) == request_exc_str


@freeze_time("2021-01-01 00:00:00")
@mark.add_handler("warehouse_handler")
def test_pyscript_task_executor(
    logger: Logger, warehouse_handler: WarehouseHandler
) -> None:
    """Test that the pyscript_task_executor works correctly."""

    mock_task_executor = Mock()

    warehouse_handler._pyscript_task_executor = mock_task_executor

    logger.debug("Debug log")
    logger.info("Info log")
    logger.warning("Warning log")
    logger.error("Error log")
    logger.critical("Critical log")

    assert mock_task_executor.call_args_list == [
        call(
            super(WarehouseHandler, warehouse_handler).post_json_response,
            "/warehouses/lumberyard/items",
            params=None,
            header_overrides=None,
            timeout=None,
            json={
                "created_at": 1609459200.0,
                "file": __file__,
                "level": 10,
                "line": ANY,
                "log_hash": md5(b"Debug log").hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Debug log",
                "module": "test__warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
            data=None,
        ),
        call(
            super(WarehouseHandler, warehouse_handler).post_json_response,
            "/warehouses/lumberyard/items",
            params=None,
            header_overrides=None,
            timeout=None,
            json={
                "created_at": 1609459200.0,
                "file": __file__,
                "level": 20,
                "line": ANY,
                "log_hash": md5(b"Info log").hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Info log",
                "module": "test__warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
            data=None,
        ),
        call(
            super(WarehouseHandler, warehouse_handler).post_json_response,
            "/warehouses/lumberyard/items",
            params=None,
            header_overrides=None,
            timeout=None,
            json={
                "created_at": 1609459200.0,
                "file": __file__,
                "level": 30,
                "line": ANY,
                "log_hash": md5(b"Warning log").hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Warning log",
                "module": "test__warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
            data=None,
        ),
        call(
            ANY,
            "/warehouses/lumberyard/items",
            params=None,
            header_overrides=None,
            timeout=None,
            json={
                "created_at": 1609459200.0,
                "file": __file__,
                "level": 40,
                "line": ANY,
                "log_hash": md5(b"Error log").hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Error log",
                "module": "test__warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
            data=None,
        ),
        call(
            ANY,
            "/warehouses/lumberyard/items",
            params=None,
            header_overrides=None,
            timeout=None,
            json={
                "created_at": 1609459200.0,
                "file": __file__,
                "level": 50,
                "line": ANY,
                "log_hash": md5(b"Critical log").hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Critical log",
                "module": "test__warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
            data=None,
        ),
    ]
