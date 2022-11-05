"""Pytest config file, used for creating fixtures etc."""

from __future__ import annotations

from collections.abc import Callable, Generator
from json import dumps, load, loads
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger, LogRecord, getLogger
from os import listdir
from pathlib import Path
from typing import TypeVar, cast
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
from wg_utilities.devices.yamaha_yas_209 import YamahaYas209
from wg_utilities.devices.yamaha_yas_209.yamaha_yas_209 import CurrentTrack
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

FLAT_FILES_DIR = Path(__file__).parent / "tests" / "flat_files"

# <editor-fold desc="JSON Objects">


def fix_colon_keys(json_obj: JSONObj) -> JSONObj:
    """Fix colons replaced with underscores in keys.

    Some keys have colons changed for underscores when they're parsed into Pydantic
    models, this undoes that.

    Args:
        json_obj (dict): the JSON object to fix

    Returns:
        dict: the fixed JSON object
    """

    json_str = dumps(json_obj)

    for key in (
        "xmlns_dc",
        "xmlns_upnp",
        "xmlns_song",
        "upnp_class",
        "song_subid",
        "song_description",
        "song_skiplimit",
        "song_id",
        "song_like",
        "song_singerid",
        "song_albumid",
        "dc_title",
        "dc_creator",
        "upnp_artist",
        "upnp_album",
        "upnp_albumArtURI",
        "dc_creator",
        "song_controls",
    ):
        json_str = json_str.replace(key, key.replace("_", ":"))

    return cast(JSONObj, loads(json_str))


def random_nested_json() -> JSONObj:
    """Return a random nested JSON object."""
    with open(
        FLAT_FILES_DIR / "json" / "random_nested.json",
        encoding="utf-8",
    ) as fin:
        return load(fin)  # type: ignore[no-any-return]


def random_nested_json_with_arrays() -> JSONObj:
    """Return a random nested JSON object with lists as values."""
    with open(
        FLAT_FILES_DIR / "json" / "random_nested_with_arrays.json",
        encoding="utf-8",
    ) as fin:
        return load(fin)  # type: ignore[no-any-return]


def random_nested_json_with_arrays_and_stringified_json() -> JSONObj:
    """Return a random nested JSON object with lists and stringified JSON.

    I've manually stringified the JSON and put it back into itself a couple of times
    for more thorough testing.

    Returns:
        JSONObj: randomly generated JSON
    """
    with open(
        FLAT_FILES_DIR / "json" / "random_nested_with_arrays_and_stringified_json.json",
        encoding="utf-8",
    ) as fin:
        return load(fin)  # type: ignore[no-any-return]


def yamaha_yas_209_get_media_info_responses(
    other_test_parameters: dict[str, CurrentTrack.Info]
) -> YieldFixture[tuple[JSONObj, CurrentTrack.Info | None]]:
    """Yields values for testing against GetMediaInfo responses.

    Yields:
        list: a list of `getMediaInfo` responses
    """
    for file in listdir(
        get_media_info_dir := (
            FLAT_FILES_DIR / "json" / "yamaha_yas_209" / "get_media_info"
        )
    ):
        with open(get_media_info_dir / file, encoding="utf-8") as fin:
            json: JSONObj = load(fin)
            values: CurrentTrack.Info | None = other_test_parameters.get(file)

            yield (json, values)


def yamaha_yas_209_last_change_av_transport_events(
    other_test_parameters: dict[str, CurrentTrack.Info] | None = None
) -> YieldFixture[tuple[JSONObj, CurrentTrack.Info | None] | JSONObj]:
    """Yields values for testing against AVTransport payloads.

    Yields:
        list: a list of `lastChange` events
    """
    other_test_parameters = other_test_parameters or {}
    for file in sorted(
        listdir(
            last_change_dir := (
                FLAT_FILES_DIR
                / "json"
                / "yamaha_yas_209"
                / "event_payloads"
                / "av_transport"
            )
        )
    ):
        with open(last_change_dir / file, encoding="utf-8") as fin:

            # The files are what's saved in HA, but we only need the lastChange object
            json_obj: JSONObj = fix_colon_keys(load(fin))[  # type: ignore[assignment]
                "last_change"
            ]

            if values := other_test_parameters.get(
                file,
            ):
                yield json_obj, values
            elif other_test_parameters:
                # If we're sending 2 arguments for any, we need to send 2 arguments for
                # all
                yield json_obj, None
            else:
                yield (json_obj,)  # type: ignore[misc]


def yamaha_yas_209_last_change_rendering_control_events(
    other_test_parameters: dict[str, CurrentTrack.Info] | None = None
) -> YieldFixture[tuple[JSONObj, CurrentTrack.Info | None] | JSONObj]:
    """Yields values for testing against RenderingControl payloads.

    Yields:
        dict: a `lastChange` event
    """
    other_test_parameters = other_test_parameters or {}
    for file in sorted(
        listdir(
            last_change_dir := (
                FLAT_FILES_DIR
                / "json"
                / "yamaha_yas_209"
                / "event_payloads"
                / "rendering_control"
            )
        )
    ):
        with open(last_change_dir / file, encoding="utf-8") as fin:
            # The files are what's saved in HA, but we only need the lastChange object
            json_obj: JSONObj = fix_colon_keys(load(fin))[  # type: ignore[assignment]
                "last_change"
            ]

            if values := other_test_parameters.get(
                file,
            ):
                yield json_obj, values
            elif other_test_parameters:
                # If we're sending 2 arguments for any, we need to send 2 arguments for
                # all
                yield json_obj, None
            else:
                yield (json_obj,)  # type: ignore[misc]


# </editor-fold>
# <editor-fold desc="Fixtures">


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


@fixture(scope="function", name="yamaha_yas_209")  # type: ignore[misc]
def _yamaha_yas_209() -> YamahaYas209:
    """Fixture for creating a YamahaYAS209 instance."""
    return YamahaYas209("192.168.1.1", start_listener=False, logging=True)


# </editor-fold>
