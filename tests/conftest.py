"""Pytest config file, used for creating fixtures etc."""

from __future__ import annotations

from collections.abc import Callable, Generator
from hashlib import md5
from http import HTTPStatus
from json import loads
from pathlib import Path
from re import compile as compile_regex
from tempfile import TemporaryDirectory
from time import time
from typing import Literal, TypeVar, cast, overload
from unittest.mock import MagicMock, patch
from urllib.parse import quote, unquote

from jwt import encode
from pytest import fixture
from requests import get
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import MissingSchema
from requests_mock import Mocker
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context
from xdist.scheduler.loadscope import LoadScopeScheduling

from wg_utilities.clients._spotify_types import SpotifyEntityJson
from wg_utilities.clients.google_calendar import CalendarJson, GoogleCalendarEntityJson
from wg_utilities.clients.google_photos import AlbumJson, MediaItemJson
from wg_utilities.clients.monzo import AccountJson, PotJson, TransactionJson
from wg_utilities.clients.oauth_client import OAuthCredentials
from wg_utilities.functions.json import JSONObj

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

FLAT_FILES_DIR = Path(__file__).parent / "flat_files"


# </editor-fold>
# <editor-fold desc="Functions">


class _XdistScheduler(LoadScopeScheduling):  # type: ignore[misc]
    # pylint: disable=too-few-public-methods
    """Custom scheduler to split tests into multiple scopes."""

    def _split_scope(self, nodeid: str) -> str:
        if "devices/yamaha_yas_209" in nodeid:
            return "yamaha_yas_209-tests"
        return nodeid


def pytest_xdist_make_scheduler(config, log):  # type: ignore[no-untyped-def]
    """Create a custom scheduler to split tests into multiple scopes."""

    return _XdistScheduler(config, log)


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


# </editor-fold>
# <editor-fold desc="JSON Objects">


@overload
def read_json_file(  # type: ignore[misc]
    rel_file_path: str, host_name: Literal["google/calendar"]
) -> CalendarJson:
    ...


@overload
def read_json_file(  # type: ignore[misc]
    rel_file_path: str, host_name: Literal["google/photos/v1/albums"]
) -> AlbumJson:
    ...


@overload
def read_json_file(  # type: ignore[misc]
    rel_file_path: str, host_name: Literal["google/photos/v1/mediaitems"]
) -> dict[Literal["mediaItems"], list[MediaItemJson]]:
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
) -> (
    JSONObj
    | SpotifyEntityJson
    | dict[Literal["accounts"], list[AccountJson]]
    | dict[Literal["pots"], list[PotJson]]
    | dict[Literal["transactions"], list[TransactionJson]]
    | GoogleCalendarEntityJson
    | AlbumJson
    | dict[Literal["mediaItems"], list[MediaItemJson]]
):
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

    if rel_file_path.startswith(":"):
        file_path = file_path.parent / (file_path.name + rel_file_path)
    else:
        file_path /= rel_file_path.lstrip("/").lower()

    return cast(JSONObj, loads(file_path.read_text()))


def get_flat_file_from_url(
    request: _RequestObjectProxy = None, context: _Context = None
) -> (
    SpotifyEntityJson
    | dict[Literal["accounts"], list[AccountJson]]
    | dict[Literal["pots"], list[PotJson]]
):
    # pylint: disable=missing-raises-doc
    """Retrieve the content of a flat JSON file for a mocked request response.

    Args:
        request (_RequestObjectProxy): the request object from the `requests` session
        context: the context object from the `requests` session

    Returns:
        dict: the content of the flat JSON file

    Raises:
        ValueError: if the URL is not recognised
    """
    context.status_code = HTTPStatus.OK
    context.reason = HTTPStatus.OK.phrase

    file_path = f"{request.path}/{request.query}".rstrip("/") + ".json"

    host_name = {
        "api.spotify.com": "spotify",
        "api.monzo.com": "monzo",
        "www.googleapis.com": "google",
        "photoslibrary.googleapis.com": "google/photos",
    }[request.hostname]

    try:
        return read_json_file(  # type: ignore[return-value]
            file_path,
            host_name=host_name,
        )
    except FileNotFoundError as exc:  # pragma: no cover
        raise ValueError(
            "Unable to dynamically load JSON file for "
            f"https://{request.hostname}{request.path}?{unquote(request.query)}"
        ) from exc
    except OSError:
        if "pagetoken" in request.qs and len(request.qs["pagetoken"]) == 1:
            file_path = file_path.replace(
                quote(request.qs["pagetoken"][0]).lower(),
                md5(request.qs["pagetoken"][0].encode()).hexdigest(),
            )
            return read_json_file(  # type: ignore[return-value]
                file_path, host_name=host_name
            )
        raise  # pragma: no cover


# </editor-fold>
# <editor-fold desc="Fixtures">


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


@fixture(  # type: ignore[misc]
    scope="function", name="mock_requests_root", autouse=True
)
def _mock_requests_root() -> YieldFixture[Mocker]:
    """Fixture for mocking sync HTTP requests."""

    with Mocker(real_http=False, case_sensitive=False) as mock_requests:
        mock_requests.get(
            compile_regex(
                # pylint: disable=line-too-long
                r"^https?:\/\/(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]):[0-9]+(\/.*)?$",
            ),
            real_http=True,
        )
        mock_requests.get(
            "http://www.not-a-real-website-abc.com",
            real_http=True,
        )

        yield mock_requests


@fixture(scope="function", name="mock_open_browser")  # type: ignore[misc]
def _mock_open_browser() -> YieldFixture[MagicMock]:
    with patch("wg_utilities.clients.oauth_client.open_browser") as mock_open_browser:
        yield mock_open_browser


@fixture(scope="function", name="temp_dir")  # type: ignore[misc]
def _temp_dir() -> YieldFixture[Path]:
    """Fixture for creating a temporary directory."""

    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Create directory for OAuth credentials cache
        (temp_dir_path / "oauth_credentials").mkdir()

        yield temp_dir_path


# </editor-fold>
