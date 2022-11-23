# pylint: disable=too-few-public-methods
"""Generic OAuth client to allow for reusable authentication flows/checks etc."""
from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from http import HTTPStatus
from json import JSONDecodeError, dumps
from logging import DEBUG, getLogger
from pathlib import Path
from random import choice
from string import ascii_letters
from time import time
from typing import Any, Generic, Literal, TypeVar
from urllib.parse import urlencode
from webbrowser import open as open_browser

from jwt import DecodeError, decode
from pydantic import BaseModel, Extra
from pydantic.generics import GenericModel
from requests import Response, get, post

from wg_utilities.api import TempAuthServer
from wg_utilities.functions import user_data_dir
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


class BaseModelWithConfig(BaseModel):
    """Reusable `BaseModel` with Config to apply to all subclasses."""

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
        extra = Extra.forbid
        validate_assignment = True


class GenericModelWithConfig(GenericModel):
    """Reusable `GenericModel` with Config to apply to all subclasses."""

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
        extra = Extra.forbid
        validate_assignment = True


class OAuthCredentials(BaseModelWithConfig):
    """Typing info for OAuth credentials."""

    access_token: str
    client_id: str
    expiry_epoch: float
    refresh_token: str
    scope: str
    token_type: Literal["Bearer"]

    # Spotify & Google
    client_secret: str | None

    # Monzo
    user_id: str | None

    # Google
    token: str | None
    token_uri: str | None
    scopes: list[str] | None

    @classmethod
    def parse_first_time_login(cls, value: dict[str, Any]) -> OAuthCredentials:
        """Parse the response from a first time login into a credentials object.

        The following fields are returned per API:
        +---------------+--------+-------+---------+-----------+
        |               | Google | Monzo | Spotify | TrueLayer |
        +===============+========+=======+=========+===========+
        | access_token  |    X   |   X   |    X    |     X     |
        | client_id     |    X   |   X   |    X    |     X     |
        | expiry_epoch  |    X   |   X   |    X    |     X     |
        | refresh_token |    X   |   X   |    X    |     X     |
        | scope         |    X   |   X   |    X    |     X     |
        | token_type    |    X   |   X   |    X    |     X     |
        | client_secret |    X   |       |    X    |           |
        | user_id       |        |   X   |         |           |
        | token         |    X   |       |         |           |
        | token_uri     |    X   |       |         |           |
        | scopes        |    X   |       |         |           |
        +---------------+--------+-------+---------+-----------+

        Args:
            value:

        Returns:
            OAuthCredentials: an OAuthCredentials instance

        Raises:
            ValueError: if `expiry` and `expiry_epoch` aren't the same
        """

        # Calculate the expiry time of the access token
        try:
            # Try to decode it if it's a valid JWT (with expiry)
            expiry_epoch = decode(
                value["access_token"],
                options={"verify_signature": False},
            )["exp"]
            value.pop("expires_in", None)
        except (DecodeError, KeyError):
            # If that's not possible, calculate it from the expires_in value
            expires_in = value.pop("expires_in")

            # Subtract 2.5 seconds to account for latency
            expiry_epoch = time() + expires_in - 2.5

            # Verify it against the expiry time string
            if expiry_time_str := value.get("expiry"):
                expiry_time = datetime.fromisoformat(expiry_time_str)
                if abs(expiry_epoch - expiry_time.timestamp()) > 60:
                    raise ValueError(  # pylint: disable=raise-missing-from
                        "`expiry` and `expires_in` are not consistent with each other:"
                        f" expiry: {expiry_time_str}, expires_in: {expiry_epoch}"
                    )

        value["expiry_epoch"] = expiry_epoch

        return cls(**value)

    def update_access_token(
        self, new_token: str, expires_in: int, refresh_token: str | None = None
    ) -> None:
        """Update the access token and expiry time.

        Args:
            new_token (str): the newly refreshed access token
            expires_in (int): the number of seconds until the token expires
            refresh_token (str, optional): a new refresh token. Defaults to unset.
        """
        self.access_token = new_token
        self.expiry_epoch = time() + expires_in - 2.5

        if refresh_token is not None:
            self.refresh_token = refresh_token

    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired.

        Returns:
            bool: True if the token is expired, False otherwise
        """
        return self.expiry_epoch < time()


GetJsonResponse = TypeVar("GetJsonResponse")


class OAuthClient(Generic[GetJsonResponse]):
    """Custom client for interacting with OAuth APIs.

    Includes all necessary/basic authentication functionality
    """

    ACCESS_TOKEN_EXPIRY_THRESHOLD = 150

    DEFAULT_PARAMS: dict[str, object] = {}

    def __init__(
        self,
        *,
        base_url: str,
        access_token_endpoint: str,
        auth_link_base: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str = "http://0.0.0.0:5001/get_auth_code",
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
        scopes: list[str] | None = None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self.base_url = base_url
        self.access_token_endpoint = access_token_endpoint
        self.auth_link_base = auth_link_base
        self.redirect_uri = redirect_uri
        self.log_requests = log_requests
        self._creds_cache_path = creds_cache_path

        self.scopes = scopes or []

        self._credentials: OAuthCredentials
        self._temp_auth_server: TempAuthServer

        if self._creds_cache_path:
            self._load_local_credentials()

    def _get(self, url: str, params: dict[str, object] | None = None) -> Response:
        """Wrapper for GET requests which covers authentication, URL parsing, etc. etc.

        Args:
            url (str): the URL path to the endpoint (not necessarily including the
             base URL)
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            Response: the response from the HTTP request
        """
        if params:
            params.update(
                {k: v for k, v in self.DEFAULT_PARAMS.items() if k not in params}
            )
        else:
            params = deepcopy(self.DEFAULT_PARAMS)

        if url.startswith("/"):
            url = f"{self.base_url}{url}"

        if self.log_requests:
            LOGGER.debug("GET %s with params %s", url, dumps(params, default=str))

        res = get(
            url,
            headers=self.request_headers,
            params=params,  # type: ignore[arg-type]
        )

        res.raise_for_status()

        return res

    def _load_local_credentials(self) -> bool:
        try:
            self._credentials = OAuthCredentials.parse_file(self.creds_cache_path)
        except FileNotFoundError:
            return False

        return True

    def _post(
        self,
        url: str,
        *,
        json: dict[str, str | int | float | bool | list[str] | dict[object, object]]
        | None = None,
        header_overrides: dict[str, str] | None = None,
        params: dict[
            str, str | bytes | int | float | Iterable[str | bytes | int | float]
        ]
        | None = None,
        data: dict[str, object] | None = None,
    ) -> Response:
        """Wrapper for POST requests which covers authentication, URL parsing, etc. etc.

        Args:
            url (str): the URL path to the endpoint (not necessarily including the
             base URL)
            json (dict): the data to be passed in the HTTP request

        Returns:
            Response: the response from the HTTP request
        """

        if url.startswith("/"):
            url = f"{self.base_url}{url}"

        if self.log_requests:
            LOGGER.debug("POST %s with data %s", url, dumps(json or {}, default=str))

        res = post(
            url,
            headers=header_overrides
            if header_overrides is not None
            else self.request_headers,
            json=json or {},
            params=params or {},
            data=data or {},
        )

        res.raise_for_status()

        return res

    def delete_creds_file(self) -> None:
        """Delete the local creds file."""
        self.creds_cache_path.unlink(missing_ok=True)

    def get_json_response(
        self,
        url: str,
        params: dict[str, str | int | object] | None = None,
    ) -> GetJsonResponse:
        """Gets a simple JSON object from a URL.

        Args:
            url (str): the API endpoint to GET
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            dict: the JSON from the response
        """
        try:
            res = self._get(url, params=params)
            if res.status_code == HTTPStatus.NO_CONTENT:
                return {}  # type: ignore[return-value]

            return res.json()  # type: ignore[no-any-return]
        except JSONDecodeError:
            return {}  # type: ignore[return-value]

    def refresh_access_token(self) -> None:
        """Refreshes access token."""

        if not hasattr(self, "_credentials") and not self._load_local_credentials():
            # If we don't have any credentials, we can't refresh the access token -
            # perform first time login and leave it at that
            self.run_first_time_login()
            return

        LOGGER.info("Refreshing access token")

        res = post(
            self.access_token_endpoint,
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.credentials.refresh_token,
            },
        )

        res.raise_for_status()

        self.credentials.update_access_token(
            new_token=res.json()["access_token"],
            expires_in=res.json()["expires_in"],
            # Monzo
            refresh_token=res.json().get("refresh_token"),
        )

        self.creds_cache_path.write_text(self.credentials.json(exclude_none=True))

    def run_first_time_login(self) -> None:
        """Runs the first time login process.

        This is a blocking call which will not return until the user has
        authenticated with the OAuth provider.
        """
        LOGGER.info("Performing first time login")

        state_token = "".join(choice(ascii_letters) for _ in range(32))

        auth_link = (
            self.auth_link_base
            + "?"
            + urlencode(
                {
                    "client_id": self._client_id,
                    "redirect_uri": self.redirect_uri,
                    "response_type": "code",
                    "state": state_token,
                    "scope": " ".join(self.scopes),
                }
            )
        )
        LOGGER.debug("Opening %s", auth_link)
        open_browser(auth_link)

        request_args = self.temp_auth_server.wait_for_request(
            "/get_auth_code", kill_on_request=True
        )

        if state_token != request_args.get("state"):
            raise ValueError(
                "State token received in request doesn't match expected value: "
                f"`{request_args.get('state')}` != `{state_token}`"
            )

        res = self._post(
            self.access_token_endpoint,
            data={
                "code": request_args["code"],
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self.redirect_uri,
            },
            header_overrides={},
        )

        credentials = res.json()

        if self._client_id:
            credentials["client_id"] = self._client_id

        if self._client_secret:
            credentials["client_secret"] = self._client_secret

        self.credentials = OAuthCredentials.parse_first_time_login(credentials)

    @property
    def access_token(self) -> str | None:
        """Access token.

        Returns:
            str: the access token for this bank's API
        """
        if self.access_token_has_expired:
            self.refresh_access_token()

        return self.credentials.access_token

    @property
    def access_token_has_expired(self) -> bool:
        """Decodes the JWT access token and evaluates the expiry time.

        Returns:
            bool: has the access token expired?
        """
        if not hasattr(self, "_credentials"):
            if not self._load_local_credentials():
                return True

        return (
            self.credentials.expiry_epoch < time() + self.ACCESS_TOKEN_EXPIRY_THRESHOLD
        )

    @property
    def client_id(self) -> str:
        """Client ID for the Google API.

        Returns:
            str: the current client ID
        """

        return self._client_id or self.credentials.client_id

    @property
    def client_secret(self) -> str | None:
        """Client secret.

        Returns:
            str: the current client secret
        """

        return self._client_secret or self.credentials.client_secret

    @property
    def credentials(self) -> OAuthCredentials:
        """Gets creds as necessary (including first time setup) and authenticates them.

        Returns:
            OAuthCredentials: the credentials for the chosen bank

        Raises:
            ValueError: if the state token returned from the request doesn't match the
             expected value
        """
        if not hasattr(self, "_credentials") and not self._load_local_credentials():
            self.run_first_time_login()

        return self._credentials

    @credentials.setter
    def credentials(self, value: OAuthCredentials) -> None:
        """Sets the client's credentials, and write to the local cache file."""

        self._credentials = value

        self.creds_cache_path.write_text(
            dumps(self._credentials.dict(exclude_none=True))
        )

    @property
    def creds_cache_path(self) -> Path:
        """Path to the credentials cache file.

        Returns:
            Path: the path to the credentials cache file

        Raises:
            ValueError: if the path to the credentials cache file is not set, and can't
                be generated due to a lack of client ID
        """
        if self._creds_cache_path:
            return self._creds_cache_path

        if (
            not (hasattr(self, "_credentials") and self._credentials)
            and not self._client_id
        ):
            raise ValueError(
                "Unable to get client ID to generate path for credentials cache file."
            )

        return user_data_dir(
            file_name=f"oauth_credentials/{type(self).__name__}/{self.client_id}.json"
        )

    @property
    def request_headers(self) -> dict[str, str]:
        """Headers to be used in requests to the API.

        Returns:
            dict: auth headers for HTTP requests
        """
        return {"Authorization": f"Bearer {self.access_token}"}

    @property
    def refresh_token(self) -> str:
        """Refresh token.

        Returns:
            str: the API refresh token
        """
        return self.credentials.refresh_token

    @property
    def temp_auth_server(self) -> TempAuthServer:
        """Creates a temporary HTTP server for the auth flow.

        Returns:
            TempAuthServer: the temporary server
        """
        if not hasattr(self, "_temp_auth_server"):
            self._temp_auth_server = TempAuthServer(__name__)

        return self._temp_auth_server
