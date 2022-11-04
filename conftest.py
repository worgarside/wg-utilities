"""Pytest config file, used for creating fixtures etc."""

from __future__ import annotations

from collections.abc import Generator
from json import load
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger, LogRecord, getLogger
from pathlib import Path
from typing import Callable, TypeVar
from unittest.mock import MagicMock

from boto3 import client
from mypy_boto3_lambda import LambdaClient
from mypy_boto3_pinpoint import PinpointClient
from mypy_boto3_s3 import S3Client
from pigpio import _callback
from pytest import FixtureRequest, fixture
from requests import get
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import MissingSchema

from wg_utilities.devices.dht22 import DHT22Sensor
from wg_utilities.functions.json import JSONObj
from wg_utilities.loggers import ListHandler
from wg_utilities.testing import MockBoto3Client

T = TypeVar("T")
YieldFixture = Generator[T, None, None]

EXCEPTION_GENERATORS: list[
    tuple[
        type[Exception],
        Callable[..., object],
        tuple[object, ...],
    ]
] = [
    (AttributeError, lambda arg1: arg1.keys(), ([1, 2, 3],)),
    (
        RequestsConnectionError,
        get,
        ("http://www.not-a-real-website-abc.com",),
    ),
    (FileNotFoundError, open, ("nonexistent_file.txt", "r")),
    (IsADirectoryError, open, (Path(__file__).parent, "r")),
    (IndexError, lambda arg1: arg1[10], ([1, 2, 3],)),
    (KeyError, lambda arg1: arg1["missing"], ({"key": "value"},)),
    (LookupError, lambda arg1: arg1["missing"], ({"key": "value"},)),
    (MissingSchema, get, ("completely invalid",)),
    # pylint: disable=undefined-variable
    (NameError, lambda: dog, ()),  # type: ignore[name-defined]  # noqa: F821
    (TypeError, lambda arg1, arg2: arg1 + arg2, ("string", 10)),
    (UnicodeError, lambda arg1: arg1.encode("ascii"), ("\u2013",)),
    (UnicodeEncodeError, lambda arg1: arg1.encode("ascii"), ("\u2013",)),
    (ValueError, int, ("string",)),
    (ZeroDivisionError, lambda: 1 / 0, ()),
]


def random_nested_json() -> JSONObj:
    """Return a random nested JSON object."""
    with open(
        Path(__file__).parent / "tests" / "flat_files" / "json" / "random_nested.json",
        encoding="utf-8",
    ) as fin:
        return load(fin)  # type: ignore[no-any-return]


def random_nested_json_with_arrays() -> JSONObj:
    """Return a random nested JSON object with lists as values."""
    with open(
        Path(__file__).parent
        / "tests"
        / "flat_files"
        / "json"
        / "random_nested_with_arrays.json",
        encoding="utf-8",
    ) as fin:
        return load(fin)  # type: ignore[no-any-return]


def random_nested_json_with_arrays_and_stringified_json() -> JSONObj:
    """Return a random nested JSON object with lists and stringified JSON.

    I've manually stringified the JSON and put it back into itself a couple of times
    for more thorough testing.
    """
    with open(
        Path(__file__).parent
        / "tests"
        / "flat_files"
        / "json"
        / "random_nested_with_arrays_and_stringified_json.json",
        encoding="utf-8",
    ) as fin:
        return load(fin)  # type: ignore[no-any-return]


@fixture(scope="function")  # type: ignore[misc]
def dht22_sensor(pigpio_pi: MagicMock) -> DHT22Sensor:
    """Fixture for DHT22 sensor."""

    return DHT22Sensor(pigpio_pi, 4)


@fixture(scope="function", name="lambda_client")  # type: ignore[misc]
def _lambda_client() -> LambdaClient:
    """Fixture for creating a boto3 client instance for Lambda Functions."""
    return client("lambda")


@fixture(scope="function", name="list_handler")  # type: ignore[misc]
def _list_handler() -> ListHandler:
    """Fixture for creating a ListHandler instance."""
    l_handler = ListHandler(log_ttl=None)
    l_handler.setLevel(DEBUG)
    return l_handler


@fixture(scope="function")  # type: ignore[misc]
def list_handler_prepopulated(
    logger: Logger,
    list_handler: ListHandler,
    sample_log_record_messages_with_level: list[tuple[int, str]],
) -> ListHandler:
    """Fixture for creating a ListHandler instance with a pre-populated list."""
    logger.addHandler(list_handler)

    for level, message in sample_log_record_messages_with_level:
        logger.log(level, message)

    return list_handler


@fixture(scope="function", name="logger")  # type: ignore[misc]
def _logger() -> YieldFixture[Logger]:
    """Fixture for creating a logger."""

    _logger = getLogger("test_logger")
    _logger.setLevel(DEBUG)

    yield _logger

    _logger.handlers.clear()


@fixture(scope="function", name="mb3c")  # type: ignore[misc]
def _mb3c(request: FixtureRequest) -> MockBoto3Client:
    """Fixture for creating a MockBoto3Client instance."""
    print(type(request))
    if name_marker := request.node.get_closest_marker("mocked_operation_lookup"):
        mocked_operation_lookup = name_marker.args[0]
    else:
        mocked_operation_lookup = {}

    return MockBoto3Client(mocked_operation_lookup=mocked_operation_lookup)


@fixture(scope="function", name="pinpoint_client")  # type: ignore[misc]
def _pinpoint_client() -> PinpointClient:
    """Fixture for creating a boto3 client instance for Pinpoint."""
    return client("pinpoint")


@fixture(scope="function")  # type: ignore[misc]
def sample_log_record() -> LogRecord:
    """Fixture for creating a sample log record."""
    return LogRecord(
        name="test_logger",
        level=10,
        pathname=__file__,
        lineno=0,
        msg="test message",
        args=(),
        exc_info=None,
        func=None,
    )


@fixture(  # type: ignore[misc]
    scope="function", name="sample_log_record_messages_with_level"
)
def _sample_log_record_messages_with_level() -> list[tuple[int, str]]:
    """Fixture for creating a list of sample log records."""
    log_levels = [DEBUG, INFO, WARNING, ERROR, CRITICAL] * 5

    return [
        (level, f"Test log message #{i} at level {level}")
        for i, level in enumerate(log_levels)
    ]


@fixture(scope="function", name="s3_client")  # type: ignore[misc]
def _s3_client() -> S3Client:
    """Fixture for creating a boto3 client instance for S3."""
    return client("s3")


@fixture(scope="function", name="pigpio_pi")  # type: ignore[misc]
def _pigpio_pi() -> YieldFixture[MagicMock]:
    """Fixture for creating a pigpio.pi instance."""

    pi = MagicMock()

    pi.INPUT = 0
    pi.OUTPUT = 1

    pi.callback.return_value = _callback(MagicMock(), 4)

    return pi
