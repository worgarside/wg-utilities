"""Generic Oauth client to allow for reusable authentication flows/checks etc."""
from __future__ import annotations

from json import dump, dumps, load
from logging import DEBUG, Logger, getLogger
from pathlib import Path
from random import choice
from string import ascii_letters
from time import time
from typing import Any, TypedDict
from webbrowser import open as open_browser

from jwt import DecodeError, decode
from requests import Response, get, post

from wg_utilities.api import TempAuthServer
from wg_utilities.functions import force_mkdir, user_data_dir


class _OauthCredentialsInfo(TypedDict):
    access_token: str
    client_id: str
    expires_in: int
    refresh_token: str
    scope: str
    token_type: str
    user_id: str


class OauthClient:
    """Custom client for interacting with Oauth APIs.

    Includes all necessary/basic authentication functionality
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        base_url: str,
        access_token_endpoint: str,
        redirect_uri: str = "http://0.0.0.0:5001/get_auth_code",
        access_token_expiry_threshold: int = 60,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
        logger: Logger | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.access_token_endpoint = access_token_endpoint
        self.redirect_uri = redirect_uri
        self.access_token_expiry_threshold = access_token_expiry_threshold
        self.log_requests = log_requests
        self.creds_cache_path = creds_cache_path or user_data_dir(
            file_name=f"{client_id}.json"
        )

        if logger:
            self.logger = logger
        else:
            self.logger = getLogger(__name__)
            self.logger.setLevel(DEBUG)

        self._credentials: _OauthCredentialsInfo

        self.temp_auth_server: TempAuthServer | None = None

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Response:
        """Wrapper for GET requests which covers authentication, URL parsing, etc. etc.

        Args:
            url (str): the URL path to the endpoint (not necessarily including the
             base URL)
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            Response: the response from the HTTP request
        """

        if url.startswith("/"):
            url = f"{self.base_url}{url}"

        if self.log_requests:
            self.logger.debug(
                "GET %s with params %s", url, dumps(params or {}, default=str)
            )

        res = get(
            url,
            headers=self.request_headers,
            params=params or {},
        )

        res.raise_for_status()

        return res

    def _load_local_credentials(self) -> None:
        with open(self.creds_cache_path, encoding="UTF-8") as fin:
            self._credentials = load(fin).get(self.client_id, {})

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

        self.credentials = res.json()

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
        return self._get(url, params=params).json()  # type: ignore[no-any-return]

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
            # treat invalid token as expired, so we get a new one
            return True

    @property
    def credentials(self) -> _OauthCredentialsInfo:
        """Gets creds as necessary (including first time setup) and authenticates them.

        Returns:
            dict: the credentials for the chosen bank

        Raises:
            ValueError: if the state token returned from the request doesn't match the
             expected value
        """
        self._load_local_credentials()

        if not self._credentials:
            self.logger.info("Performing first time login")
            state_token = "".join(choice(ascii_letters) for _ in range(32))
            # pylint: disable=line-too-long
            auth_link = f"https://auth.monzo.com/?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&state={state_token}"  # noqa: E501
            self.logger.debug("Opening %s", auth_link)
            open_browser(auth_link)

            self.temp_auth_server = TempAuthServer(__name__)

            request_args = self.temp_auth_server.wait_for_request(
                "/get_auth_code", kill_on_request=True
            )

            if state_token != request_args.get("state"):
                raise ValueError(
                    "State token received in request doesn't match expected value"
                )

            self.exchange_auth_code(request_args["code"])

        if self.access_token_has_expired:
            self.refresh_access_token()

        return self._credentials

    @credentials.setter
    def credentials(self, value: _OauthCredentialsInfo) -> None:
        """Setter for credentials.

        Args:
            value (dict): the new values to use for the creds for this project
        """
        self._credentials = value

        try:
            with open(
                force_mkdir(self.creds_cache_path, path_is_file=True), encoding="UTF-8"
            ) as fin:
                all_credentials = load(fin)
        except FileNotFoundError:
            all_credentials = {}

        all_credentials[self.client_id] = self._credentials

        with open(self.creds_cache_path, "w", encoding="UTF-8") as fout:
            dump(all_credentials, fout)

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
