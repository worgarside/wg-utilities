"""Custom client for interacting with Google's Fit API"""
from __future__ import annotations

from datetime import datetime
from logging import Logger
from typing import Literal, TypedDict

from wg_utilities.clients._google import GoogleClient, _GoogleEntityInfo
from wg_utilities.functions.datetime_helpers import DatetimeFixedUnit as DFUnit
from wg_utilities.functions.datetime_helpers import utcnow


class _DataSourceDataTypeFieldInfo(TypedDict):
    format: Literal[
        "blob", "floatList", "floatPoint", "integer", "integerList", "map", "string"
    ]
    name: str


class _DataSourceDataTypeInfo(TypedDict):
    field: list[_DataSourceDataTypeFieldInfo]
    name: str


class _DataSourceDescriptionInfo(TypedDict):
    application: dict[str, str]
    dataStreamId: str
    dataStreamName: str
    dataType: _DataSourceDataTypeInfo


class _GoogleFitDataPointInfo(_GoogleEntityInfo):
    id: str
    startTimeNanos: str
    endTimeNanos: str
    dataTypeName: str
    originDataSourceId: str
    value: list[dict[str, int]]


class DataSource:
    """Class for interacting with Google Fit Data Sources. An example of a data source
    is Strava, Google Fit, MyFitnessPal, etc. The ID is something _like_ "...weight",
    "...calories burnt"

    Args:
        data_source_id (str): the unique ID of the data source
        google_client (GoogleClient): a GoogleClient instance, needed for getting
         DataSource info
    """

    DP_VALUE_KEY_LOOKUP = {"floatPoint": "fpVal", "integer": "intVal"}

    def __init__(self, data_source_id: str, *, google_client: GoogleClient):
        self.data_source_id = data_source_id
        self.url = (
            f"{GoogleFitClient.BASE_URL}/users/me/dataSources/{self.data_source_id}"
        )
        self.google_client = google_client

        self._description: _DataSourceDescriptionInfo

    @property
    def description(self) -> _DataSourceDescriptionInfo:
        """
        Returns:
            dict: the JSON description of this data source
        """
        if not hasattr(self, "_description"):
            self._description = self.google_client.session.get(self.url).json()

        return self._description

    def sum_data_points_in_range(
        self,
        from_datetime: datetime | None = None,
        to_datetime: datetime | None = None,
    ) -> int:
        """Gets the sum of data points in the given range: if no `from_datetime` is
        provided, it defaults to the start of today; if no `to_datetime` is provided
        then it defaults to now.

        Args:
            from_datetime (datetime): lower boundary for step count
            to_datetime (datetime): upper boundary for step count

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
                / DFUnit.NANOSECOND.value
            )
        )

        to_nano = int(
            int(to_datetime.timestamp() * 1000000000)
            if to_datetime
            else utcnow(DFUnit.NANOSECOND)  # type: ignore[arg-type]
        )

        data_points: list[_GoogleFitDataPointInfo] = self.google_client.get_items(
            f"{self.url}/datasets/{from_nano}-{to_nano}",
            "point",
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
    ) -> Literal[
        "blob", "floatList", "floatPoint", "integer", "integerList", "map", "string"
    ]:
        """
        Returns:
            str: the field format of this data source (i.e. "integer" or "floatPoint")

        Raises:
            Exception: if more than 1 dataType field value is found
        """
        data_type_fields = self.description["dataType"]["field"]
        if len(data_type_fields) != 1:
            raise Exception(
                f"Unexpected number of dataType fields ({len(data_type_fields)}): "
                + ", ".join(f["name"] for f in data_type_fields)
            )

        return data_type_fields[0]["format"]

    @property
    def data_point_value_key(self) -> Literal["fpVal", "intVal"]:
        """
        Returns:
            str: the key to use when extracting data from a data point
        """
        # pylint: disable=line-too-long
        return self.DP_VALUE_KEY_LOOKUP[self.data_type_field_format]  # type: ignore[return-value]


class GoogleFitClient(GoogleClient):
    """Custom client for interacting with the Google Fit API

    See Also:
        GoogleClient: the base Google client, used for authentication and common
         functions
    """

    BASE_URL = "https://www.googleapis.com/fitness/v1"

    def __init__(
        self,
        project: str,
        scopes: list[str] | None = None,
        client_id_json_path: str | None = None,
        creds_cache_path: str | None = None,
        access_token_expiry_threshold: int = 60,
        logger: Logger | None = None,
    ):
        super().__init__(
            project,
            scopes=scopes,
            client_id_json_path=client_id_json_path,
            creds_cache_path=creds_cache_path,
            access_token_expiry_threshold=access_token_expiry_threshold,
            logger=logger,
        )
        self.data_sources: dict[str, DataSource] = {}

    def get_data_source(self, data_source_id: str) -> DataSource:
        """Gets a data source based on its UID. DataSource instances are cached for the
         lifetime of the GoogleClient instance

        Args:
            data_source_id (str): the UID of the data source

        Returns:
            DataSource: an instance, ready to use!
        """

        # TODO why isn't this just a list an we compare the istance IDs?
        if (data_source := self.data_sources.get(data_source_id)) is None:
            data_source = DataSource(data_source_id, google_client=self)
            self.data_sources[data_source_id] = data_source

        return data_source
