"""Generic Google Client - having one client for all APIs is way too big."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from json import dumps
from logging import DEBUG, getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Generic, Literal, TypedDict, TypeVar

from wg_utilities.clients.oauth_client import OAuthClient, OAuthCredentials
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


if TYPE_CHECKING:
    from wg_utilities.clients.google_calendar import GoogleCalendarEntityJson


class GoogleCredentialsInfo(OAuthCredentials):
    """Typed dict for Google credentials."""

    id_token: str | None
    scopes: list[str]
    token: str
    token_uri: str


GetJsonResponseGoogleClient = TypeVar("GetJsonResponseGoogleClient")


class PaginatedResponse(TypedDict):
    """Typing info for a paginated response."""

    accessRole: str
    defaultReminders: list[dict[str, object]]
    etag: str
    items: list[GoogleCalendarEntityJson]
    kind: Literal["calendar#events"]
    nextPageToken: str
    summary: str
    timeZone: str
    updated: str


class GoogleClient(
    Generic[GetJsonResponseGoogleClient], OAuthClient[GetJsonResponseGoogleClient]
):
    """Custom client for interacting with the Google APIs."""

    ACCESS_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    AUTH_LINK_BASE = "https://accounts.google.com/o/oauth2/v2/auth"

    DEFAULT_PARAMS: dict[str, object] = {
        "pageSize": "50",
    }

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        base_url: str,
        redirect_uri: str = "http://localhost:5001/get_auth_code",
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
        scopes: list[str] | None = None,
    ):
        """Initialise the client."""
        super().__init__(
            base_url=base_url,
            access_token_endpoint=self.ACCESS_TOKEN_ENDPOINT,
            auth_link_base=self.AUTH_LINK_BASE,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            log_requests=log_requests,
            creds_cache_path=creds_cache_path,
            scopes=scopes,
        )

    def _list_items(
        self,
        url: str,
        list_key: str,  # pylint: disable=unused-argument
        *,
        params: Mapping[str, object] | None = None,
    ) -> list[GetJsonResponseGoogleClient]:
        """Generic method for listing items on Google's API(s).

        Args:
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
        LOGGER.info(
            "Listing all items at endpoint `%s` with params %s", url, dumps(params)
        )

        res: PaginatedResponse = self.get_json_response(
            url, params=params
        )  # type: ignore[assignment]
        # reveal_type(res)

        item_list: list[GetJsonResponseGoogleClient] = res[
            "items"
        ]  # type: ignore[assignment]

        next_token: str | None
        while next_token := res.get("nextPageToken"):
            params = {**params, "pageToken": next_token}
            res = self.get_json_response(  # type: ignore[assignment]
                url,
                params=params,
            )

            item_list.extend(res["items"])  # type: ignore[arg-type]
            LOGGER.debug("Found %i items so far", len(item_list))

        return item_list

    def get_items(
        self,
        url: str,
        list_key: str = "items",
        *,
        params: Mapping[str, str | int | float | bool] | None = None,
    ) -> list[GetJsonResponseGoogleClient]:
        """Wrapper method for getting a list of items.

        See Also:
            self._list_items: main worker method for this functionality
        """

        return self._list_items(url, list_key, params=params)
