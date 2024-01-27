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

import pytest
from jwt import encode
from requests import get
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import MissingSchema
from requests_mock import Mocker
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context
from xdist.scheduler.loadscope import (  # type: ignore[import-not-found]
    LoadScopeScheduling,
)

from wg_utilities.clients._spotify_types import SpotifyEntityJson
from wg_utilities.clients.google_calendar import CalendarJson, GoogleCalendarEntityJson
from wg_utilities.clients.google_photos import AlbumJson, MediaItemJson
from wg_utilities.clients.monzo import AccountJson as MonzoAccountJson
from wg_utilities.clients.monzo import PotJson, TransactionJson
from wg_utilities.clients.oauth_client import OAuthCredentials
from wg_utilities.clients.truelayer import AccountJson as TrueLayerAccountJson
from wg_utilities.clients.truelayer import CardJson
from wg_utilities.functions.json import JSONObj

T = TypeVar("T")
YieldFixture = Generator[T, None, None]


class TestError(Exception):
    """Custom exception for testing."""

    __test__ = False


TEST_EXCEPTION = TestError("Test Exception")

# Constants

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


# Functions


class _XdistScheduler(LoadScopeScheduling):  # type: ignore[misc]
    """Custom scheduler to split tests into multiple scopes."""

    def _split_scope(self, nodeid: str) -> str:
        if "devices/yamaha_yas_209" in nodeid:
            return "yamaha_yas_209-tests"

        if "force_mkdir" in nodeid:
            return "force_mkdir-tests"

        return nodeid


def pytest_xdist_make_scheduler(config, log):  # type: ignore[no-untyped-def]
    """Create a custom scheduler to split tests into multiple scopes."""

    return _XdistScheduler(config, log)


def assert_mock_requests_request_history(
    request_history: list[_RequestObjectProxy],
    expected: list[dict[str, str | dict[str, str]]],
) -> None:
    """Assert that the request history matches the expected data."""

    assert len(request_history) == len(expected)

    for i, expected_values in enumerate(expected):
        assert request_history[i].method == expected_values["method"]
        assert (
            request_history[i].url.lower()
            == expected_values["url"].lower()  # type: ignore[union-attr]
        )
        for k, v in expected_values["headers"].items():  # type: ignore[union-attr]
            assert request_history[i].headers[k] == v


# JSON Objects


@overload
def read_json_file(  # type: ignore[overload-overlap]
    rel_file_path: str, host_name: Literal["google/calendar"]
) -> CalendarJson:
    ...


@overload
def read_json_file(  # type: ignore[overload-overlap]
    rel_file_path: str, host_name: Literal["google/photos/v1/albums"]
) -> AlbumJson:
    ...


@overload
def read_json_file(  # type: ignore[overload-overlap]
    rel_file_path: str, host_name: Literal["google/photos/v1/mediaitems"]
) -> dict[Literal["mediaItems"], list[MediaItemJson]]:
    ...


@overload
def read_json_file(  # type: ignore[overload-overlap]
    rel_file_path: str, host_name: Literal["monzo", "monzo/accounts"]
) -> dict[Literal["accounts"], list[MonzoAccountJson]]:
    ...


@overload
def read_json_file(  # type: ignore[overload-overlap]
    rel_file_path: str, host_name: Literal["monzo/pots"]
) -> dict[Literal["pots"], list[PotJson]]:
    ...


@overload
def read_json_file(  # type: ignore[overload-overlap]
    rel_file_path: str, host_name: Literal["monzo/transactions"]
) -> dict[Literal["transactions"], list[TransactionJson]]:
    ...


@overload
def read_json_file(  # type: ignore[overload-overlap]
    rel_file_path: str, host_name: Literal["spotify"]
) -> SpotifyEntityJson:
    ...


@overload
def read_json_file(  # type: ignore[overload-overlap]
    rel_file_path: str, host_name: Literal["truelayer"]
) -> dict[Literal["results"], list[TrueLayerAccountJson | CardJson]]:
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
    | dict[Literal["accounts"], list[MonzoAccountJson]]
    | dict[Literal["pots"], list[PotJson]]
    | dict[Literal["transactions"], list[TransactionJson]]
    | GoogleCalendarEntityJson
    | AlbumJson
    | dict[Literal["mediaItems"], list[MediaItemJson]]
    | dict[Literal["results"], list[TrueLayerAccountJson | CardJson]]
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
    request: _RequestObjectProxy, context: _Context
) -> (
    JSONObj
    | SpotifyEntityJson
    | dict[Literal["accounts"], list[MonzoAccountJson]]
    | dict[Literal["pots"], list[PotJson]]
    | dict[Literal["transactions"], list[TransactionJson]]
    | GoogleCalendarEntityJson
    | AlbumJson
    | dict[Literal["mediaItems"], list[MediaItemJson]]
    | dict[Literal["results"], list[TrueLayerAccountJson | CardJson]]
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
        "api.truelayer.com": "truelayer",
    }[request.hostname]

    try:
        return read_json_file(
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
                md5(
                    request.qs["pagetoken"][0].encode(), usedforsecurity=False
                ).hexdigest(),
            )
            return read_json_file(file_path, host_name=host_name)
        raise  # pragma: no cover


# Fixtures


@pytest.fixture()
def fake_oauth_credentials(live_jwt_token: str) -> OAuthCredentials:
    """Fixture for fake OAuth credentials."""
    return OAuthCredentials(
        access_token=live_jwt_token,
        client_id="test_client_id",
        client_secret="test_client_secret",
        expiry_epoch=int(time()) + 3600,
        refresh_token="test_refresh_token",
        scope="test_scope,test_scope_two",
        token_type="Bearer",
    )


@pytest.fixture(scope="module", name="live_jwt_token")
def live_jwt_token_() -> str:
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


@pytest.fixture(scope="module")
def live_jwt_token_alt() -> str:
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


@pytest.fixture(autouse=True)
def mock_requests_root() -> YieldFixture[Mocker]:
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
            compile_regex(
                r"^https?:\/\/localhost:[0-9]+(\/.*)?$",
            ),
            real_http=True,
        )
        mock_requests.get(
            "http://www.not-a-real-website-abc.com",
            real_http=True,
        )

        yield mock_requests


@pytest.fixture(name="mock_open_browser")
def mock_open_browser_() -> YieldFixture[MagicMock]:
    """Fixture for mocking opening the user's browser."""
    with patch("wg_utilities.clients.oauth_client.open_browser") as mock_open_browser:
        yield mock_open_browser


@pytest.fixture(name="temp_dir")
def temp_dir_() -> YieldFixture[Path]:
    """Fixture for creating a temporary directory."""

    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Create directory for OAuth credentials cache
        (temp_dir_path / "oauth_credentials").mkdir()

        yield temp_dir_path
