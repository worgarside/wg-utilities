"""Unit Tests for `wg_utilities.clients._google.GoogleClient`."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any
from unittest.mock import call, patch

from requests import Response, post

from wg_utilities.clients._google import GoogleClient
from wg_utilities.clients.json_api_client import StrBytIntFlt
from wg_utilities.clients.oauth_client import OAuthClient, OAuthCredentials


def test_instantiation(fake_oauth_credentials: OAuthCredentials) -> None:
    """Test the instantiation of the Google client."""
    client: GoogleClient[dict[str, Any]] = GoogleClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
        base_url="https://www.example.com",
        scopes=[],
    )
    assert isinstance(client, GoogleClient)
    assert isinstance(client, OAuthClient)


def test_get_items_method(fake_oauth_credentials: OAuthCredentials) -> None:
    """Test the `get_items` method."""
    client: GoogleClient[dict[str, Any]] = GoogleClient(
        client_id=fake_oauth_credentials.client_id,
        client_secret=fake_oauth_credentials.client_secret,
        base_url="https://www.example.com",
        scopes=[],
    )
    expected_items = [
        {"name": "sample.txt", "size": "500PB"},
        {"name": "backup.txt", "size": "1B"},
        {"name": "CV.docx", "size": "123kB"},
        {"name": "train_pics.zip", "size": "420GB"},
        {"name": "py.typed", "size": "0B"},
        {"name": "diary.xlsx", "size": "83kB"},
    ]

    def _req_json_res_side_effect(
        method: Callable[..., Response],
        url: str,
        params: dict[
            StrBytIntFlt,
            StrBytIntFlt | Iterable[StrBytIntFlt] | None,
        ],
    ) -> dict[str, str | list[dict[str, str]]]:
        if "pageToken" not in params:
            return {"files": expected_items[:2], "nextPageToken": "abcdef"}

        if (page_token := params.get("pageToken")) == "abcdef":
            return {"files": expected_items[2:4], "nextPageToken": "ghijkl"}

        if page_token == "ghijkl":
            return {
                "files": expected_items[4:],
                # No next page token
            }

        raise ValueError(  # pragma: no cover
            f"Unexpected request: {method!r}, {url}, {params!r}"
        )

    with patch.object(
        client, "_request_json_response", wraps=_req_json_res_side_effect
    ) as mock_request_json_response:
        items = client.get_items(
            f"{client.base_url}/endpoint",
            list_key="files",
            params={"key": "value"},
            method_override=post,
        )

    assert items == expected_items

    assert mock_request_json_response.call_args_list == [
        call(
            method=post,
            url="https://www.example.com/endpoint",
            params={"pageSize": "50", "key": "value"},
        ),
        call(
            method=post,
            url="https://www.example.com/endpoint",
            params={"pageSize": "50", "key": "value", "pageToken": "abcdef"},
        ),
        call(
            method=post,
            url="https://www.example.com/endpoint",
            params={"pageSize": "50", "key": "value", "pageToken": "ghijkl"},
        ),
    ]
