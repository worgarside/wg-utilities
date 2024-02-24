"""Custom client for interacting with Google's Fit API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from typing_extensions import TypedDict

from wg_utilities.clients._google import GoogleClient
from wg_utilities.functions.datetime_helpers import DatetimeFixedUnit as DFUnit
from wg_utilities.functions.datetime_helpers import utcnow


class _DataSourceDataTypeFieldInfo(TypedDict):
    format: Literal["floatPoint", "integer"]
    name: str


class _DataSourceDataTypeInfo(TypedDict):
    field: list[_DataSourceDataTypeFieldInfo]
    name: str


class _DataSourceDescriptionInfo(TypedDict):
    application: dict[str, str]
    dataStreamId: str
    dataStreamName: str
    dataType: _DataSourceDataTypeInfo


class _GoogleFitDataPointInfo(TypedDict):
    id: str
    startTimeNanos: str
    endTimeNanos: str
    dataTypeName: str
    originDataSourceId: str
    value: list[dict[str, int]]


class DataSource:
    """Class for interacting with Google Fit Data Sources.

    An example of a data source is Strava, Google Fit, MyFitnessPal, etc. The ID is
    something _like_ "...weight", "...calories burnt".

    Args:
        data_source_id (str): the unique ID of the data source
        google_client (GoogleClient): a GoogleClient instance, needed for getting DataSource info
    """

    DP_VALUE_KEY_LOOKUP: ClassVar[DataPointValueKeyLookupInfo] = {
        "floatPoint": "fpVal",
        "integer": "intVal",
    }

    class DataPointValueKeyLookupInfo(TypedDict):
        """Typing info for the Data Point lookup dict."""

        floatPoint: Literal["fpVal"]
        integer: Literal["intVal"]

    def __init__(self, data_source_id: str, *, google_client: GoogleFitClient):
        self.data_source_id = data_source_id
        self.url = f"/users/me/dataSources/{self.data_source_id}"
        self.google_client = google_client

        self._description: _DataSourceDescriptionInfo

    @property
    def description(self) -> _DataSourceDescriptionInfo:
        """Description of the data source, in JSON format.

        Returns:
            dict: the JSON description of this data source
        """
        if not hasattr(self, "_description"):
            self._description = self.google_client.get_json_response(self.url)

        return self._description

    def sum_data_points_in_range(
        self,
        from_datetime: datetime | None = None,
        to_datetime: datetime | None = None,
    ) -> int:
        """Get the sum of data points in the given range.

        If no `from_datetime` is provided, it defaults to the start of today; if no
        `to_datetime` is provided then it defaults to now.

        Args:
            from_datetime (datetime): lower boundary for step count. Defaults to
                start of today.
            to_datetime (datetime): upper boundary for step count. Defaults to now.

        Returns:
            int: a sum of data points in the given range
        """

        from_nano = int(
            int(from_datetime.timestamp() * 1000000000)
            if from_datetime
            else int(
                datetime.today()
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .timestamp()
                / DFUnit.NANOSECOND.value,
            ),
        )

        to_nano = int(
            int(to_datetime.timestamp() * 1000000000)
            if to_datetime
            else utcnow(DFUnit.NANOSECOND),
        )

        data_points: list[_GoogleFitDataPointInfo] = self.google_client.get_items(
            f"{self.url}/datasets/{from_nano}-{to_nano}",
            list_key="point",
        )

        count = 0
        for point in data_points:
            if (
                int(point["startTimeNanos"]) >= from_nano
                and int(point["endTimeNanos"]) <= to_nano
            ):
                count += point["value"][0][self.data_point_value_key]

        return count

    @property
    def data_type_field_format(
        self,
    ) -> Literal["floatPoint", "integer"]:
        """Field format of the data type.

        Original return type on here was as follows, think it was for other endpoints
        I haven't implemented

        ```
        Literal[
            "blob", "floatList", "floatPoint", "integer", "integerList", "map", "string"
        ]
        ```

        Returns:
            str: the field format of this data source (i.e. "integer" or "floatPoint")

        Raises:
            Exception: if more than 1 dataType field value is found
        """
        data_type_fields = self.description["dataType"]["field"]
        if len(data_type_fields) != 1:
            raise ValueError(
                f"Unexpected number of dataType fields ({len(data_type_fields)}): "
                + ", ".join(f["name"] for f in data_type_fields),
            )

        return data_type_fields[0]["format"]

    @property
    def data_point_value_key(self) -> Literal["fpVal", "intVal"]:
        """Key to use when looking up the value of a data point.

        Returns:
            str: the key to use when extracting data from a data point
        """

        return self.DP_VALUE_KEY_LOOKUP[self.data_type_field_format]


class GoogleFitClient(GoogleClient[Any]):
    """Custom client for interacting with the Google Fit API.

    See Also:
        GoogleClient: the base Google client, used for authentication and common functions
    """

    BASE_URL = "https://www.googleapis.com/fitness/v1"

    DEFAULT_SCOPES: ClassVar[list[str]] = [
        "https://www.googleapis.com/auth/fitness.activity.read",
        "https://www.googleapis.com/auth/fitness.body.read",
        "https://www.googleapis.com/auth/fitness.location.read",
        "https://www.googleapis.com/auth/fitness.nutrition.read",
    ]

    _data_sources: dict[str, DataSource]

    def get_data_source(self, data_source_id: str) -> DataSource:
        """Get a data source based on its UID.

        DataSource instances are cached for the lifetime of the GoogleClient instance

        Args:
            data_source_id (str): the UID of the data source

        Returns:
            DataSource: an instance, ready to use!
        """

        if (data_source := self.data_sources.get(data_source_id)) is None:
            data_source = DataSource(data_source_id=data_source_id, google_client=self)
            self.data_sources[data_source_id] = data_source

        return data_source

    @property
    def data_sources(self) -> dict[str, DataSource]:
        """Data sources available to this client.

        Returns:
            dict: a dict of data sources, keyed by their UID
        """
        if not hasattr(self, "_data_sources"):
            self._data_sources = {}

        return self._data_sources
