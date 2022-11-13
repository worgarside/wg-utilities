"""Generic Google Client - having one client for all APIs is way too big."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime
from json import dumps, loads
from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, Union
from webbrowser import open as open_browser

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from mypy_extensions import DefaultNamedArg
from requests import Response

from wg_utilities.clients.oauth_client import OAuthClient, OAuthCredentialsInfo

if TYPE_CHECKING:  # pragma: no cover
    from wg_utilities.clients.google_calendar import _GoogleCalendarEntityInfo
    from wg_utilities.clients.google_drive import _DirectoryItemInfo
    from wg_utilities.clients.google_fit import _GoogleFitDataPointInfo
    from wg_utilities.clients.google_photos import _AlbumInfo, _MediaItemInfo

    _GoogleEntityInfo = TypeVar(
        "_GoogleEntityInfo",
        bound=Union[
            _GoogleCalendarEntityInfo,
            _GoogleFitDataPointInfo,
            _DirectoryItemInfo,
            _AlbumInfo,
            _MediaItemInfo,
        ],
    )


class GoogleCredentialsInfo(OAuthCredentialsInfo):
    """Typed dict for Google credentials."""

    expiry_epoch: float
    id_token: str | None
    scopes: list[str]
    token: str
    token_uri: str


class GoogleClient(OAuthClient):
    """Custom client for interacting with the Google APIs."""

    DEFAULT_PARAMS: dict[str, object] = {
        "pageSize": "50",
    }

    def __init__(
        self,
        project: str,
        *,
        base_url: str,
        redirect_uri: str = "http://0.0.0.0:5001/get_auth_code",
        access_token_expiry_threshold: int = 300,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
        logger: Logger | None = None,
        scopes: list[str] | None = None,
        client_id_json_path: Path | None = None,
    ):
        """Initialise the client."""
        super().__init__(
            base_url=base_url,
            access_token_endpoint="https://accounts.google.com/o/oauth2/token",
            redirect_uri=redirect_uri,
            access_token_expiry_threshold=access_token_expiry_threshold,
            log_requests=log_requests,
            creds_cache_path=creds_cache_path,
            logger=logger,
        )

        self.project = project
        self.scopes = scopes or []
        self.client_id_json_path = client_id_json_path

        self._credentials: GoogleCredentialsInfo
        self._session: AuthorizedSession

        if self.client_id_json_path:
            self._client_id = loads(self.client_id_json_path.read_text())["web"][
                "client_id"
            ]

    def list_items(
        self,
        method: Callable[
            [str, DefaultNamedArg(dict[str, object] | None, "params")], Response
        ],
        url: str,
        list_key: str,
        *,
        params: Mapping[str, object] | None = None,
    ) -> list[_GoogleEntityInfo]:
        """Generic method for listing items on Google's API(s).

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

        res: Response = method(url, params=params)

        res.raise_for_status()

        item_list: list[_GoogleEntityInfo] = res.json().get(list_key, [])

        next_token: str | None
        while next_token := res.json().get("nextPageToken"):
            # noinspection PyArgumentList
            params = {**params, "pageToken": next_token}
            res = method(
                url,
                params=params,
            )
            res.raise_for_status()

            item_list.extend(res.json().get(list_key, []))
            self.logger.debug("Found %i items so far", len(item_list))

        return item_list

    def get_items(
        self,
        url: str,
        list_key: str = "items",
        *,
        params: Mapping[str, str | int | float | bool] | None = None,
    ) -> list[_GoogleEntityInfo]:
        """Wrapper method for getting a list of items.

        See Also:
            self._list_items: main worker method for this functionality
        """

        return self.list_items(
            self.session.get, url, list_key, params=params  # type: ignore[arg-type]
        )

    @property
    def access_token_expiry_time(self) -> datetime:
        """Get the time at which the current access token will expire.

        Returns:
            datetime: the time at which the current access token will expire
        """

        return self.credentials.expiry  # type: ignore[no-any-return]

    @property
    def access_token_has_expired(self) -> bool:
        """Decodes the JWT access token and evaluates the expiry time.

        Returns:
            bool: has the access token expired?
        """

        return bool(self.credentials.expired)

    @property
    def client_id(self) -> str:
        """Client ID for the Google API.

        Returns:
            str: the current client ID
        """

        return str(self.credentials.client_id)

    @property
    def client_secret(self) -> str:
        """Client secret.

        Returns:
            str: the current client secret
        """

        return str(self.credentials.client_secret)

    @property  # type: ignore[override]
    def credentials(self) -> Credentials:
        """Gets creds as necessary (including first time setup) and authenticates them.

        Returns:
            Credentials: authorized credentials for use in creating a session

        Raises:
            EOFError: when no data is successfully returned for the auth code (usually
             when running the script automatically)
            ValueError: same as above, but if the EOFError isn't raised
        """

        if not hasattr(self, "_credentials"):
            self._load_local_credentials()

        if not self._credentials:
            self.logger.info(
                "Performing first time login for project `%s`", self.project
            )

            self.client_id_json_path = self.client_id_json_path or Path(
                input(
                    "Download your Client ID JSON from https://console.cloud."
                    f"google.com/apis/credentials?project={self.project} and paste"
                    " the file path here: "
                )
            )

            flow = Flow.from_client_secrets_file(
                self.client_id_json_path.as_posix(),
                scopes=self.scopes,
                redirect_uri="http://localhost:5001/get_auth_code",
            )

            auth_url, _ = flow.authorization_url(access_type="offline")
            self.logger.debug("Opening %s", auth_url)
            open_browser(auth_url)

            request_args = self.temp_auth_server.wait_for_request(
                "/get_auth_code", kill_on_request=True
            )

            flow.fetch_token(code=request_args.get("code"))

            self.credentials = loads(flow.credentials.to_json())

        credentials: Credentials = Credentials.from_authorized_user_info(
            self._credentials, self.scopes
        )

        return credentials

    @credentials.setter
    def credentials(self, value: GoogleCredentialsInfo) -> None:
        """Setter for credentials.

        Args:
            value (dict): the new values to use for the creds for this project
        """
        self._set_credentials(value)

    @property
    def refresh_token(self) -> str:
        """Refresh token for the current project.

        Returns:
            str: the current refresh token
        """
        return str(self.credentials.refresh_token)

    @property
    def session(self) -> AuthorizedSession:
        """Uses the Credentials object to sign in to an authorized Google API session.

        Returns:
            AuthorizedSession: an active, authorized Google API session
        """
        if not (hasattr(self, "_session") and self._session):
            self._session = AuthorizedSession(self.credentials)

        return self._session
