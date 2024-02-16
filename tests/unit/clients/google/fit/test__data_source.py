"""Unit Tests for `wg_utilities.clients.google_fit.DataSource`."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from wg_utilities.clients import GoogleFitClient
from wg_utilities.clients.google_fit import DataSource


def test_instantiation(google_fit_client: GoogleFitClient) -> None:
    """Test that the `DataSource` class can be instantiated."""

    data_source = DataSource(
        data_source_id="derived:com.google.step_count.delta:com.google.android.gms:estimated_steps",
        google_client=google_fit_client,
    )

    assert isinstance(data_source, DataSource)
    assert (
        data_source.data_source_id
        == "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
    )


def test_description_property(data_source: DataSource) -> None:
    """Test that the `description` property returns the data source's description."""

    assert not hasattr(data_source, "_description")

    with patch.object(
        data_source.google_client,
        "get_json_response",
        wraps=data_source.google_client.get_json_response,
    ) as mock_get_json_response:
        description = data_source.description

    mock_get_json_response.assert_called_once_with(
        f"/users/me/dataSources/{data_source.data_source_id}",
    )

    assert description == {
        "application": {"packageName": "com.google.android.gms"},
        "dataQualityStandard": [],
        "dataStreamId": data_source.data_source_id,
        "dataStreamName": "estimated_steps",
        "dataType": {
            "field": [{"format": "integer", "name": "steps"}],
            "name": "com.google.step_count.delta",
        },
        "type": "derived",
    }


@pytest.mark.parametrize(
    ("from_datetime", "to_datetime", "expected_url_range", "expected_count"),
    [
        (
            datetime(2023, 1, 9, 0, 0, 0),
            datetime(2023, 1, 10, 16, 15, 00),
            "1673222400000000000-1673367300000000000",
            6052,
        ),
        (
            datetime(2023, 1, 9, 0, 0, 0),
            None,
            "1673222400000000000-1673367600000000000",
            6052,
        ),
        (
            None,
            datetime(2023, 1, 10, 16, 15, 00),
            "1673308800000000000-1673367300000000000",
            1183,
        ),
    ],
)
def test_sum_data_points_in_range(
    data_source: DataSource,
    from_datetime: datetime,
    to_datetime: datetime,
    expected_url_range: str,
    expected_count: int,
) -> None:
    """Test `sum_data_points_in_range` sums data points in a given range correctly."""

    with patch.object(
        data_source.google_client,
        "get_items",
        wraps=data_source.google_client.get_items,
    ) as mock_get_items, freeze_time("2023-01-10 16:20:00"):
        count = data_source.sum_data_points_in_range(
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

    mock_get_items.assert_called_once_with(
        "/users/me/dataSources/derived:com.google.step_count.delta:com.google.android.gms:estimated_steps/datasets/"
        + expected_url_range,
        list_key="point",
    )

    assert count == expected_count


def test_data_type_field_format_property(data_source: DataSource) -> None:
    """Test that the `data_type_field_format` property returns the correct value."""

    with patch.object(
        data_source.google_client,
        "get_json_response",
        wraps=data_source.google_client.get_json_response,
    ) as mock_get_json_response:
        data_type_field_format = data_source.data_type_field_format

    mock_get_json_response.assert_called_once_with(
        f"/users/me/dataSources/{data_source.data_source_id}",
    )

    assert data_type_field_format == "integer"


def test_test_data_type_field_format_property_invalid_description(
    data_source: DataSource,
) -> None:
    """Test that `data_type_field_format` property raises an exception."""

    with patch.object(
        data_source.google_client,
        "get_json_response",
        wraps=data_source.google_client.get_json_response,
    ) as mock_get_json_response:
        mock_get_json_response.return_value = {
            "dataType": {
                "field": [
                    {"format": "integer", "name": "intSteps"},
                    {"format": "string", "name": "stringSteps"},
                ],
                "name": "com.google.step_count.delta",
            },
        }
        with pytest.raises(
            ValueError,
            match=r"Unexpected number of dataType fields \(2\): intSteps, stringSteps",
        ):
            _ = data_source.data_type_field_format

    mock_get_json_response.assert_called_once_with(
        f"/users/me/dataSources/{data_source.data_source_id}",
    )
