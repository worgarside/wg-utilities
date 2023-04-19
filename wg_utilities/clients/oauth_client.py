# pylint: disable=too-few-public-methods
"""Generic OAuth client to allow for reusable authentication flows/checks etc."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from datetime import datetime
from http import HTTPStatus
from json import JSONDecodeError, dumps
from logging import DEBUG, getLogger
from os import getenv
from pathlib import Path
from random import choice
from string import ascii_letters
from time import time
from typing import Any, Generic, Literal, TypeAlias, TypeVar
from urllib.parse import urlencode
from webbrowser import open as open_browser

from jwt import DecodeError, decode
from pydantic import BaseModel, Extra, validate_model
from pydantic.generics import GenericModel
from requests import Response, get, post

from wg_utilities.api import TempAuthServer
from wg_utilities.functions import user_data_dir
from wg_utilities.functions.file_management import force_mkdir
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


class _ModelBase:
    """Base class for `BaseModelWithConfig` and `GenericModelWithConfig`.

    This is just to prevent duplicating the methods in both classes.
    """

    __fields__: dict[str, Any]

    def _set_private_attr(self, attr_name: str, attr_value: Any) -> None:
        """Set private attribute on the instance.

        Args:
            attr_name (str): the name of the attribute to set
            attr_value (Any): the value to set the attribute to

        Raises:
            ValueError: if the attribute isn't private (i.e. the name doesn't start
                with an underscore)
        """
        if not attr_name.startswith("_"):
            raise ValueError("Only private attributes can be set via this method.")

        object.__setattr__(self, attr_name, attr_value)

    def _validate(self) -> None:
        """Validate the model.

        Any fields which have been renamed via `alias` will be renamed in the
        validation dict before being passed to `validate_model`. Private attributes,
        functions, and excluded fields are also ignored.

        Raises:
            ValidationError: if the model is invalid
        """

        model_dict = {
            self.__fields__[k].alias if k in self.__fields__ else k: v
            for k, v in self.__dict__.items()
            if not k.startswith("_") and not callable(v)
        }

        *_, validation_error = validate_model(
            self.__class__, model_dict, self.__class__  # type: ignore[arg-type]
        )

        if validation_error:  # pragma: no cover
            LOGGER.error(repr(validation_error))
            raise validation_error


class BaseModelWithConfig(_ModelBase, BaseModel):
    """Reusable `BaseModel` with Config to apply to all subclasses."""

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
        extra = Extra.forbid
        validate_assignment = True


class GenericModelWithConfig(_ModelBase, GenericModel):
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
    client_secret: str

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
            value: the response from the API

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
                    raise ValueError(
                        "`expiry` and `expires_in` are not consistent with each other:"
                        f" expiry: {expiry_time_str}, expires_in: {expiry_epoch}"
                    ) from None

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


GetJsonResponse = TypeVar("GetJsonResponse", bound=Mapping[Any, Any])

StrBytIntFlt: TypeAlias = str | bytes | int | float


class OAuthClient(Generic[GetJsonResponse]):
    """Custom client for interacting with OAuth APIs.

    Includes all necessary/basic authentication functionality
    """

    ACCESS_TOKEN_ENDPOINT: str
    AUTH_LINK_BASE: str
    BASE_URL: str

    ACCESS_TOKEN_EXPIRY_THRESHOLD = 150

    # Second env var added for compatibility
    DEFAULT_CACHE_DIR = getenv(
        "WG_UTILITIES_CACHE_DIR", getenv("WG_UTILITIES_CREDS_CACHE_DIR")
    )
    DEFAULT_PARAMS: dict[
        StrBytIntFlt, StrBytIntFlt | Iterable[StrBytIntFlt] | None
    ] = {}
    DEFAULT_SCOPES: list[str] = []

    HEADLESS_MODE = getenv("WG_UTILITIES_HEADLESS_MODE", "0") == "1"

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
        scopes: list[str] | None = None,
        oauth_login_redirect_host: str = "localhost",
        oauth_redirect_uri_override: str | None = None,
        headless_auth_link_callback: Callable[[str], None] | None = None,
        use_existing_credentials_only: bool = False,
        access_token_endpoint: str | None = None,
        auth_link_base: str | None = None,
        base_url: str | None = None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self.base_url = base_url or self.BASE_URL
        self.access_token_endpoint = access_token_endpoint or self.ACCESS_TOKEN_ENDPOINT
        self.auth_link_base = auth_link_base or self.AUTH_LINK_BASE
        self.log_requests = log_requests
        self._creds_cache_path = creds_cache_path
        self.oauth_login_redirect_host = oauth_login_redirect_host
        self.oauth_redirect_uri_override = oauth_redirect_uri_override
        self.headless_auth_link_callback = headless_auth_link_callback
        self.use_existing_credentials_only = use_existing_credentials_only

        self.scopes = scopes or self.DEFAULT_SCOPES

        self._credentials: OAuthCredentials
        self._temp_auth_server: TempAuthServer

        if self._creds_cache_path:
            self._load_local_credentials()

    def _get(
        self,
        url: str,
        *,
        params: dict[
            StrBytIntFlt,
            StrBytIntFlt | Iterable[StrBytIntFlt] | None,
        ]
        | None = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: (float | tuple[float, float] | tuple[float, None] | None) = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> Response:
        """Wrap all GET requests to cover authentication, URL parsing, etc. etc.

        Args:
            url (str): the URL path to the endpoint (not necessarily including the
                base URL)
            params (dict): the parameters to be passed in the HTTP request
            header_overrides (dict): any headers to override the default headers
            timeout (float | tuple[float, float] | tuple[float, None] | None): the
                timeout for the request
            json (Any): the JSON to be passed in the HTTP request
            data (Any): the data to be passed in the HTTP request

        Returns:
            Response: the response from the HTTP request
        """
        return self._request(
            method=get,
            url=url,
            params=params,
            header_overrides=header_overrides,
            timeout=timeout,
            json=json,
            data=data,
        )

    def _load_local_credentials(self) -> bool:
        """Load credentials from the local cache.

        Returns:
            bool: True if the credentials were loaded successfully, False otherwise
        """
        try:
            self._credentials = OAuthCredentials.parse_file(self.creds_cache_path)
        except FileNotFoundError:
            return False

        return True

    def _post(
        self,
        url: str,
        *,
        params: dict[
            StrBytIntFlt,
            StrBytIntFlt | Iterable[StrBytIntFlt] | None,
        ]
        | None = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: (float | tuple[float, float] | tuple[float, None] | None) = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> Response:
        """Wrap all POST requests to cover authentication, URL parsing, etc. etc.

        Args:
            url (str): the URL path to the endpoint (not necessarily including the
                base URL)
            json (dict): the data to be passed in the HTTP request
            params (dict): the parameters to be passed in the HTTP request
            header_overrides (dict): any headers to override the default headers
            timeout (float | tuple[float, float] | tuple[float, None] | None): the
                timeout for the request
            json (Any): the JSON to be passed in the HTTP request
            data (Any): the data to be passed in the HTTP request

        Returns:
            Response: the response from the HTTP request
        """
        return self._request(
            method=post,
            url=url,
            params=params,
            header_overrides=header_overrides,
            timeout=timeout,
            json=json,
            data=data,
        )

    def _request(
        self,
        *,
        method: Callable[..., Response],
        url: str,
        params: dict[
            StrBytIntFlt,
            StrBytIntFlt | Iterable[StrBytIntFlt] | None,
        ]
        | None = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: (float | tuple[float, float] | tuple[float, None] | None) = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> Response:
        """Make a HTTP request.

        Args:
            method (Callable): the HTTP method to use
            url (str): the URL path to the endpoint (not necessarily including the
                base URL)
            params (dict): the parameters to be passed in the HTTP request
            header_overrides (dict): any headers to override the default headers
            timeout (float | tuple[float, float] | tuple[float, None] | None): the
                timeout for the request
            json (dict): the data to be passed in the HTTP request
            data (dict): the data to be passed in the HTTP request
        """
        if params is not None:
            params.update(
                {k: v for k, v in self.DEFAULT_PARAMS.items() if k not in params}
            )
        else:
            params = deepcopy(self.DEFAULT_PARAMS)

        params = {k: v for k, v in params.items() if v is not None}

        if url.startswith("/"):
            url = f"{self.base_url}{url}"

        if self.log_requests:
            LOGGER.debug(
                "%s %s: %s", method.__name__.upper(), url, dumps(params, default=str)
            )

        res = method(
            url,
            headers=header_overrides
            if header_overrides is not None
            else self.request_headers,
            params=params,
            timeout=timeout,
            json=json,
            data=data,
        )

        res.raise_for_status()

        return res

    def _request_json_response(
        self,
        *,
        method: Callable[..., Response],
        url: str,
        params: dict[
            StrBytIntFlt,
            StrBytIntFlt | Iterable[StrBytIntFlt] | None,
        ]
        | None = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: (float | tuple[float, float] | tuple[float, None] | None) = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> GetJsonResponse:
        res = self._request(
            method=method,
            url=url,
            params=params,
            header_overrides=header_overrides,
            timeout=timeout,
            json=json,
            data=data,
        )
        if res.status_code == HTTPStatus.NO_CONTENT:
            return {}  # type: ignore[return-value]

        try:
            return res.json()  # type: ignore[no-any-return]
        except JSONDecodeError as exc:
            if not res.content:
                return {}  # type: ignore[return-value]

            raise ValueError(res.text) from exc

    def delete_creds_file(self) -> None:
        """Delete the local creds file."""
        self.creds_cache_path.unlink(missing_ok=True)

    def get_json_response(
        self,
        url: str,
        params: dict[
            StrBytIntFlt,
            StrBytIntFlt | Iterable[StrBytIntFlt] | None,
        ]
        | None = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: float | None = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> GetJsonResponse:
        """Get a simple JSON object from a URL.

        Args:
            url (str): the API endpoint to GET
            params (dict): the parameters to be passed in the HTTP request
            header_overrides (dict): headers to add to/overwrite the headers in
                `self.request_headers`. Setting this to an empty dict will erase all
                headers; `None` will use `self.request_headers`.
            timeout (float): How many seconds to wait for the server to send data
                before giving up
            json (dict): a JSON payload to pass in the request
            data (dict): a data payload to pass in the request

        Returns:
            dict: the JSON from the response
        """

        return self._request_json_response(
            method=get,
            url=url,
            params=params,
            header_overrides=header_overrides,
            timeout=timeout,
            json=json,
            data=data,
        )

    def post_json_response(
        self,
        url: str,
        params: dict[
            StrBytIntFlt,
            StrBytIntFlt | Iterable[StrBytIntFlt] | None,
        ]
        | None = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: (float | tuple[float, float] | tuple[float, None] | None) = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> GetJsonResponse:
        """Get a simple JSON object from a URL from a POST request.

        Args:
            url (str): the API endpoint to GET
            params (dict): the parameters to be passed in the HTTP request
            header_overrides (dict): headers to add to/overwrite the headers in
                `self.request_headers`. Setting this to an empty dict will erase all
                headers; `None` will use `self.request_headers`.
            timeout (float): How many seconds to wait for the server to send data
                before giving up
            json (dict): a JSON payload to pass in the request
            data (dict): a data payload to pass in the request

        Returns:
            dict: the JSON from the response
        """

        return self._request_json_response(
            method=post,
            url=url,
            params=params,
            header_overrides=header_overrides,
            timeout=timeout,
            json=json,
            data=data,
        )

    def refresh_access_token(self) -> None:
        """Refresh access token."""

        if not hasattr(self, "_credentials") and not self._load_local_credentials():
            # If we don't have any credentials, we can't refresh the access token -
            # perform first time login and leave it at that
            self.run_first_time_login()
            return

        LOGGER.info("Refreshing access token")

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.credentials.refresh_token,
        }

        new_creds = self.post_json_response(
            self.access_token_endpoint,
            data=payload,
            header_overrides={},
        )

        self.credentials.update_access_token(
            new_token=new_creds["access_token"],
            expires_in=new_creds["expires_in"],
            # Monzo
            refresh_token=new_creds.get("refresh_token"),
        )

        self.creds_cache_path.write_text(self.credentials.json(exclude_none=True))

    def run_first_time_login(self) -> None:
        """Run the first time login process.

        This is a blocking call which will not return until the user has
        authenticated with the OAuth provider.

        Raises:
            RuntimeError: if `use_existing_credentials_only` is set to True
            ValueError: if the state token returned by the OAuth provider does not
                match
        """

        if self.use_existing_credentials_only:
            raise RuntimeError(
                "No existing credentials found, and `use_existing_credentials_only` "
                "is set to True"
            )

        LOGGER.info("Performing first time login")

        state_token = "".join(choice(ascii_letters) for _ in range(32))

        self.temp_auth_server.start_server()

        if self.oauth_redirect_uri_override:
            redirect_uri = self.oauth_redirect_uri_override
        else:
            # pylint: disable=line-too-long
            redirect_uri = f"http://{self.oauth_login_redirect_host}:{self.temp_auth_server.port}/get_auth_code"

        auth_link_params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state_token,
            "access_type": "offline",
            "prompt": "consent",
        }

        if self.scopes:
            auth_link_params["scope"] = " ".join(self.scopes)

        auth_link = self.auth_link_base + "?" + urlencode(auth_link_params)

        if self.HEADLESS_MODE:
            if self.headless_auth_link_callback is None:
                LOGGER.warning(
                    "Headless mode is enabled, but no headless auth link callback "
                    "has been set. The auth link will not be opened."
                )
                LOGGER.debug("Auth link: %s", auth_link)
            else:
                LOGGER.info("Sending auth link to callback")
                self.headless_auth_link_callback(auth_link)
        else:
            open_browser(auth_link)

        request_args = self.temp_auth_server.wait_for_request(
            "/get_auth_code", kill_on_request=True
        )

        if state_token != request_args.get("state"):
            raise ValueError(
                "State token received in request doesn't match expected value: "
                f"`{request_args.get('state')}` != `{state_token}`"
            )

        payload_key = (
            "data"
            if self.__class__.__name__ in ("MonzoClient", "SpotifyClient")
            else "json"
        )

        res = self._post(
            self.access_token_endpoint,
            **{  # type: ignore[arg-type]
                payload_key: {
                    "code": request_args["code"],
                    "grant_type": "authorization_code",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": redirect_uri,
                }
            },
            # Stops recursive call to `self.request_headers`
            header_overrides={"Content-Type": "application/x-www-form-urlencoded"}
            if self.__class__.__name__ in ("MonzoClient", "SpotifyClient")
            else {},
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
        """Decode the JWT access token and evaluates the expiry time.

        Returns:
            bool: has the access token expired?
        """
        if not hasattr(self, "_credentials"):
            if not self._load_local_credentials():
                return True

        return (
            self.credentials.expiry_epoch
            < int(time()) + self.ACCESS_TOKEN_EXPIRY_THRESHOLD
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
        """Get creds as necessary (including first time setup) and authenticates them.

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
        """Set the client's credentials, and write to the local cache file."""

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

        file_path = f"{type(self).__name__}/{self.client_id}.json"

        return force_mkdir(
            Path(self.DEFAULT_CACHE_DIR) / file_path
            if self.DEFAULT_CACHE_DIR
            else user_data_dir() / "oauth_credentials" / file_path,
            path_is_file=True,
        )

    @property
    def request_headers(self) -> dict[str, str]:
        """Header to be used in requests to the API.

        Returns:
            dict: auth headers for HTTP requests
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    @property
    def refresh_token(self) -> str:
        """Refresh token.

        Returns:
            str: the API refresh token
        """
        return self.credentials.refresh_token

    @property
    def temp_auth_server(self) -> TempAuthServer:
        """Create a temporary HTTP server for the auth flow.

        Returns:
            TempAuthServer: the temporary server
        """
        if not hasattr(self, "_temp_auth_server"):
            self._temp_auth_server = TempAuthServer(__name__, auto_run=False)

        return self._temp_auth_server
