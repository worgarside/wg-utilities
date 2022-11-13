"""Generic OAuth client to allow for reusable authentication flows/checks etc."""
from __future__ import annotations

from copy import deepcopy
from http import HTTPStatus
from json import JSONDecodeError, dump, dumps, loads
from logging import DEBUG, Logger, getLogger
from pathlib import Path
from time import time
from typing import Any, Literal, TypedDict

from jwt import DecodeError, decode
from requests import Response, get, post

from wg_utilities.api import TempAuthServer
from wg_utilities.functions import user_data_dir


class OAuthCredentialsInfo(TypedDict):
    """Typing info for OAuth credentials."""

    access_token: str
    client_id: str
    client_secret: str
    expires_in: int
    refresh_token: str
    scope: str
    token_type: Literal["Bearer"]
    user_id: str


class OAuthClient:
    """Custom client for interacting with OAuth APIs.

    Includes all necessary/basic authentication functionality
    """

    DEFAULT_PARAMS: dict[str, object] = {}

    def __init__(
        self,
        *,
        base_url: str,
        access_token_endpoint: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str = "http://0.0.0.0:5001/get_auth_code",
        access_token_expiry_threshold: int = 60,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
        logger: Logger | None = None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self.base_url = base_url
        self.access_token_endpoint = access_token_endpoint
        self.redirect_uri = redirect_uri
        self.access_token_expiry_threshold = access_token_expiry_threshold
        self.log_requests = log_requests
        self._creds_cache_path = creds_cache_path

        if logger:
            self.logger = logger
        else:
            self.logger = getLogger(__name__)
            self.logger.setLevel(DEBUG)

        self._credentials: OAuthCredentialsInfo

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
            self.logger.debug("GET %s with params %s", url, dumps(params, default=str))

        res = get(
            url,
            headers=self.request_headers,
            params=params,  # type: ignore[arg-type]
        )

        res.raise_for_status()

        return res

    def _load_local_credentials(self) -> None:

        if not (self._creds_cache_path and self._creds_cache_path.exists()):
            self._credentials = {}  # type: ignore[typeddict-item]
            return

        self._credentials = loads(self.creds_cache_path.read_text())

    def _set_credentials(self, value: OAuthCredentialsInfo) -> None:
        """Actual setter for credentials.

        Args:
            value (OAuthCredentialsInfo): the new values to use for the creds for
                this project
        """
        self._credentials = value

        with open(self.creds_cache_path, "w", encoding="UTF-8") as fout:
            dump(self._credentials, fout)

    def delete_creds_file(self) -> None:
        """Delete the local creds file."""
        try:
            self.creds_cache_path.unlink()
        except FileNotFoundError:
            pass

    def exchange_auth_code(self, code: str) -> None:
        """Allows first-time (or repeated) authentication.

        Args:
            code (str): the authorization code returned from the auth flow
        """

        res = post(
            self.access_token_endpoint,
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )

        res.raise_for_status()

        self.credentials = {**self._credentials, **res.json()}  # type: ignore[misc]

    def get_json_response(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
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
                return {}

            return res.json()  # type: ignore[no-any-return]
        except JSONDecodeError:
            return {}

    def refresh_access_token(self) -> None:
        """Refreshes access token.

        Uses the cached refresh token to submit a request to TL's API for a new
        access token
        """

        if not hasattr(self, "_credentials"):
            self._load_local_credentials()

        self.logger.info("Refreshing access token")

        res = post(
            self.access_token_endpoint,
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self._credentials.get("refresh_token"),
            },
        )

        res.raise_for_status()

        # Maintain any existing credential values in the dictionary whilst updating
        # new ones
        self.credentials = {
            **self._credentials,  # type: ignore[misc]
            # TODO is this correct? :/
            **res.json(),
        }

    @property
    def access_token(self) -> str | None:
        """Access token.

        Returns:
            str: the access token for this bank's API
        """
        return self.credentials.get("access_token")

    @property
    def access_token_has_expired(self) -> bool:
        """Decodes the JWT access token and evaluates the expiry time.

        Returns:
            bool: has the access token expired?
        """
        if not hasattr(self, "_credentials"):
            self._load_local_credentials()

        try:
            expiry_epoch = decode(
                # can't use self.access_token here, as that uses self.credentials,
                # which in turn (recursively) checks if the access token has expired
                self._credentials["access_token"],
                options={"verify_signature": False},
            ).get("exp", 0)

            return bool(
                (expiry_epoch - self.access_token_expiry_threshold) < int(time())
            )
        except (DecodeError, KeyError):
            # Treat invalid token as expired, so we get a new one
            return True

    @property
    def client_id(self) -> str:
        """Client ID for the Google API.

        Returns:
            str: the current client ID
        """

        return self._client_id or self.credentials["client_id"]

    @property
    def client_secret(self) -> str:
        """Client secret.

        Returns:
            str: the current client secret
        """

        return self._client_secret or self.credentials["client_secret"]

    @property
    def credentials(self) -> OAuthCredentialsInfo:
        """Gets creds as necessary (including first time setup) and authenticates them.

        Returns:
            dict: the credentials for the chosen bank

        Raises:
            ValueError: if the state token returned from the request doesn't match the
             expected value
        """
        if not hasattr(self, "_credentials"):
            self._load_local_credentials()

        return self._credentials

    @credentials.setter
    def credentials(self, value: OAuthCredentialsInfo) -> None:
        """Setter for credentials.

        Args:
            value (dict): the new values to use for the creds for this project
        """
        self._set_credentials(value)

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
    def refresh_token(self) -> str | None:
        """Refresh token.

        Returns:
            str: the API refresh token
        """
        return self.credentials.get("refresh_token")

    @property
    def temp_auth_server(self) -> TempAuthServer:
        """Creates a temporary HTTP server for the auth flow.

        Returns:
            TempAuthServer: the temporary server
        """
        if not hasattr(self, "_temp_auth_server"):
            self._temp_auth_server = TempAuthServer(__name__)

        return self._temp_auth_server
