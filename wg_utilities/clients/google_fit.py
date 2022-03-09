"""Custom client for interacting with Google's Fit API"""

from datetime import datetime

from wg_utilities.clients._generic import GoogleClient
from wg_utilities.functions.datetime_helpers import utcnow, DatetimeFixedUnit as DFUnit


class DataSource:
    """Class for interacting with Google Fit Data Sources

    Args:
        data_source_id (str): the unique ID of the data source
        google_client (GoogleClient): a GoogleClient instance, needed for getting
         DataSource info
    """

    DP_VALUE_KEY_LOOKUP = {"floatPoint": "fpVal", "integer": "intVal"}

    GOOGLE_CLIENT = None

    def __init__(self, data_source_id, *, google_client=None):
        self.data_source_id = data_source_id
        self.url = (
            f"{GoogleFitClient.BASE_URL}/users/me/dataSources/{self.data_source_id}"
        )

        self._description = None

        if isinstance(google_client, GoogleClient) and self.GOOGLE_CLIENT is None:
            # This is a class attribute, so it can be shared across all instances
            DataSource.GOOGLE_CLIENT = google_client

    @property
    def description(self):
        """
        Returns:
            dict: the JSON description of this data source
        """
        if not self._description:
            self._description = self.google_client.session.get(self.url).json()

        return self._description

    def sum_data_points_in_range(self, from_datetime=None, to_datetime=None):
        """Gets the sum of data points in the given range: if no `from_datetime` is
        provided, it defaults to the start of today; if no `to_datetime` is provided
        then it defaults to now.

        Args:
            from_datetime (datetime): lower boundary for step count
            to_datetime (datetime): upper boundary for step count

        Returns:
            list: a list of data point in the given range
        """

        from_nano = (
            int(from_datetime.timestamp() * 1000000000)
            if from_datetime
            else int(
                datetime.today()
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .timestamp()
                / DFUnit.NANOSECOND.value
            )
        )

        to_nano = (
            int(to_datetime.timestamp() * 1000000000)
            if to_datetime
            else utcnow(DFUnit.NANOSECOND)
        )

        data_points = self.google_client.get_items(
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
    def data_type_field_format(self):
        """
        Returns:
            str: the field format of this data source (i.e. "integer" or "floatPoint")
        """
        return self.description.get("dataType", {}).get("field", [{}])[0].get("format")

    @property
    def data_point_value_key(self):
        """
        Returns:
            str: the key to use when extracting data from a data point
        """
        return self.DP_VALUE_KEY_LOOKUP.get(self.data_type_field_format)

    @property
    def google_client(self):
        """

        Returns:
            GoogleClient: a GoogleClient instance, needed for getting DataSource info
        """
        return self.GOOGLE_CLIENT

    # pylint: disable=no-self-use
    @google_client.setter
    def google_client(self, value):
        """Sets the class attribute for the Google client to the given value

        Args:
            value (GoogleClient): a GoogleClient instance, needed for getting
             DataSource info
        """
        DataSource.GOOGLE_CLIENT = value


class GoogleFitClient(GoogleClient):
    """Custom client for interacting with the Google Fit API

    See Also:
        GoogleClient: the base Google client, used for authentication and common
         functions
    """

    BASE_URL = "https://www.googleapis.com/fitness/v1"

    def __init__(
        self,
        project,
        scopes=None,
        client_id_json_path=None,
        creds_cache_path=None,
        access_token_expiry_threshold=60,
        logger=None,
    ):
        super().__init__(
            project,
            scopes=scopes,
            client_id_json_path=client_id_json_path,
            creds_cache_path=creds_cache_path,
            access_token_expiry_threshold=access_token_expiry_threshold,
            logger=logger,
        )
        self.data_sources = {}

    def get_data_source(self, data_source_id):
        """Gets a data source based on its UID. DataSource instances are cached for the
         lifetime of the GoogleClient instance

        Args:
            data_source_id (str): the UID of the data source

        Returns:
            DataSource: an instance, ready to use!
        """

        if not (data_source := self.data_sources.get(data_source_id)):
            data_source = DataSource(data_source_id, google_client=self)
            self.data_sources[data_source_id] = data_source

        return data_source
