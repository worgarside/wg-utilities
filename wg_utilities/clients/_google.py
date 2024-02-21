"""Generic Google Client - having one client for all APIs is way too big."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from json import dumps
from logging import DEBUG, getLogger
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Literal, TypeAlias, TypeVar

from requests import Response, get
from typing_extensions import TypedDict

from wg_utilities.clients.oauth_client import OAuthClient
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


if TYPE_CHECKING:  # pragma: no cover
    from wg_utilities.clients.google_calendar import GoogleCalendarEntityJson
    from wg_utilities.clients.google_photos import GooglePhotosEntityJson
    from wg_utilities.clients.json_api_client import StrBytIntFlt


GetJsonResponseGoogleClient = TypeVar(
    "GetJsonResponseGoogleClient",
    bound=Mapping[Any, Any],
)


class _PaginatedResponseBase(TypedDict):
    """Typing info for a paginated response."""

    accessRole: str
    defaultReminders: list[dict[str, object]]
    etag: str
    kind: Literal["calendar#events"]
    nextPageToken: str
    summary: str
    timeZone: str
    updated: str


class PaginatedResponseCalendar(_PaginatedResponseBase):
    """Paginated response specifically for the Calendar client."""

    items: list[GoogleCalendarEntityJson]


class PaginatedResponseFit(TypedDict):
    """Paginated response specifically for the Fit client."""

    minStartTimeNs: str
    maxEndTimeNs: str
    dataSourceId: str
    point: list[dict[str, object]]


class PaginatedResponsePhotos(_PaginatedResponseBase):
    """Paginated response specifically for the Photos client."""

    albums: list[GooglePhotosEntityJson]


AnyPaginatedResponse: TypeAlias = (
    PaginatedResponseCalendar | PaginatedResponseFit | PaginatedResponsePhotos
)


class GoogleClient(
    Generic[GetJsonResponseGoogleClient],
    OAuthClient[GetJsonResponseGoogleClient],
):
    """Custom client for interacting with the Google APIs."""

    ACCESS_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # noqa: S105
    AUTH_LINK_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
    BASE_URL: str

    DEFAULT_PARAMS: ClassVar[
        dict[StrBytIntFlt, StrBytIntFlt | Iterable[StrBytIntFlt] | None]
    ] = {
        "pageSize": "50",
    }

    def get_items(
        self,
        url: str,
        *,
        list_key: Literal[
            "albums",
            "drives",
            "files",
            "items",
            "mediaItems",
            "point",
        ] = "items",
        params: (
            dict[
                StrBytIntFlt,
                StrBytIntFlt | Iterable[StrBytIntFlt] | None,
            ]
            | None
        ) = None,
        method_override: Callable[..., Response] | None = None,
    ) -> list[GetJsonResponseGoogleClient]:
        """List generic items on Google's API(s).

        Args:
            url (str): the API endpoint to send a request to
            list_key (str): the key to use in extracting the data from the response
            method_override (Callable): the method to use to get the data (e.g. GET,
                POST)
            params (dict): any extra params to be passed in the request


        Returns:
            list: a list of dicts, each representing an item from the API
        """

        params = (
            {**self.DEFAULT_PARAMS, **params} if params else deepcopy(self.DEFAULT_PARAMS)
        )
        LOGGER.info(
            "Listing all items at endpoint `%s` with params %s",
            url,
            dumps(params),
        )

        res: AnyPaginatedResponse = self._request_json_response(
            method=method_override or get,
            url=url,
            params=params,
        )  # type: ignore[assignment]

        item_list: list[GetJsonResponseGoogleClient] = res[
            list_key  # type: ignore[typeddict-item]
        ]

        while next_token := res.get("nextPageToken"):
            params = {**params, "pageToken": next_token}  # type: ignore[dict-item]
            res = self._request_json_response(
                method=method_override or get,
                url=url,
                params=params,
            )  # type: ignore[assignment]

            item_list.extend(res[list_key])  # type: ignore[typeddict-item]
            LOGGER.debug("Found %i items so far", len(item_list))

        return item_list
