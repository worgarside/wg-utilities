"""Pytest config file, used for creating fixtures etc."""

from __future__ import annotations

from collections.abc import Callable, Generator
from http import HTTPStatus
from json import dump, dumps, load, loads
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger, LogRecord, getLogger
from os import environ, listdir, walk
from os.path import join
from pathlib import Path
from re import IGNORECASE
from re import compile as compile_regex
from re import fullmatch
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import Literal, TypeVar, cast
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

from aioresponses import aioresponses
from async_upnp_client.client import UpnpRequester, UpnpService, UpnpStateVariable
from async_upnp_client.const import (
    ServiceInfo,
    StateVariableInfo,
    StateVariableTypeInfo,
)
from boto3 import client
from flask import Flask
from mypy_boto3_lambda import LambdaClient
from mypy_boto3_pinpoint import PinpointClient
from mypy_boto3_s3 import S3Client
from pigpio import _callback
from pytest import FixtureRequest, fixture
from requests import get
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import MissingSchema
from requests_mock import Mocker
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context
from spotipy import SpotifyOAuth
from voluptuous import All, Schema

from wg_utilities.api import TempAuthServer
from wg_utilities.clients import MonzoClient, SpotifyClient
from wg_utilities.clients._generic import OAuthClient, OAuthCredentialsInfo
from wg_utilities.clients.monzo import Account as MonzoAccount
from wg_utilities.clients.monzo import Pot, _MonzoAccountInfo, _MonzoPotInfo
from wg_utilities.clients.spotify import Album as SpotifyAlbum
from wg_utilities.clients.spotify import Artist, Playlist, SpotifyEntity, Track, User
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


SPOTIFY_PATHS_TO_MOCK = [
    _dir_path  # pylint: disable=used-before-assignment
    for root, *_ in walk(f"{FLAT_FILES_DIR}/json/spotify")
    if (_dir_path := root.replace(f"{FLAT_FILES_DIR}/json/spotify", ""))
]
SPOTIFY_PATTERNS_TO_MOCK = [
    # Matches `https://api.spotify.com/v1/<entity_type>s/<entity_id>`
    compile_regex(
        # pylint: disable=line-too-long
        r"^https:\/\/api\.spotify\.com\/v1\/(playlists|tracks|albums|artists|audio\-features)\/([a-z0-9]{22})$",
        flags=IGNORECASE,
    ),
    # Matches `https://api.spotify.com/v1/artists/<entity_id>/albums`
    compile_regex(
        # pylint: disable=line-too-long
        r"^https:\/\/api\.spotify\.com\/v1\/artists/([a-z0-9]{22})/albums(\?limit=50)?$",
        flags=IGNORECASE,
    ),
]

YAS_209_IP = "192.168.1.1"
YAS_209_HOST = f"http://{YAS_209_IP}:49152"


# <editor-fold desc="Functions">


def assert_mock_requests_request_history(
    request_history: list[_RequestObjectProxy],
    expected: list[dict[str, str | dict[str, str]]],
) -> None:
    """Assert that the request history matches the expected data."""

    for i, expected_values in enumerate(expected):
        assert request_history[i].method == expected_values["method"]
        assert request_history[i].url == expected_values["url"]
        for k, v in expected_values["headers"].items():  # type: ignore[union-attr]
            assert request_history[i].headers[k] == v

    assert len(request_history) == len(expected)


# </editor-fold>
# <editor-fold desc="JSON Objects">


def read_json_file(json_dir_path: str) -> JSONObj:
    """Read a JSON file from the flat files `json` subdirectory.

    Args:
        json_dir_path (str): the path to the JSON file, relative to the flat files
            `json` subdirectory
    """
    with open(
        str(FLAT_FILES_DIR / "json" / json_dir_path).lower(), encoding="utf-8"
    ) as fin:
        return cast(JSONObj, load(fin))


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


def get_flat_file_from_url(
    request: _RequestObjectProxy = None, context: _Context = None
) -> JSONObj:
    """Retrieves the content of a flat JSON file for a mocked request response.

    Args:
        request (_RequestObjectProxy): the request object from the `requests` session
        context: the context object from the `requests` session

    Returns:
        dict: the content of the flat JSON file
    """
    context.status_code = HTTPStatus.OK
    context.reason = HTTPStatus.OK.phrase

    file_path = (
        f"spotify/{request.path.replace('/v1/', '')}/{request.query}".rstrip("/")
        + ".json"
    )

    return read_json_file(file_path)


def monzo_account_json(
    request: _RequestObjectProxy = None,
    _: _Context = None,  # noqa: N803
    *,
    account_type: str = "uk_prepaid",
) -> dict[Literal["accounts"], list[_MonzoAccountInfo]]:
    """Return sample Monzo account JSON.

    Args:
        request (_RequestObjectProxy): the request object from the `requests` session
        _: the context object from the `requests` session (unused)
        account_type (str): the type of account to return (if called manually)

    Returns:
        dict: the JSON object

    Raises:
        ValueError: if the account type is invalid
    """
    uk_retail = read_json_file("monzo/account/uk_retail.json")

    if request is not None:
        account_type = request.qs.get("account_type")[0]

    account_list = []

    if account_type == "uk_prepaid":
        account_list.append(read_json_file("monzo/account/uk_prepaid.json"))
    elif account_type == "uk_retail":
        account_list.append(uk_retail)
        account_list.append(read_json_file("monzo/account/uk_retail_closed.json"))

    elif account_type == "uk_monzo_flex":
        account_list.append(read_json_file("monzo/account/uk_monzo_flex.json"))

    elif account_type == "uk_monzo_flex_backing_loan":
        account_list.append(
            read_json_file("monzo/account/uk_monzo_flex_backing_loan_1.json")
        )
        account_list.append(
            read_json_file("monzo/account/uk_monzo_flex_backing_loan_2.json")
        )
        account_list.append(
            read_json_file("monzo/account/uk_monzo_flex_backing_loan_3.json")
        )

    elif account_type == "uk_retail_joint":
        account_list.append(read_json_file("monzo/account/uk_retail_joint.json"))
    else:
        raise ValueError(f"Unknown account type: {account_type!r}")

    return {"accounts": cast(list[_MonzoAccountInfo], account_list)}


def monzo_pot_json() -> dict[Literal["pots"], list[_MonzoPotInfo]]:
    """Return a list of sample Monzo Pot JSON objects.

    Returns:
        list[dict]: the JSON objects
    """
    default_pot_values = {
        "currency": "GBP",
        "type": "default",
        "product_id": "default",
        "isa_wrapper": "",
        "cover_image_url": "https://via.placeholder.com/200x100",
        "round_up": False,
        "round_up_multiplier": None,
        "is_tax_pot": False,
        "locked": False,
        "available_for_bills": True,
        "has_virtual_cards": False,
    }

    return {
        "pots": [
            {
                **default_pot_values,  # type: ignore[misc]
                "id": "test_pot_id_1",
                "name": "Bills",
                "style": "",
                "balance": 50000,
                "current_account_id": "test_account_id",
                "created": "2018-08-23T22:34:19.122Z",
                "updated": "2020-07-10T22:39:33.262Z",
                "deleted": False,
            },
            {
                **default_pot_values,  # type: ignore[misc]
                "id": "test_pot_id_savings",
                "name": "Savings",
                "style": "piggy_bank",
                "balance": 2000000,
                "type": "flexible_savings",
                "product_id": "BigBank_2015-01-01_ISA",
                "isa_wrapper": "ISA",
                "created": "2019-05-15T06:54:56.762Z",
                "updated": "2020-07-10T22:39:34.638Z",
                "deleted": False,
                "available_for_bills": False,
            },
            {
                **default_pot_values,  # type: ignore[misc]
                "id": "test_pot_id_2",
                "name": "New Car",
                "style": "",
                "balance": 0,
                "goal_amount": 100000000,
                "created": "2019-06-05T06:59:17.502Z",
                "updated": "2020-07-10T22:39:34.703Z",
                "deleted": True,
            },
            {
                **default_pot_values,  # type: ignore[misc]
                "id": "test_pot_id_3",
                "name": "Ibiza Mad One",
                "style": "teal",
                "balance": 0,
                "goal_amount": 50000,
                "created": "2019-05-14T16:51:39.657Z",
                "updated": "2020-07-10T22:39:34.529Z",
                "deleted": True,
            },
            {
                **default_pot_values,  # type: ignore[misc]
                "id": "test_pot_id_4",
                "name": "Round Ups",
                "style": "cactus",
                "balance": 5000,
                "round_up": True,
                "round_up_multiplier": 1,
                "created": "2020-11-05T22:55:54.031Z",
                "updated": "2021-06-15T09:50:39.238Z",
                "deleted": False,
                "locked": True,
                "lock_type": "until_date",
                "locked_until": "2026-04-20T00:00:00Z",
            },
        ]
    }


def random_nested_json() -> JSONObj:
    """Return a random nested JSON object."""
    return read_json_file("random_nested.json")


def random_nested_json_with_arrays() -> JSONObj:
    """Return a random nested JSON object with lists as values."""
    return read_json_file("random_nested_with_arrays.json")


def random_nested_json_with_arrays_and_stringified_json() -> JSONObj:
    """Return a random nested JSON object with lists and stringified JSON.

    I've manually stringified the JSON and put it back into itself a couple of times
    for more thorough testing.

    Returns:
        JSONObj: randomly generated JSON
    """
    return read_json_file("random_nested_with_arrays_and_stringified_json.json")


def spotify_get_entity_by_id_json_callback(
    request: _RequestObjectProxy, _: _Context  # noqa: N803
) -> JSONObj:
    """Return a Spotify entity JSON object.

    Args:
        request (_RequestObjectProxy): the request object from the `requests` session
        _: the context object from the `requests` session (unused)

    Returns:
        JSONObj: the JSON object
    """
    *_, entity_type, entity_id = request.path.split("/")
    return read_json_file(f"spotify/{entity_type}/{entity_id}.json")


def yamaha_yas_209_get_media_info_responses(
    other_test_parameters: dict[str, CurrentTrack.Info]
) -> YieldFixture[tuple[JSONObj, CurrentTrack.Info | None]]:
    """Yields values for testing against GetMediaInfo responses.

    Yields:
        list: a list of `getMediaInfo` responses
    """
    for file in listdir(FLAT_FILES_DIR / "json" / "yamaha_yas_209" / "get_media_info"):
        json = read_json_file(f"yamaha_yas_209/get_media_info/{file}")
        values: CurrentTrack.Info | None = other_test_parameters.get(file)

        yield (json, values)


def yamaha_yas_209_last_change_av_transport_event_singular() -> JSONObj:
    """Returns a single AVTransport LastChange payloads.

    Returns:
        JSONObj: a `LastChange` event
    """

    json_obj = fix_colon_keys(
        read_json_file(
            join(
                "yamaha_yas_209",
                "event_payloads",
                "av_transport",
                "payload_20221013234843601604.json",
            )
        )
    )["last_change"]

    return cast(JSONObj, json_obj)


def yamaha_yas_209_last_change_av_transport_events(
    other_test_parameters: dict[str, CurrentTrack.Info] | None = None
) -> YieldFixture[tuple[JSONObj, CurrentTrack.Info | None] | JSONObj]:
    """Yields values for testing against AVTransport payloads.

    Args:
        other_test_parameters (dict[str, CurrentTrack.Info], optional): a dictionary
            of values which are returned for given files. Defaults to None.

    Yields:
        list: a list of `lastChange` events
    """
    other_test_parameters = other_test_parameters or {}
    for file in sorted(
        listdir(
            FLAT_FILES_DIR
            / "json"
            / "yamaha_yas_209"
            / "event_payloads"
            / "av_transport"
        )
    ):
        json_obj = cast(
            JSONObj,
            fix_colon_keys(
                read_json_file(f"yamaha_yas_209/event_payloads/av_transport/{file}")
            )["last_change"],
        )

        if values := other_test_parameters.get(
            file,
        ):
            yield json_obj, values
        elif other_test_parameters:
            # If we're sending 2 arguments for any, we need to send 2 arguments for all
            yield json_obj, None
        else:
            # Removing the parentheses here gives me typing errors, and removing
            # the comma makes the `yield` statement fail for some reason
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
            FLAT_FILES_DIR
            / "json"
            / "yamaha_yas_209"
            / "event_payloads"
            / "rendering_control"
        )
    ):
        json_obj = cast(
            JSONObj,
            fix_colon_keys(
                read_json_file(
                    f"yamaha_yas_209/event_payloads/rendering_control/{file}"
                )
            )["last_change"],
        )

        if values := other_test_parameters.get(
            file,
        ):
            yield json_obj, values
        elif other_test_parameters:
            # If we're sending 2 arguments for any, we need to send 2 arguments for all
            yield json_obj, None
        else:
            # Removing the parentheses here gives me typing errors, and removing
            # the comma makes the `yield` statement fail for some reason
            yield (json_obj,)  # type: ignore[misc]


# </editor-fold>
# <editor-fold desc="Fixtures">


@fixture(scope="function", name="aws_credentials_env_vars")  # type: ignore[misc]
def _aws_credentials_env_vars() -> YieldFixture[None]:
    """Mocks environment variables.

    This is done here instead of in`pyproject.toml` because `pytest-aws-config` blocks
    consuming AWS credentials from all env vars.
    """
    with patch.dict(
        environ,
        {
            "AWS_ACCESS_KEY_ID": "AKIATESTTESTTESTTEST",
            "AWS_SECRET_ACCESS_KEY": "T3ST/S3CuR17Y*K3Y[S7R1NG!?L00K5.L1K3.17!",
            "AWS_SECURITY_TOKEN": "ANYVALUEWEWANTINHERE",
            "AWS_SESSION_TOKEN": "ASLONGASITISNOTREAL",
            "AWS_DEFAULT_REGION": "eu-west-1",
        },
    ):
        yield


@fixture(scope="function", name="current_track_null")  # type: ignore[misc]
def _current_track_null() -> CurrentTrack:
    """Return a CurrentTrack object with null values."""
    return CurrentTrack(
        album_art_uri=None,
        media_album_name=None,
        media_artist=None,
        media_duration=0.0,
        media_title=None,
    )


@fixture(scope="function", name="dht22_sensor")  # type: ignore[misc]
def _dht22_sensor(pigpio_pi: MagicMock) -> DHT22Sensor:
    """Fixture for DHT22 sensor."""

    return DHT22Sensor(pigpio_pi, 4)


@fixture(scope="function", name="fake_oauth_credentials")  # type: ignore[misc]
def _fake_oauth_credentials() -> dict[str, OAuthCredentialsInfo]:
    """Fixture for fake OAuth credentials."""
    return {
        "test_client_id": {
            "access_token": "test_access_token",
            "client_id": "test_client_id",
            "expires_in": 3600,
            "refresh_token": "test_refresh_token",
            "scope": "test_scope,test_scope_two",
            "token_type": "Bearer",
            "user_id": "test_user_id",
        }
    }


@fixture(scope="session", name="flask_app")  # type: ignore[misc]
def _flask_app() -> Flask:
    """Fixture for Flask app."""

    return Flask(__name__)


@fixture(scope="function", name="lambda_client")  # type: ignore[misc]
def _lambda_client(
    aws_credentials_env_vars: None,  # pylint: disable=unused-argument
) -> LambdaClient:
    """Fixture for creating a boto3 client instance for Lambda Functions."""
    return client("lambda")


@fixture(scope="function", name="list_handler")  # type: ignore[misc]
def _list_handler() -> ListHandler:
    """Fixture for creating a ListHandler instance."""
    l_handler = ListHandler(log_ttl=None)
    l_handler.setLevel(DEBUG)
    return l_handler


@fixture(scope="function", name="list_handler_prepopulated")  # type: ignore[misc]
def _list_handler_prepopulated(
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

    if name_marker := request.node.get_closest_marker("mocked_operation_lookup"):
        mocked_operation_lookup = name_marker.args[0]
    else:
        mocked_operation_lookup = {}

    return MockBoto3Client(mocked_operation_lookup=mocked_operation_lookup)


@fixture(scope="function", name="mock_aiohttp")  # type: ignore[misc]
def _mock_aiohttp() -> YieldFixture[aioresponses]:
    """Fixture for mocking async HTTP requests."""

    with aioresponses() as mock_aiohttp:
        for root, _, files in walk(
            get_dir := FLAT_FILES_DIR
            / "xml"
            / "yamaha_yas_209"
            / "aiohttp_responses"
            / "get"
        ):
            for file in files:
                with open(join(root, file), "rb") as fin:
                    body = fin.read()

                mock_aiohttp.get(
                    f"{YAS_209_HOST}{join(root, file).replace(str(get_dir), '') }",
                    status=HTTPStatus.OK,
                    reason=HTTPStatus.OK.phrase,
                    body=body,
                    repeat=True,
                )

        yield mock_aiohttp


@fixture(scope="function", name="mock_requests")  # type: ignore[misc]
def _mock_requests(request: FixtureRequest) -> YieldFixture[Mocker]:
    """Fixture for mocking sync HTTP requests."""

    def _whoami_json_cb(
        request: _RequestObjectProxy = None,
        _: _Context = None,  # noqa: N803
    ) -> dict[Literal["authenticated"], bool]:
        return {
            "authenticated": request.headers["Authorization"]
            != "Bearer expired_access_token",
        }

    with Mocker(real_http=False) as mock_requests:
        if fullmatch(
            r"^tests/unit/clients/monzo/test__[a-z_]+\.py$", request.node.parent.name
        ):
            mock_requests.get(
                f"{MonzoClient.BASE_URL}/ping/whoami",
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
                json=_whoami_json_cb,
            )

            mock_requests.get(
                f"{MonzoClient.BASE_URL}/balance",
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
                json={
                    "balance": 10000,
                    "balance_including_flexible_savings": 50000,
                    "currency": "GBP",
                    "local_currency": "",
                    "local_exchange_rate": "",
                    "local_spend": [{"spend_today": -115, "currency": "GBP"}],
                    "spend_today": -115,
                    "total_balance": 10000,
                },
            )

            mock_requests.put(
                f"{MonzoClient.BASE_URL}/pots/test_pot_id/deposit",
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
            )

            mock_requests.get(
                f"{MonzoClient.BASE_URL}/accounts",
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
                json=monzo_account_json,
            )

            mock_requests.get(
                f"{MonzoClient.BASE_URL}/pots",
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
                json=monzo_pot_json(),
            )

            mock_requests.post(
                MonzoClient.ACCESS_TOKEN_ENDPOINT,
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
                json={
                    "access_token": "test_access_token_new",
                    "client_id": "test_client_id",
                    "expires_in": 3600,
                    "refresh_token": "test_refresh_token_new",
                    "scope": "test_scope,test_scope_two",
                    "token_type": "Bearer",
                    "user_id": "test_user_id",
                },
            )
        elif fullmatch(
            r"^tests/unit/clients/spotify/test__[a-z_]+\.py$", request.node.parent.name
        ):
            for url in SPOTIFY_PATHS_TO_MOCK:
                mock_requests.get(
                    SpotifyClient.BASE_URL + url, json=get_flat_file_from_url
                )
            for pattern in SPOTIFY_PATTERNS_TO_MOCK:
                mock_requests.get(
                    pattern,
                    json=get_flat_file_from_url,
                )

            # Special case because it goes to a single file, not a directory with
            # querystring-files
            mock_requests.get(
                SpotifyClient.BASE_URL + "/me/player/currently-playing",
                json=get_flat_file_from_url,
            )

            for method in ("put", "delete"):
                for entity_type in ("albums", "following", "tracks"):
                    mock_requests.register_uri(
                        method,
                        SpotifyClient.BASE_URL + f"/me/{entity_type}",
                        status_code=HTTPStatus.OK,
                        reason=HTTPStatus.OK.phrase,
                    )

                mock_requests.register_uri(
                    method,
                    # Matches `/v1/playlists/<playlist id>/followers`
                    compile_regex(
                        # pylint: disable=line-too-long
                        r"^https:\/\/api\.spotify\.com\/v1\/playlists/([a-z0-9]{22})/followers",
                        flags=IGNORECASE,
                    ),
                    status_code=HTTPStatus.OK,
                    reason=HTTPStatus.OK.phrase,
                )

        yield mock_requests


@fixture(scope="function", name="monzo_account")  # type: ignore[misc]
def _monzo_account(monzo_client: MonzoClient) -> MonzoAccount:
    """Fixture for creating a MonzoAccount instance."""

    return MonzoAccount(
        json=monzo_account_json(account_type="uk_retail")["accounts"][0],
        monzo_client=monzo_client,
    )


@fixture(scope="function", name="monzo_client")  # type: ignore[misc]
def _monzo_client(
    temp_dir: Path,
    fake_oauth_credentials: dict[str, OAuthCredentialsInfo],
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> MonzoClient:
    """Fixture for creating a MonzoClient instance."""

    with open(
        creds_cache_path := temp_dir / "monzo_credentials.json",
        "w",
        encoding="utf-8",
    ) as fout:
        dump(fake_oauth_credentials, fout)

    return MonzoClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        log_requests=True,
        creds_cache_path=Path(creds_cache_path),
    )


@fixture(scope="function", name="monzo_pot")  # type: ignore[misc]
def _monzo_pot() -> Pot:
    """Fixture for creating a Pot instance."""

    return Pot(
        json={
            "id": "test_pot_id",
            "name": "Pot Name",
            "style": "",
            "balance": 50,
            "currency": "GBP",
            "type": "default",
            "product_id": "default",
            "current_account_id": "test_account_id",
            "cover_image_url": "https://via.placeholder.com/200x100",
            "isa_wrapper": "",
            "round_up": True,
            "round_up_multiplier": None,
            "is_tax_pot": False,
            "created": "2020-01-01T01:00:00.000Z",
            "updated": "2020-01-01T02:00:00.000Z",
            "deleted": False,
            "locked": False,
            "available_for_bills": True,
            "has_virtual_cards": False,
            "goal_amount": None,
            "charity_id": None,
        }
    )


@fixture(scope="function", name="oauth_client")  # type: ignore[misc]
def _oauth_client(
    logger: Logger,
    temp_dir: Path,
    fake_oauth_credentials: dict[str, OAuthCredentialsInfo],
) -> OAuthClient:
    """Fixture for creating an OAuthClient instance."""

    with open(
        creds_cache_path := temp_dir / "oauth_credentials.json",
        "w",
        encoding="utf-8",
    ) as fout:
        dump(fake_oauth_credentials, fout)

    return OAuthClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        base_url="https://api.example.com",
        access_token_endpoint="https://api.example.com/oauth2/token",
        log_requests=True,
        creds_cache_path=Path(creds_cache_path),
        logger=logger,
    )


@fixture(scope="function", name="pigpio_pi")  # type: ignore[misc]
def _pigpio_pi() -> YieldFixture[MagicMock]:
    """Fixture for creating a `pigpio.pi` instance."""

    pi = MagicMock()

    pi.INPUT = 0
    pi.OUTPUT = 1

    pi.callback.return_value = _callback(MagicMock(), 4)

    return pi


@fixture(scope="function", name="pinpoint_client")  # type: ignore[misc]
def _pinpoint_client() -> PinpointClient:
    """Fixture for creating a boto3 client instance for Pinpoint."""
    return client("pinpoint")


@fixture(scope="function", name="s3_client")  # type: ignore[misc]
def _s3_client(
    aws_credentials_env_vars: None,  # pylint: disable=unused-argument
) -> S3Client:
    """Fixture for creating a boto3 client instance for S3."""
    return client("s3")


@fixture(scope="function", name="sample_log_record")  # type: ignore[misc]
def _sample_log_record() -> LogRecord:
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


@fixture(scope="function", name="server_thread")  # type: ignore[misc]
def _server_thread(flask_app: Flask) -> YieldFixture[TempAuthServer.ServerThread]:
    """Fixture for creating a server thread."""

    server_thread = TempAuthServer.ServerThread(flask_app)
    server_thread.start()

    yield server_thread

    server_thread.shutdown()
    del server_thread


@fixture(scope="function", name="spotify_album")  # type: ignore[misc]
def _spotify_album(spotify_client: SpotifyClient) -> SpotifyAlbum:
    """Fixture for creating a Spotify `Album` instance."""

    return SpotifyAlbum(
        json=read_json_file(  # type: ignore[arg-type]
            "spotify/albums/4julBAGYv4WmRXwhjJ2LPD.json"
        ),
        spotify_client=spotify_client,
    )


@fixture(scope="function", name="spotify_artist")  # type: ignore[misc]
def _spotify_artist(spotify_client: SpotifyClient) -> Artist:
    """Fixture for creating a Spotify `Artist` instance."""

    return Artist(
        json=read_json_file(  # type: ignore[arg-type]
            "spotify/artists/1Ma3pJzPIrAyYPNRkp3SUF.json"
        ),
        spotify_client=spotify_client,
    )


@fixture(scope="function", name="spotify_client")  # type: ignore[misc]
def _spotify_client(
    fake_oauth_credentials: dict[str, OAuthCredentialsInfo],
    temp_dir: Path,
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> SpotifyClient:
    """Fixture for creating a `SpotifyClient` instance."""

    with open(
        creds_cache_path := temp_dir / "oauth_credentials.json",
        "w",
        encoding="utf-8",
    ) as fout:
        dump(fake_oauth_credentials, fout)

    spotify_oauth_manager = MagicMock(auto_spec=SpotifyOAuth)
    spotify_oauth_manager.get_access_token.return_value = "test_access_token"

    return SpotifyClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        log_requests=True,
        creds_cache_path=Path(creds_cache_path),
        oauth_manager=spotify_oauth_manager,
    )


@fixture(scope="function", name="spotify_entity")  # type: ignore[misc]
def _spotify_entity(spotify_client: SpotifyClient) -> SpotifyEntity:
    """Fixture for creating a `SpotifyEntity` instance."""

    return SpotifyEntity(
        json={
            "href": "https://api.spotify.com/v1/artists/0gxyHStUsqpMadRV0Di1Qt",
            "id": "0gxyHStUsqpMadRV0Di1Qt",
            "uri": "spotify:artist:0gxyHStUsqpMadRV0Di1Qt",
            "external_urls": {
                "spotify": "https://open.spotify.com/artist/0gxyHStUsqpMadRV0Di1Qt"
            },
        },
        spotify_client=spotify_client,
    )


@fixture(scope="function", name="spotify_playlist")  # type: ignore[misc]
def _spotify_playlist(spotify_client: SpotifyClient) -> Playlist:
    """Fixture for creating a `Playlist` instance."""

    return Playlist(
        json=read_json_file(  # type: ignore[arg-type]
            "spotify/playlists/2lMx8FU0SeQ7eA5kcMlNpX.json"
        ),
        spotify_client=spotify_client,
    )


@fixture(scope="function", name="spotify_track")  # type: ignore[misc]
def _spotify_track(spotify_client: SpotifyClient) -> Track:
    """Fixture for creating a `Track` instance."""

    return Track(
        json=read_json_file(  # type: ignore[arg-type]
            "spotify/tracks/27cgqh0vrhvem61ugtnord.json"
        ),
        spotify_client=spotify_client,
    )


@fixture(scope="function", name="spotify_user")  # type: ignore[misc]
def _spotify_user(spotify_client: SpotifyClient) -> User:
    """Fixture for creating a Spotify User instance."""

    return User(
        json=read_json_file("spotify/me.json"),  # type: ignore[arg-type]
        spotify_client=spotify_client,
    )


@fixture(scope="function", name="temp_auth_server")  # type: ignore[misc]
def _temp_auth_server() -> YieldFixture[TempAuthServer]:
    """Fixture for creating a temporary auth server."""

    temp_auth_server = TempAuthServer(__name__, auto_run=False, debug=True)

    yield temp_auth_server

    temp_auth_server.stop_server()


@fixture(scope="session", name="temp_dir")  # type: ignore[misc]
def _temp_dir() -> YieldFixture[Path]:
    """Fixture for creating a temporary directory."""

    with TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@fixture(scope="function", name="upnp_service_av_transport")  # type: ignore[misc]
def _upnp_service_av_transport() -> UpnpService:
    """Fixture for creating an UpnpService instance."""
    return UpnpService(
        UpnpRequester(),
        service_info=ServiceInfo(
            control_url="/upnp/control/rendertransport1",
            event_sub_url="/upnp/event/rendertransport1",
            scpd_url="/upnp/scpd/rendertransport1",
            service_id="urn:upnp-org:serviceId:AVTransport",
            service_type="urn:schemas-upnp-org:service:AVTransport:1",
            xml=ElementTree.fromstring(
                dedent(
                    # pylint: disable=line-too-long
                    """
                        <ns0:service xmlns:ns0="urn:schemas-upnp-org:device-1-0">
                            <ns0:serviceType>urn:schemas-upnp-org:service:AVTransport:1
                            </ns0:serviceType>
                            <ns0:serviceId>urn:upnp-org:serviceId:AVTransport</ns0:serviceId>
                            <ns0:SCPDURL>/upnp/rendertransportSCPD.xml</ns0:SCPDURL>
                            <ns0:controlURL>/upnp/control/rendertransport1</ns0:controlURL>
                            <ns0:eventSubURL>/upnp/event/rendertransport1</ns0:eventSubURL>
                        </ns0:service>
                    """
                ).strip()
            ),
        ),
        state_variables=[],
        actions=[],
    )


@fixture(scope="function", name="upnp_service_rendering_control")  # type: ignore[misc]
def _upnp_service_rendering_control() -> UpnpService:
    """Fixture for creating an UpnpService instance."""
    return UpnpService(
        UpnpRequester(),
        service_info=ServiceInfo(
            control_url="/upnp/control/rendercontrol1",
            event_sub_url="/upnp/event/rendercontrol1",
            scpd_url="/upnp/rendercontrolSCPD.xml",
            service_id="urn:upnp-org:serviceId:RenderingControl",
            service_type="urn:schemas-upnp-org:service:RenderingControl:1",
            xml=ElementTree.fromstring(
                dedent(
                    """
            <ns0:service xmlns:ns0="urn:schemas-upnp-org:device-1-0">
                <ns0:serviceType>urn:schemas-upnp-org:service:RenderingControl:1
                </ns0:serviceType>
                <ns0:serviceId>urn:upnp-org:serviceId:RenderingControl</ns0:serviceId>
                <ns0:SCPDURL>/upnp/rendercontrolSCPD.xml</ns0:SCPDURL>
                <ns0:controlURL>/upnp/control/rendercontrol1</ns0:controlURL>
                <ns0:eventSubURL>/upnp/event/rendercontrol1</ns0:eventSubURL>
            </ns0:service>
                    """
                ).strip()
            ),
        ),
        state_variables=[],
        actions=[],
    )


@fixture(scope="function", name="upnp_state_variable")  # type: ignore[misc]
def _upnp_state_variable(request: FixtureRequest) -> UpnpStateVariable:
    """Fixture for creating an UpnpStateVariable instance."""
    state_var = UpnpStateVariable(
        StateVariableInfo(
            name="LastChange",
            send_events=True,
            type_info=StateVariableTypeInfo(
                data_type="string",
                data_type_mapping={"type": str, "in": str, "out": str},
                default_value=None,
                allowed_value_range={},
                allowed_values=None,
                xml=(
                    last_change_xml := ElementTree.fromstring(
                        dedent(
                            # pylint: disable=line-too-long
                            """
                                <ns0:stateVariable xmlns:ns0="urn:schemas-upnp-org:service-1-0" sendEvents="yes">
                                    <ns0:name>LastChange</ns0:name>
                                    <ns0:dataType>string</ns0:dataType>
                                </ns0:stateVariable>
                            """
                        ).strip()
                    )
                ),
            ),
            xml=last_change_xml,
        ),
        schema=Schema(
            schema=All(),
        ),
    )

    if name_marker := request.node.get_closest_marker("upnp_value_path"):
        with open(name_marker.args[0], encoding="utf-8") as fin:
            state_var.upnp_value = fin.read()

    return state_var


@fixture(scope="function", name="yamaha_yas_209")  # type: ignore[misc]
def _yamaha_yas_209() -> YieldFixture[YamahaYas209]:
    """Fixture for creating a YamahaYAS209 instance."""

    yas_209 = YamahaYas209(
        YAS_209_IP,
        start_listener=False,
        logging=True,
        listen_ip="192.168.1.2",
        listen_port=12345,
    )

    yield yas_209


# </editor-fold>
