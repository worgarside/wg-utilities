"""Pytest config file, used for creating fixtures etc."""

from __future__ import annotations

from collections.abc import Callable, Generator
from http import HTTPStatus
from json import dumps, loads
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger, LogRecord, getLogger
from os import environ, listdir
from pathlib import Path
from re import IGNORECASE
from re import compile as compile_regex
from re import fullmatch
from tempfile import TemporaryDirectory
from textwrap import dedent
from time import sleep, time
from typing import Any, Literal, TypeVar, cast, overload
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
from jwt import decode, encode
from mypy_boto3_lambda import LambdaClient
from mypy_boto3_s3 import S3Client
from pigpio import _callback
from pytest import FixtureRequest, fixture
from requests import get
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import MissingSchema
from requests_mock import Mocker
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context
from voluptuous import All, Schema

from wg_utilities.api import TempAuthServer
from wg_utilities.clients import GoogleCalendarClient, MonzoClient, SpotifyClient
from wg_utilities.clients._google import GoogleClient
from wg_utilities.clients._spotify_types import SpotifyBaseEntityJson, SpotifyEntityJson
from wg_utilities.clients.google_calendar import (
    Calendar,
    CalendarJson,
    GoogleCalendarEntityJson,
)
from wg_utilities.clients.monzo import Account as MonzoAccount
from wg_utilities.clients.monzo import AccountJson, Pot, PotJson, TransactionJson
from wg_utilities.clients.oauth_client import OAuthClient, OAuthCredentials
from wg_utilities.clients.spotify import Album as SpotifyAlbum
from wg_utilities.clients.spotify import Artist, Playlist, SpotifyEntity, Track, User
from wg_utilities.devices.dht22 import DHT22Sensor
from wg_utilities.devices.yamaha_yas_209 import YamahaYas209
from wg_utilities.devices.yamaha_yas_209.yamaha_yas_209 import CurrentTrack
from wg_utilities.functions import force_mkdir
from wg_utilities.functions.json import JSONObj
from wg_utilities.loggers import ListHandler
from wg_utilities.testing import MockBoto3Client

T = TypeVar("T")
YieldFixture = Generator[T, None, None]

# <editor-fold desc="Constants">

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


YAS_209_IP = "192.168.1.1"
YAS_209_HOST = f"http://{YAS_209_IP}:49152"

# </editor-fold>
# <editor-fold desc="Functions">


def assert_mock_requests_request_history(
    request_history: list[_RequestObjectProxy],
    expected: list[dict[str, str | dict[str, str]]],
) -> None:
    """Assert that the request history matches the expected data."""

    for i, expected_values in enumerate(expected):
        assert request_history[i].method == expected_values["method"]
        assert (
            request_history[i].url.lower()
            == expected_values["url"].lower()  # type: ignore[union-attr]
        )
        for k, v in expected_values["headers"].items():  # type: ignore[union-attr]
            assert request_history[i].headers[k] == v

    assert len(request_history) == len(expected)


def get_jwt_expiry(token: str) -> float:
    """Get the expiry time of a JWT token."""
    return float(decode(token, options={"verify_signature": False})["exp"])


# </editor-fold>
# <editor-fold desc="JSON Objects">


@overload
def read_json_file(  # type: ignore[misc]
    rel_file_path: str, host_name: Literal["google/calendars"]
) -> CalendarJson:
    ...


@overload
def read_json_file(  # type: ignore[misc]
    rel_file_path: str, host_name: Literal["monzo", "monzo/accounts"]
) -> dict[Literal["accounts"], list[AccountJson]]:
    ...


@overload
def read_json_file(  # type: ignore[misc]
    rel_file_path: str, host_name: Literal["monzo/pots"]
) -> dict[Literal["pots"], list[PotJson]]:
    ...


@overload
def read_json_file(  # type: ignore[misc]
    rel_file_path: str, host_name: Literal["monzo/transactions"]
) -> dict[Literal["transactions"], list[TransactionJson]]:
    ...


@overload
def read_json_file(  # type: ignore[misc]
    rel_file_path: str, host_name: Literal["spotify"]
) -> SpotifyEntityJson:
    ...


@overload
def read_json_file(rel_file_path: str, host_name: str | None) -> JSONObj:
    ...


@overload
def read_json_file(rel_file_path: str) -> JSONObj:
    ...


def read_json_file(
    rel_file_path: str, host_name: str | None = None
) -> JSONObj | SpotifyEntityJson | dict[Literal["accounts"], list[AccountJson]] | dict[
    Literal["pots"], list[PotJson]
] | dict[Literal["transactions"], list[TransactionJson]] | GoogleCalendarEntityJson:
    """Read a JSON file from the flat files `json` subdirectory.

    Args:
        rel_file_path (str): the path to the JSON file, relative to the flat files
            `json` subdirectory or its children
        host_name (str, optional): the name of the host to which the JSON file
            belongs. Defaults to None. This isn't necessary at all (because you could
            just prepend the `rel_file_path` instead); it's just used for typing info.

    Returns:
        JSONObj | SpotifyEntityJson: the JSON object from the file
    """

    file_path = FLAT_FILES_DIR / "json"
    if host_name:
        file_path /= host_name.lower()

    file_path /= rel_file_path.lstrip("/").lower()

    return cast(JSONObj, loads(file_path.read_text()))


def fix_colon_keys(json_obj: JSONObj | SpotifyEntityJson) -> JSONObj:
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
) -> SpotifyEntityJson | dict[Literal["accounts"], list[AccountJson]] | dict[
    Literal["pots"], list[PotJson]
]:
    """Retrieves the content of a flat JSON file for a mocked request response.

    Args:
        request (_RequestObjectProxy): the request object from the `requests` session
        context: the context object from the `requests` session

    Returns:
        dict: the content of the flat JSON file
    """
    context.status_code = HTTPStatus.OK
    context.reason = HTTPStatus.OK.phrase

    if request.hostname == "www.googleapis.com":
        for child in GoogleClient.__subclasses__():
            if request.url.startswith(
                base_url := child.BASE_URL  # type: ignore[attr-defined]
            ):
                file_path = (
                    "/".join(
                        [
                            request.path.replace(
                                base_url.split(request.hostname)[-1], ""
                            ),
                            request.query,
                        ]
                    ).rstrip("/")
                    + ".json"
                )
    else:
        file_path = (
            f"{request.path.replace('/v1/', '')}/{request.query}".rstrip("/") + ".json"
        )

    return read_json_file(  # type: ignore[return-value]
        file_path,
        host_name={
            "api.spotify.com": "spotify",
            "api.monzo.com": "monzo",
            "www.googleapis.com": "google",
        }[request.hostname],
    )


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


def spotify_create_playlist_callback(
    request: _RequestObjectProxy, _: _Context
) -> JSONObj:
    """Callback for mock requests to create a new playlist.

    Args:
        request (_RequestObjectProxy): the request object from the `requests` session
        _: the context object from the `requests` session (unused)

    Returns:
        JSONObj: the JSON response
    """
    res = read_json_file("spotify/users/worgarside/playlists.json")

    if request.json()["collaborative"] is True:
        res["collaborative"] = True
    else:
        res["collaborative"] = False

    if request.json()["public"] is True:
        res["public"] = True
    else:
        res["public"] = False

    return res


def yamaha_yas_209_get_media_info_responses(
    other_test_parameters: dict[str, CurrentTrack.Info]
) -> YieldFixture[tuple[JSONObj | SpotifyEntityJson, CurrentTrack.Info | None]]:
    """Yields values for testing against GetMediaInfo responses.

    Yields:
        list: a list of `getMediaInfo` responses
    """
    for file in listdir(FLAT_FILES_DIR / "json" / "yamaha_yas_209" / "get_media_info"):
        json = read_json_file(f"yamaha_yas_209/get_media_info/{file}")
        values: CurrentTrack.Info | None = other_test_parameters.get(file)

        yield json, values


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


def yamaha_yas_209_last_change_rendering_control_events() -> YieldFixture[JSONObj]:
    """Yields values for testing against RenderingControl payloads.

    Yields:
        dict: a `lastChange` event
    """
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

        yield json_obj


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


@fixture(scope="function", name="calendar")  # type: ignore[misc]
def _calendar(google_calendar_client: GoogleCalendarClient) -> Calendar:
    """Fixture for a Google Calendar instance."""
    return Calendar.from_json_response(
        read_json_file("primary.json", host_name="google/calendars"),
        google_client=google_calendar_client,
    )


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
def _fake_oauth_credentials(live_jwt_token: str) -> OAuthCredentials:
    """Fixture for fake OAuth credentials."""
    return OAuthCredentials(
        access_token=live_jwt_token,
        client_id="test_client_id",
        client_secret="test_client_secret",
        expiry_epoch=time() + 3600,
        refresh_token="test_refresh_token",
        scope="test_scope,test_scope_two",
        token_type="Bearer",
    )


@fixture(scope="session", name="flask_app")  # type: ignore[misc]
def _flask_app() -> Flask:
    """Fixture for Flask app."""

    return Flask(__name__)


@fixture(scope="function", name="google_calendar_client")  # type: ignore[misc]
def _google_calendar_client(
    temp_dir: Path,
    fake_oauth_credentials: OAuthCredentials,
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> GoogleCalendarClient:
    """Fixture for `GoogleCalendarClient` instance."""

    (creds_cache_path := temp_dir / "google_calendar_credentials.json").write_text(
        fake_oauth_credentials.json()
    )

    return GoogleCalendarClient(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret",
        scopes=[
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
        ],
        creds_cache_path=creds_cache_path,
    )


@fixture(scope="module", name="live_jwt_token")  # type: ignore[misc]
def _live_jwt_token() -> str:
    """Fixture for a live JWT token."""
    return str(
        encode(
            {
                "iss": "test",
                "sub": "test",
                "aud": "test",
                "exp": int(time()) + 3600,
            },
            "test_access_token",
        )
    )


@fixture(scope="module", name="live_jwt_token_alt")  # type: ignore[misc]
def _live_jwt_token_alt() -> str:
    """Another fixture for a live JWT token."""
    return str(
        encode(
            {
                "iss": "test",
                "sub": "test",
                "aud": "test",
                "exp": int(time()) + 3600,
            },
            "new_test_access_token",
        )
    )


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
        for path_object in (
            get_dir := FLAT_FILES_DIR
            / "xml"
            / "yamaha_yas_209"
            / "aiohttp_responses"
            / "get"
        ).rglob("*"):
            if path_object.is_file():
                mock_aiohttp.get(
                    YAS_209_HOST + "/" + str(path_object.relative_to(get_dir)),
                    status=HTTPStatus.OK,
                    reason=HTTPStatus.OK.phrase,
                    body=path_object.read_bytes(),
                    repeat=True,
                )

        yield mock_aiohttp


@fixture(scope="function", name="mock_requests")  # type: ignore[misc]
def _mock_requests(
    request: FixtureRequest, live_jwt_token_alt: str
) -> YieldFixture[Mocker]:
    """Fixture for mocking sync HTTP requests."""

    with Mocker(real_http=False) as mock_requests:
        if fullmatch(
            r"^tests/unit/clients/monzo/test__[a-z_]+\.py$", request.node.parent.name
        ):
            for path_object in (monzo_dir := FLAT_FILES_DIR / "json" / "monzo").rglob(
                "*"
            ):
                if path_object.is_dir():
                    mock_requests.get(
                        MonzoClient.BASE_URL
                        + "/"
                        + str(path_object.relative_to(monzo_dir)),
                        json=get_flat_file_from_url,
                    )

            mock_requests.put(
                f"{MonzoClient.BASE_URL}/pots/pot_0000000000000000000014/deposit",
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
            )
        elif fullmatch(
            r"^tests/unit/clients/oauth_client/test__[a-z_]+\.py$",
            request.node.parent.name,
        ):
            mock_requests.post(
                "https://api.example.com/oauth2/token",
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
                json={
                    "access_token": live_jwt_token_alt,
                    "client_id": "test_client_id",
                    "expires_in": 3600,
                    "refresh_token": "new_test_refresh_token",
                    "scope": "test_scope,test_scope_two",
                    "token_type": "Bearer",
                },
            )
        elif fullmatch(
            r"^tests/unit/clients/spotify/test__[a-z_]+\.py$", request.node.parent.name
        ):

            for path_object in (
                spotify_dir := FLAT_FILES_DIR / "json" / "spotify"
            ).rglob("*"):
                if path_object.is_dir():
                    mock_requests.get(
                        SpotifyClient.BASE_URL
                        + "/"
                        + str(path_object.relative_to(spotify_dir)),
                        json=get_flat_file_from_url,
                    )

            for pattern in (
                # Matches `https://api.spotify.com/v1/<entity_type>s/<entity_id>`
                compile_regex(
                    # pylint: disable=line-too-long
                    r"^https:\/\/api\.spotify\.com\/v1\/(playlists|tracks|albums|artists|audio\-features|users)\/([a-z0-9]{4,22})$",
                    flags=IGNORECASE,
                ),
                # Matches `https://api.spotify.com/v1/artists/<entity_id>/albums`
                compile_regex(
                    # pylint: disable=line-too-long
                    r"^https:\/\/api\.spotify\.com\/v1\/artists/([a-z0-9]{22})/albums(\?limit=50)?$",
                    flags=IGNORECASE,
                ),
            ):
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

            mock_requests.post(
                # Matches `/v1/playlists/<playlist id>/tracks`
                compile_regex(
                    # pylint: disable=line-too-long
                    r"^https:\/\/api\.spotify\.com\/v1\/playlists/([a-z0-9]{22})/tracks",
                    flags=IGNORECASE,
                ),
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
                json={"snapshot_id": "MTAsZDVmZjMjJhZTVmZjcxOGNlMA=="},
            )

            mock_requests.post(
                "https://api.spotify.com/v1/users/worgarside/playlists",
                status_code=HTTPStatus.OK,
                reason=HTTPStatus.OK.phrase,
                json=spotify_create_playlist_callback,
            )
        elif fullmatch(
            r"^tests/unit/clients/google/test__[a-z_]+\.py$", request.node.parent.name
        ):
            for path_object in (FLAT_FILES_DIR / "json" / "google").rglob("*"):
                if path_object.is_dir():
                    mock_requests.get(
                        GoogleCalendarClient.BASE_URL
                        + "/"
                        + str(
                            path_object.relative_to(FLAT_FILES_DIR / "json" / "google")
                        ),
                        json=get_flat_file_from_url,
                    )

                mock_requests.get(
                    f"{GoogleCalendarClient.BASE_URL}/calendars/primary",
                    json=get_flat_file_from_url,
                )

        yield mock_requests


@fixture(scope="function", name="monzo_account")  # type: ignore[misc]
def _monzo_account(monzo_client: MonzoClient) -> MonzoAccount:
    """Fixture for creating a MonzoAccount instance."""

    return MonzoAccount.from_json_response(
        read_json_file("account_Type=uk_retail.json", host_name="monzo/accounts")[
            "accounts"
        ][0],
        monzo_client=monzo_client,
    )


@fixture(scope="function", name="monzo_client")  # type: ignore[misc]
def _monzo_client(
    temp_dir: Path,
    fake_oauth_credentials: OAuthCredentials,
    mock_requests: Mocker,  # pylint: disable=unused-argument
    mock_open_browser: Mocker,  # pylint: disable=unused-argument
) -> MonzoClient:
    """Fixture for creating a MonzoClient instance."""

    (creds_cache_path := temp_dir / "monzo_credentials.json").write_text(
        fake_oauth_credentials.json()
    )

    return MonzoClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        log_requests=True,
        creds_cache_path=creds_cache_path,
    )


@fixture(scope="function", name="monzo_pot")  # type: ignore[misc]
def _monzo_pot() -> Pot:
    """Fixture for creating a Pot instance."""

    return Pot(
        **read_json_file(
            "current_account_id=acc_0000000000000000000000.json",
            host_name="monzo/pots",
        )["pots"][14]
    )


@fixture(scope="function", name="oauth_client")  # type: ignore[misc]
def _oauth_client(
    temp_dir: Path,
    fake_oauth_credentials: OAuthCredentials,
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> OAuthClient[dict[str, Any]]:
    """Fixture for creating an OAuthClient instance."""

    (
        creds_cache_path := force_mkdir(
            temp_dir / "oauth_credentials" / "test_client_id.json", path_is_file=True
        )
    ).write_text(fake_oauth_credentials.json(exclude_none=True))

    return OAuthClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        base_url="https://api.example.com",
        access_token_endpoint="https://api.example.com/oauth2/token",
        log_requests=True,
        creds_cache_path=Path(creds_cache_path),
        auth_link_base="https://api.example.com/oauth2/authorize",
    )


@fixture(scope="function", name="mock_open_browser")  # type: ignore[misc]
def _mock_open_browser() -> YieldFixture[MagicMock]:

    with patch("wg_utilities.clients.oauth_client.open_browser") as mock_open_browser:
        yield mock_open_browser


@fixture(scope="function", name="pigpio_pi")  # type: ignore[misc]
def _pigpio_pi() -> YieldFixture[MagicMock]:
    """Fixture for creating a `pigpio.pi` instance."""

    pi = MagicMock()

    pi.INPUT = 0
    pi.OUTPUT = 1

    pi.callback.return_value = _callback(MagicMock(), 4)

    return pi


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
    """Fixture for creating a Spotify `Album` instance.

    3210 (Ross from Friends Remix)
    https://open.spotify.com/track/5U5X1TnRhnp9GogRfaE9XQ
    """

    return SpotifyAlbum.from_json_response(
        read_json_file("albums/4julBAGYv4WmRXwhjJ2LPD.json", host_name="spotify"),
        spotify_client=spotify_client,
    )


@fixture(scope="function", name="spotify_artist")  # type: ignore[misc]
def _spotify_artist(spotify_client: SpotifyClient) -> Artist:
    """Fixture for creating a Spotify `Artist` instance.

    Ross from Friends
    https://open.spotify.com/artist/1Ma3pJzPIrAyYPNRkp3SUF
    """

    return Artist.from_json_response(
        read_json_file("artists/1Ma3pJzPIrAyYPNRkp3SUF.json", host_name="spotify"),
        spotify_client=spotify_client,
    )


@fixture(scope="function", name="spotify_client")  # type: ignore[misc]
def _spotify_client(
    fake_oauth_credentials: OAuthCredentials,
    temp_dir: Path,
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> SpotifyClient:
    """Fixture for creating a `SpotifyClient` instance."""

    (creds_cache_path := temp_dir / "oauth_credentials.json").write_text(
        fake_oauth_credentials.json(exclude_none=True)
    )

    return SpotifyClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        log_requests=True,
        creds_cache_path=Path(creds_cache_path),
    )


@fixture(scope="function", name="spotify_entity")  # type: ignore[misc]
def _spotify_entity(
    spotify_client: SpotifyClient,
) -> SpotifyEntity[SpotifyBaseEntityJson]:
    """Fixture for creating a `SpotifyEntity` instance."""

    return SpotifyEntity.from_json_response(
        {
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
    """Fixture for creating a `Playlist` instance.

    Chill Electronica
    https://open.spotify.com/playlist/2lMx8FU0SeQ7eA5kcMlNpX
    """

    return Playlist.from_json_response(
        read_json_file("playlists/2lmx8fu0seq7ea5kcmlnpx.json", host_name="spotify"),
        spotify_client=spotify_client,
    )


@fixture(scope="function", name="spotify_track")  # type: ignore[misc]
def _spotify_track(spotify_client: SpotifyClient) -> Track:
    """Fixture for creating a `Track` instance."""

    return Track.from_json_response(
        read_json_file("tracks/27cgqh0vrhvem61ugtnord.json", host_name="spotify"),
        spotify_client=spotify_client,
    )


@fixture(scope="function", name="spotify_user")  # type: ignore[misc]
def _spotify_user(spotify_client: SpotifyClient) -> User:
    """Fixture for creating a Spotify User instance."""

    return User.from_json_response(
        read_json_file("me.json", host_name="spotify"),
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

    if yas_209.is_listening:  # pragma: no cover
        yas_209.stop_listening()

        while yas_209.is_listening:
            sleep(0.1)


# </editor-fold>
