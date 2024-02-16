"""Unit Tests for `wg_utilities.clients.json_api_client.JsonApiClient`."""

from __future__ import annotations

from http import HTTPStatus
from logging import DEBUG
from typing import Any
from unittest.mock import call, patch

import pytest
from requests import HTTPError, get, post
from requests_mock import Mocker

from wg_utilities.clients.json_api_client import JsonApiClient


def test_get_method_calls_request_correctly(
    json_api_client: JsonApiClient[dict[str, Any]],
) -> None:
    """Test the `_get` method calls `request` correctly."""

    with patch.object(json_api_client, "_request") as mock_request:
        json_api_client._get(
            "test_endpoint",
        )
        json_api_client._get(
            "test_endpoint",
            params={"param_key": "param_value"},
            header_overrides={"header_key": "header_value"},
            timeout=10,
            json={"json_key": "json_value"},
        )

    assert mock_request.call_args_list == [
        call(
            method=get,
            url="test_endpoint",
            params=None,
            header_overrides=None,
            timeout=None,
            json=None,
            data=None,
        ),
        call(
            method=get,
            url="test_endpoint",
            params={"param_key": "param_value"},
            header_overrides={"header_key": "header_value"},
            timeout=10,
            json={"json_key": "json_value"},
            data=None,
        ),
    ]


def test_post_method_calls_request_correctly(
    json_api_client: JsonApiClient[dict[str, Any]],
) -> None:
    """Test the `_post` method calls `request` correctly."""

    with patch.object(json_api_client, "_request") as mock_request:
        json_api_client._post(
            "test_endpoint",
        )
        json_api_client._post(
            "test_endpoint",
            params={"param_key": "param_value"},
            header_overrides={"header_key": "header_value"},
            timeout=10,
            json={"json_key": "json_value"},
        )

    assert mock_request.call_args_list == [
        call(
            method=post,
            url="test_endpoint",
            params=None,
            header_overrides=None,
            timeout=None,
            json=None,
            data=None,
        ),
        call(
            method=post,
            url="test_endpoint",
            params={"param_key": "param_value"},
            header_overrides={"header_key": "header_value"},
            timeout=10,
            json={"json_key": "json_value"},
            data=None,
        ),
    ]


def test_request_method_sends_correct_request(
    json_api_client: JsonApiClient[dict[str, Any]],
    mock_requests: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the `_request`` method sends the correct request."""

    mock_requests.post(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={"key": "value"},
    )

    res = json_api_client._request(
        method=post,
        url="/test_endpoint",
        params={"test_param": "test_value"},
        json={"test_json_key": "test_json_value"},
        header_overrides={"test_header": "test_value"},
    )

    assert res.json() == {"key": "value"}
    assert res.status_code == HTTPStatus.OK
    assert res.reason == HTTPStatus.OK.phrase

    request = mock_requests.request_history.pop(0)

    assert len(mock_requests.request_history) == 0

    assert request.method == "POST"
    assert request.url == "https://api.example.com/test_endpoint?test_param=test_value"
    assert "Authorization" not in request.headers
    assert request.headers["test_header"] == "test_value"
    assert request.json() == {"test_json_key": "test_json_value"}
    assert request.qs == {"test_param": ["test_value"]}

    assert caplog.records[0].levelno == DEBUG
    assert (
        caplog.records[0].message
        == 'POST https://api.example.com/test_endpoint: {"test_param": "test_value"}'
    )


def test_request_raises_exception_for_non_200_response(
    json_api_client: JsonApiClient[dict[str, Any]],
    mock_requests: Mocker,
) -> None:
    """Test that the `_request`` method raises an exception for non-200 responses."""

    mock_requests.post(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.NOT_FOUND,
        reason=HTTPStatus.NOT_FOUND.phrase,
    )

    with pytest.raises(HTTPError) as exc_info:
        json_api_client._request(
            method=post,
            url="/test_endpoint",
        )

    assert exc_info.value.response is not None
    assert exc_info.value.response.status_code == HTTPStatus.NOT_FOUND
    assert exc_info.value.response.reason == HTTPStatus.NOT_FOUND.phrase

    assert (
        str(exc_info.value) == "404 Client Error: Not Found for url: "
        "https://api.example.com/test_endpoint"
    )

    json_api_client.validate_request_success = False

    res = json_api_client._request(
        method=post,
        url="/test_endpoint",
    )

    assert res.status_code == HTTPStatus.NOT_FOUND


def test_request_validate_request_success_false(
    json_api_client: JsonApiClient[dict[str, Any]],
    mock_requests: Mocker,
) -> None:
    """Test that the `_request`` method raises an exception for non-200 responses."""

    json_api_client.validate_request_success = False

    mock_requests.post(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.NOT_FOUND,
        reason=HTTPStatus.NOT_FOUND.phrase,
    )

    res = json_api_client._request(
        method=post,
        url="/test_endpoint",
    )

    assert res.status_code == HTTPStatus.NOT_FOUND


def test_request_json_response(
    json_api_client: JsonApiClient[dict[str, Any]],
    mock_requests: Mocker,
) -> None:
    """Test that the request method returns a JSON response."""

    mock_requests.get(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={"key": "value"},
    )
    with patch.object(
        json_api_client,
        "_request_json_response",
        wraps=json_api_client._request_json_response,
    ) as mock_request:
        res = json_api_client._request_json_response(
            method=get,
            url="/test_endpoint",
            params={"test_param": "test_value"},
            json={"test_key": "test_value"},
            header_overrides={"test_header": "test_value"},
        )

    mock_request.assert_called_once_with(
        method=get,
        url="/test_endpoint",
        params={"test_param": "test_value"},
        json={"test_key": "test_value"},
        header_overrides={"test_header": "test_value"},
    )

    assert res == {"key": "value"}


def test_request_json_response_defaults_to_empty_dict_for_no_content(
    json_api_client: JsonApiClient[dict[str, Any]],
    mock_requests: Mocker,
) -> None:
    """Test that the request method returns an empty dict for no content."""

    mock_requests.get(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.NO_CONTENT,
        reason=HTTPStatus.NO_CONTENT.phrase,
    )

    res = json_api_client._request_json_response(
        method=get,
        url="/test_endpoint",
    )

    assert res == {}


def test_request_json_response_defaults_to_empty_dict_with_json_decode_error(
    json_api_client: JsonApiClient[dict[str, Any]],
    mock_requests: Mocker,
) -> None:
    """Test that the request method returns an empty dict for JSON decode errors."""

    mock_requests.get(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        text="",
    )

    res = json_api_client._request_json_response(
        method=get,
        url="/test_endpoint",
    )

    assert res == {}


def test_request_json_response_raises_exception_with_invalid_json(
    json_api_client: JsonApiClient[dict[str, Any]],
    mock_requests: Mocker,
) -> None:
    """Test that the request method returns an empty dict for JSON decode errors."""

    mock_requests.get(
        "https://api.example.com/test_endpoint",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        text="invalid_json",
    )

    with pytest.raises(ValueError) as exc_info:
        json_api_client._request_json_response(
            method=get,
            url="/test_endpoint",
        )

    assert str(exc_info.value) == "invalid_json"


def test_get_json_response_calls_request_json_response(
    json_api_client: JsonApiClient[dict[str, Any]],
) -> None:
    """Test the `get_json_response` method calls `_request_json_response` correctly."""

    with patch.object(
        json_api_client,
        "_request_json_response",
    ) as mock_request_json_response:
        json_api_client.get_json_response(
            "/test_endpoint",
            params={"test_param": "test_value"},
            header_overrides={"test_header": "test_value"},
            timeout=10,
            json={"test_key": "test_value"},
        )

    mock_request_json_response.assert_called_once_with(
        method=get,
        url="/test_endpoint",
        params={"test_param": "test_value"},
        header_overrides={"test_header": "test_value"},
        timeout=10,
        json={"test_key": "test_value"},
        data=None,
    )


def test_post_json_response_calls_request_json_response(
    json_api_client: JsonApiClient[dict[str, Any]],
) -> None:
    """Test the `post_json_response` method calls `_request_json_response` correctly."""

    with patch.object(
        json_api_client,
        "_request_json_response",
    ) as mock_request_json_response:
        json_api_client.post_json_response(
            "/test_endpoint",
            params={"test_param": "test_value"},
            header_overrides={"test_header": "test_value"},
            timeout=10,
            json={"test_key": "test_value"},
        )

    mock_request_json_response.assert_called_once_with(
        method=post,
        url="/test_endpoint",
        params={"test_param": "test_value"},
        header_overrides={"test_header": "test_value"},
        timeout=10,
        json={"test_key": "test_value"},
        data=None,
    )


def test_request_headers(
    json_api_client: JsonApiClient[dict[str, Any]],
) -> None:
    """Test the `request_headers` property returns the expected value."""
    assert json_api_client.request_headers == {
        "Content-Type": "application/json",
    }
