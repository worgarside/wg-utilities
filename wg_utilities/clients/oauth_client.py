"""Generic OAuth client to allow for reusable authentication flows/checks etc."""

from __future__ import annotations

from datetime import datetime
from json import dumps
from logging import DEBUG, getLogger
from os import getenv
from pathlib import Path
from random import choice
from string import ascii_letters
from time import time
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from urllib.parse import urlencode
from webbrowser import open as open_browser

from jwt import DecodeError, decode
from pydantic import BaseModel, ConfigDict

from wg_utilities.api import TempAuthServer
from wg_utilities.clients.json_api_client import GetJsonResponse, JsonApiClient
from wg_utilities.functions import user_data_dir
from wg_utilities.functions.file_management import force_mkdir

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from pydantic.main import IncEx

else:
    IncEx = set[int] | set[str] | dict[int, Any] | dict[str, Any] | None

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


class BaseModelWithConfig(BaseModel):
    """Reusable `BaseModel` with Config to apply to all subclasses."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        arbitrary_types_allowed=True,
        extra="ignore",
        validate_assignment=True,
    )

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = True,
        exclude_unset: bool = True,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> dict[str, Any]:
        """Create a dictionary representation of the model.

        Overrides the standard `BaseModel.dict` method, so we can always return the
        dict with the same field names it came in with, and exclude any null values
        that have been added when parsing

        Original documentation is here:
          - https://docs.pydantic.dev/latest/usage/serialization/#modelmodel_dump

        Overridden Parameters:
            by_alias: False -> True
            exclude_unset: False -> True
        """

        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
        )

    def model_dump_json(
        self,
        *,
        indent: int | None = None,
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = True,
        exclude_unset: bool = True,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> str:
        """Create a JSON string representation of the model.

        Overrides the standard `BaseModel.json` method, so we can always return the
        dict with the same field names it came in with, and exclude any null values
        that have been added when parsing

        Original documentation is here:
          - https://docs.pydantic.dev/latest/usage/serialization/#modelmodel_dump_json

        Overridden Parameters:
            by_alias: False -> True
            exclude_unset: False -> True
        """

        return super().model_dump_json(
            indent=indent,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
        )


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
    user_id: str | None = None

    # Google
    token: str | None = None
    token_uri: str | None = None
    scopes: list[str] | None = None

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
                if abs(expiry_epoch - expiry_time.timestamp()) > 60:  # noqa: PLR2004
                    raise ValueError(
                        "`expiry` and `expires_in` are not consistent with each other:"
                        f" expiry: {expiry_time_str}, expires_in: {expiry_epoch}",
                    ) from None

        value["expiry_epoch"] = expiry_epoch

        return cls(**value)

    def update_access_token(
        self,
        new_token: str,
        expires_in: int,
        refresh_token: str | None = None,
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


class OAuthClient(JsonApiClient[GetJsonResponse]):
    """Custom client for interacting with OAuth APIs.

    Includes all necessary/basic authentication functionality
    """

    ACCESS_TOKEN_ENDPOINT: str
    AUTH_LINK_BASE: str

    ACCESS_TOKEN_EXPIRY_THRESHOLD = 150

    DEFAULT_CACHE_DIR = getenv("WG_UTILITIES_CREDS_CACHE_DIR")

    DEFAULT_SCOPES: ClassVar[list[str]] = []

    HEADLESS_MODE = getenv("WG_UTILITIES_HEADLESS_MODE", "0") == "1"

    _credentials: OAuthCredentials
    _temp_auth_server: TempAuthServer

    def __init__(  # noqa: PLR0913
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
        creds_cache_dir: Path | None = None,
        scopes: list[str] | None = None,
        oauth_login_redirect_host: str = "localhost",
        oauth_redirect_uri_override: str | None = None,
        headless_auth_link_callback: Callable[[str], None] | None = None,
        use_existing_credentials_only: bool = False,
        access_token_endpoint: str | None = None,
        auth_link_base: str | None = None,
        base_url: str | None = None,
        validate_request_success: bool = True,
    ):
        """Initialise the client.

        Args:
            client_id (str, optional): the client ID for the API. Defaults to None.
            client_secret (str, optional): the client secret for the API. Defaults to
                None.
            log_requests (bool, optional): whether to log requests. Defaults to False.
            creds_cache_path (Path, optional): the path to the credentials cache file.
                Defaults to None. Overrides `creds_cache_dir`.
            creds_cache_dir (Path, optional): the path to the credentials cache directory.
                Overrides environment variable `WG_UTILITIES_CREDS_CACHE_DIR`. Defaults to
                None.
            scopes (list[str], optional): the scopes to request when authenticating.
                Defaults to None.
            oauth_login_redirect_host (str, optional): the host to redirect to after
                authenticating. Defaults to "localhost".
            oauth_redirect_uri_override (str, optional): override the redirect URI
                specified in the OAuth flow. Defaults to None.
            headless_auth_link_callback (Callable[[str], None], optional): callback to
                send the auth link to when running in headless mode. Defaults to None.
            use_existing_credentials_only (bool, optional): whether to only use existing
                credentials, and not attempt to authenticate. Defaults to False.
            access_token_endpoint (str, optional): the endpoint to use to get an access
                token. Defaults to None.
            auth_link_base (str, optional): the base URL to use to generate the auth
                link. Defaults to None.
            base_url (str, optional): the base URL to use for API requests. Defaults to
                None.
            validate_request_success (bool, optional): whether to validate that the
                request was successful. Defaults to True.
        """
        super().__init__(
            log_requests=log_requests,
            base_url=base_url,
            validate_request_success=validate_request_success,
        )

        self._client_id = client_id
        self._client_secret = client_secret
        self.access_token_endpoint = access_token_endpoint or self.ACCESS_TOKEN_ENDPOINT
        self.auth_link_base = auth_link_base or self.AUTH_LINK_BASE
        self.oauth_login_redirect_host = oauth_login_redirect_host
        self.oauth_redirect_uri_override = oauth_redirect_uri_override
        self.headless_auth_link_callback = headless_auth_link_callback
        self.use_existing_credentials_only = use_existing_credentials_only

        if creds_cache_path:
            self._creds_cache_path: Path | None = creds_cache_path
            self._creds_cache_dir: Path | None = None
        elif creds_cache_dir:
            self._creds_cache_path = None
            self._creds_cache_dir = creds_cache_dir
        else:
            self._creds_cache_path = None
            if self.DEFAULT_CACHE_DIR:
                self._creds_cache_dir = Path(self.DEFAULT_CACHE_DIR)
            else:
                self._creds_cache_dir = None

        self.scopes = scopes or self.DEFAULT_SCOPES

        if self._creds_cache_path:
            self._load_local_credentials()

    def _load_local_credentials(self) -> bool:
        """Load credentials from the local cache.

        Returns:
            bool: True if the credentials were loaded successfully, False otherwise
        """
        try:
            self._credentials = OAuthCredentials.model_validate_json(
                self.creds_cache_path.read_text(),
            )
        except FileNotFoundError:
            return False

        return True

    def delete_creds_file(self) -> None:
        """Delete the local creds file."""
        self.creds_cache_path.unlink(missing_ok=True)

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

        self.creds_cache_path.write_text(
            self.credentials.model_dump_json(exclude_none=True),
        )

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
                "is set to True",
            )

        LOGGER.info("Performing first time login")

        state_token = "".join(choice(ascii_letters) for _ in range(32))  # noqa: S311

        self.temp_auth_server.start_server()

        if self.oauth_redirect_uri_override:
            redirect_uri = self.oauth_redirect_uri_override
        else:
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
                    "has been set. The auth link will not be opened.",
                )
                LOGGER.debug("Auth link: %s", auth_link)
            else:
                LOGGER.info("Sending auth link to callback")
                self.headless_auth_link_callback(auth_link)
        else:
            open_browser(auth_link)

        request_args = self.temp_auth_server.wait_for_request(
            "/get_auth_code",
            kill_on_request=True,
        )

        if state_token != request_args.get("state"):
            raise ValueError(
                "State token received in request doesn't match expected value: "
                f"`{request_args.get('state')}` != `{state_token}`",
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
                },
            },
            # Stops recursive call to `self.request_headers`
            header_overrides=(
                {"Content-Type": "application/x-www-form-urlencoded"}
                if self.__class__.__name__ in ("MonzoClient", "SpotifyClient")
                else {}
            ),
        )

        credentials = res.json()

        if self._client_id:
            credentials["client_id"] = self._client_id

        if self._client_secret:
            credentials["client_secret"] = self._client_secret

        self.credentials = OAuthCredentials.parse_first_time_login(credentials)

    @property
    def _creds_rel_file_path(self) -> Path | None:
        """Get the credentials cache filepath relative to the cache directory.

        Overridable in subclasses.
        """

        try:
            client_id = self._client_id or self._credentials.client_id
        except AttributeError:
            return None

        return Path(type(self).__name__, f"{client_id}.json")

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
        if not hasattr(self, "_credentials") and not self._load_local_credentials():
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
            dumps(self._credentials.model_dump(exclude_none=True)),
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

        if not self._creds_rel_file_path:
            raise ValueError(
                "Unable to get client ID to generate path for credentials cache file.",
            )

        return force_mkdir(
            (self._creds_cache_dir or user_data_dir() / "oauth_credentials")
            / self._creds_rel_file_path,
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
