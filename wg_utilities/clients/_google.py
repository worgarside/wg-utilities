"""Generic Google Client - having one client for all APIs is way too big"""
from __future__ import annotations

from copy import deepcopy
from json import dump, dumps, load
from logging import DEBUG, Logger, getLogger
from os import remove
from time import time
from typing import Any, Literal, Mapping, TypedDict, TypeVar
from webbrowser import open as open_browser

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from jwt import DecodeError, decode
from requests import Response, post
from typing_extensions import Protocol

from wg_utilities.clients._generic import TempAuthServer
from wg_utilities.functions import force_mkdir, user_data_dir


class _GoogleEntityInfo(TypedDict):
    pass


_GoogleEntityInfoTypeVar = TypeVar("_GoogleEntityInfoTypeVar", bound=_GoogleEntityInfo)


class _GoogleCredentialsInfo(TypedDict):
    access_token: str
    client_id: str
    client_secret: str
    expires_in: int
    id_token: str | None
    refresh_token: str
    scope: str
    scopes: list[str]
    token: str
    token_type: Literal["Bearer"]
    token_uri: str


class _SessionMethodCallable(Protocol):
    def __call__(self, url: str, params: dict[str, Any] | None = None) -> Response:
        ...


class GoogleClient:
    """Custom client for interacting with the Google APIs

    Args:
        project (str): the name of the project which this client is being used for
        scopes (list): a list of scopes the client can be given
        client_id_json_path (str): the path to the `client_id.json` file downloaded
         from Google's API Console
        creds_cache_path (str): file path for where to cache credentials
        access_token_expiry_threshold (int): the threshold for when the access token is
         considered expired
        logger (RootLogger): a logger to use throughout the client functions
    """

    DEFAULT_PARAMS = {
        "pageSize": "50",
    }

    def __init__(
        self,
        project: str,
        scopes: list[str] | None = None,
        client_id_json_path: str | None = None,
        creds_cache_path: str | None = None,
        access_token_expiry_threshold: int = 60,
        logger: Logger | None = None,
    ):
        self.project = project
        self.scopes = scopes or []
        self.client_id_json_path = client_id_json_path
        self.creds_cache_path = creds_cache_path or user_data_dir(
            file_name="google_api_creds.json"
        )
        self.access_token_expiry_threshold = access_token_expiry_threshold

        if logger:
            self.logger = logger
        else:
            self.logger = getLogger(__name__)
            self.logger.setLevel(DEBUG)

        if not scopes:
            self.logger.warning(
                "No scopes set for Google client. Functionality will be limited."
            )

        self._all_credentials_json: dict[str, _GoogleCredentialsInfo] = {}
        self._session = None

        self.temp_auth_server: TempAuthServer | None = None

    def _list_items(
        self,
        method: _SessionMethodCallable,
        url: str,
        list_key: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> list[_GoogleEntityInfoTypeVar]:
        """Generic method for listing items on Google's API(s)

        Args:
            method (Callable): the Google client session method to use
            url (str): the API endpoint to send a request to
            list_key (str): the key to use in extracting the data from the response
            params (dict): any extra params to be passed in the request

        Returns:
            list: a list of dicts, each representing an item from the API
        """
        params = (
            {**self.DEFAULT_PARAMS, **params}
            if params
            else deepcopy(self.DEFAULT_PARAMS)
        )
        self.logger.info(
            "Listing all items at endpoint `%s` with params %s", url, dumps(params)
        )

        res = method(url, params=params)

        res.raise_for_status()

        item_list: list[_GoogleEntityInfoTypeVar] = res.json().get(list_key, [])

        while next_token := res.json().get("nextPageToken"):
            # noinspection PyArgumentList
            res = method(
                url,
                params={**params, "pageToken": next_token},
            )
            res.raise_for_status()
            item_list.extend(res.json().get(list_key, []))
            self.logger.debug("Found %i items so far", len(item_list))

        return item_list

    def delete_creds_file(self) -> None:
        """Delete the local creds file"""
        try:
            remove(self.creds_cache_path)
        except FileNotFoundError:
            pass

    def get_items(
        self,
        url: str,
        list_key: str = "items",
        *,
        params: Mapping[str, str | int | float | bool] | None = None,
    ) -> list[_GoogleEntityInfoTypeVar]:
        """Wrapper method for getting a list of items

        See Also:
            self._list_items: main worker method for this functionality
        """

        return self._list_items(self.session.get, url, list_key, params=params)

    def refresh_access_token(self) -> None:
        """Uses the cached refresh token to submit a request to TL's API for a new
        access token"""

        self.logger.info("Refreshing access token")

        res = post(
            "https://accounts.google.com/o/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
            },
        )

        res.raise_for_status()

        # Maintain any existing credential values in the dictionary whilst updating
        # new ones
        self.credentials = {
            **self._all_credentials_json[self.project],
            **res.json(),
        }

    @property
    def access_token_has_expired(self) -> bool:
        """Decodes the JWT access token and evaluates the expiry time

        Returns:
            bool: has the access token expired?
        """

        if self.project not in self._all_credentials_json:
            return True

        try:
            expiry_epoch = decode(
                # can't use self.access_token here, as that uses self.credentials,
                # which in turn (recursively) checks if the access token has expired
                self._all_credentials_json[self.project]["access_token"],
                options={"verify_signature": False},
            ).get("exp", 0)

            return bool(
                (expiry_epoch - self.access_token_expiry_threshold) < int(time())
            )
        except (DecodeError, KeyError):
            # treat invalid/missing token as expired, so we get a new one
            return True

    @property
    def client_id(self) -> str:
        """
        Returns:
            str: the current client ID
        """
        return self._all_credentials_json[self.project]["client_id"]

    @property
    def client_secret(self) -> str:
        """
        Returns:
            str: the current client secret
        """
        return self._all_credentials_json[self.project]["client_secret"]

    @property
    def credentials(self) -> Credentials:
        """Gets creds as necessary (including first time setup) and authenticates them

        Returns:
            Credentials: authorized credentials for use in creating a session

        Raises:
            EOFError: when no data is successfully returned for the auth code (usually
             when running the script automatically)
            ValueError: same as above, but if the EOFError isn't raised
        """

        try:
            with open(
                force_mkdir(self.creds_cache_path, path_is_file=True), encoding="UTF-8"
            ) as fin:
                self._all_credentials_json = load(fin)
        except FileNotFoundError:
            self.logger.info("Unable to find local creds file")
            self._all_credentials_json = {}

        if self.project not in self._all_credentials_json:
            self.logger.info(
                "Performing first time login for project `%s`", self.project
            )

            self.client_id_json_path = self.client_id_json_path or input(
                "Download your Client ID JSON from https://console.cloud.google.com/"
                f"apis/credentials?project={self.project} and paste the file path"
                " here: "
            )

            flow = Flow.from_client_secrets_file(
                self.client_id_json_path,
                scopes=self.scopes,
                redirect_uri="http://localhost:5001/get_auth_code",
            )

            auth_url, _ = flow.authorization_url(access_type="offline")
            self.logger.debug("Opening %s", auth_url)
            open_browser(auth_url)

            self.temp_auth_server = TempAuthServer(__name__)

            request_args = self.temp_auth_server.wait_for_request(
                "/get_auth_code", kill_on_request=True
            )

            flow.fetch_token(code=request_args.get("code"))

            self.credentials = {
                "token": flow.credentials.token,
                "refresh_token": flow.credentials.refresh_token,
                "id_token": flow.credentials.id_token,
                "scopes": flow.credentials.scopes,
                "token_uri": flow.credentials.token_uri,
                "client_id": flow.credentials.client_id,
                "client_secret": flow.credentials.client_secret,
            }

        if self.access_token_has_expired:
            self.refresh_access_token()

        return Credentials.from_authorized_user_info(
            self._all_credentials_json[self.project], self.scopes
        )

    @credentials.setter
    def credentials(self, value: _GoogleCredentialsInfo) -> None:
        """
        Args:
            value (dict): the new values to use for the creds for this project
        """
        self._all_credentials_json[self.project] = value

        with open(
            force_mkdir(self.creds_cache_path, path_is_file=True), "w", encoding="UTF-8"
        ) as fout:
            dump(self._all_credentials_json, fout)

    @property
    def refresh_token(self) -> str:
        """
        Returns:
            str: the current refresh token
        """
        return self._all_credentials_json[self.project]["refresh_token"]

    @property
    def session(self) -> AuthorizedSession:
        """Uses the Credentials object to sign in to an authorized Google API session

        Returns:
            AuthorizedSession: an active, authorized Google API session
        """
        if not self._session:
            self._session = AuthorizedSession(self.credentials)

        return self._session
