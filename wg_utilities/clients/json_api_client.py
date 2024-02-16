"""Generic no-auth JSON API client to simplify interactions."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from http import HTTPStatus
from json import JSONDecodeError, dumps
from logging import DEBUG, getLogger
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar

from requests import Response, get, post

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)

GetJsonResponse = TypeVar("GetJsonResponse", bound=Mapping[Any, Any])

StrBytIntFlt: TypeAlias = str | bytes | int | float


class JsonApiClient(Generic[GetJsonResponse]):
    """Generic no-auth JSON API client to simplify interactions.

    Sort of an SDK?
    """

    BASE_URL: str

    DEFAULT_PARAMS: ClassVar[
        dict[StrBytIntFlt, StrBytIntFlt | Iterable[StrBytIntFlt] | None]
    ] = {}

    def __init__(
        self,
        *,
        log_requests: bool = False,
        base_url: str | None = None,
        validate_request_success: bool = True,
    ):
        self.base_url = base_url or self.BASE_URL
        self.log_requests = log_requests
        self.validate_request_success = validate_request_success

    def _get(
        self,
        url: str,
        *,
        params: (
            dict[
                StrBytIntFlt,
                StrBytIntFlt | Iterable[StrBytIntFlt] | None,
            ]
            | None
        ) = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
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

    def _post(
        self,
        url: str,
        *,
        params: (
            dict[
                StrBytIntFlt,
                StrBytIntFlt | Iterable[StrBytIntFlt] | None,
            ]
            | None
        ) = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
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
        params: (
            dict[
                StrBytIntFlt,
                StrBytIntFlt | Iterable[StrBytIntFlt] | None,
            ]
            | None
        ) = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
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
                {k: v for k, v in self.DEFAULT_PARAMS.items() if k not in params},
            )
        else:
            params = deepcopy(self.DEFAULT_PARAMS)

        params = {k: v for k, v in params.items() if v is not None}

        if url.startswith("/"):
            url = f"{self.base_url}{url}"

        if self.log_requests:
            LOGGER.debug(
                "%s %s: %s",
                method.__name__.upper(),
                url,
                dumps(params, default=str),
            )

        res = method(
            url,
            headers=(
                header_overrides if header_overrides is not None else self.request_headers
            ),
            params=params,
            timeout=timeout,
            json=json,
            data=data,
        )

        if self.validate_request_success:
            res.raise_for_status()

        return res

    def _request_json_response(
        self,
        *,
        method: Callable[..., Response],
        url: str,
        params: (
            dict[
                StrBytIntFlt,
                StrBytIntFlt | Iterable[StrBytIntFlt] | None,
            ]
            | None
        ) = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
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

    def get_json_response(
        self,
        url: str,
        /,
        *,
        params: (
            dict[
                StrBytIntFlt,
                StrBytIntFlt | Iterable[StrBytIntFlt] | None,
            ]
            | None
        ) = None,
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
        /,
        *,
        params: (
            dict[
                StrBytIntFlt,
                StrBytIntFlt | Iterable[StrBytIntFlt] | None,
            ]
            | None
        ) = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
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

    @property
    def request_headers(self) -> dict[str, str]:
        """Header to be used in requests to the API.

        Returns:
            dict: auth headers for HTTP requests
        """
        return {
            "Content-Type": "application/json",
        }
