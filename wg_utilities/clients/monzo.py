"""Custom client for interacting with Monzo's API"""

from logging import getLogger, DEBUG

from datetime import datetime, timedelta
from requests import get

from wg_utilities.clients._generic_oauth import OauthClient
from wg_utilities.functions import user_data_dir
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class Account:
    """Class for managing individual bank accounts"""

    def __init__(self, json, monzo_client=None, balance_update_threshold=15):
        self.json = json
        self._monzo_client = monzo_client

        self._balance_variables = None

        self.last_balance_update = datetime(1970, 1, 1)
        self.balance_update_threshold = balance_update_threshold

    def _get_balance_property(self, var_name):
        """Gets a value for a balance-specific property, updating the values if
         necessary (i.e. if they don't already exist). This also has a check to see if
         property is relevant for the given entity type and if not it just returns None

        Args:
            var_name (str): the name of the variable

        Returns:
            str: the value of the balance property
        """

        if (
            self._balance_variables is not None
            and var_name not in self._balance_variables
        ):
            # assume it's not a valid value so there's no point polling the API again
            return None

        if self.last_balance_update <= (
            datetime.utcnow() - timedelta(minutes=self.balance_update_threshold)
        ):
            self.update_balance_variables()

        return self._balance_variables[var_name]

    def update_balance_variables(self):
        """Updates the balance-related instance attributes with the latest values from
        the API
        """

        self._balance_variables = self._monzo_client.get_json_response(
            "/balance", params={"account_id": self.id}
        )

        # convert values from pence to pounds
        for key, value in self._balance_variables.items():
            if isinstance(value, int):
                self._balance_variables[key] = value / 100

        self.last_balance_update = datetime.utcnow()

    @property
    def account_number(self):
        """
        Returns:
            str: the account's account number
        """
        return self.json.get("account_number")

    @property
    def balance(self):
        """
        Returns:
            float: the currently available balance of the account
        """
        return self._get_balance_property("balance")

    @property
    def balance_including_flexible_savings(self):
        """
        Returns:
            float: the currently available balance of the account, including flexible
             savings pots
        """
        return self._get_balance_property("balance_including_flexible_savings")

    @property
    def created_datetime(self):
        """
        Returns:
            datetime: when the account was created
        """
        if "created" not in self.json:
            return None

        return datetime.strptime(self.json["created"], DATETIME_FORMAT)

    @property
    def description(self):
        """
        Returns:
            str: the description of the account
        """
        return self.json.get("description")

    @property
    def id(self):
        """
        Returns:
            str: the account's UUID
        """
        return self.json.get("id")

    @property
    def sort_code(self):
        """
        Returns:
            str: the account's sort code
        """
        return self.json.get("sort_code")

    @property
    def spend_today(self):
        """
        Returns:
            float: the amount spent from this account today (considered from approx
             4am onwards)
        """
        return self._get_balance_property("spend_today")

    @property
    def total_balance(self):
        """
        Returns:
            str: the sum of the currently available balance of the account and the
             combined total of all the user’s pots
        """
        return self._get_balance_property("total_balance")


class MonzoClient(OauthClient):
    """Custom client for interacting with Monzo's API"""

    ACCESS_TOKEN_ENDPOINT = "https://api.monzo.com/oauth2/token"
    BASE_URL = "https://api.monzo.com"
    CREDS_FILE_PATH = user_data_dir(file_name="monzo_api_creds.json")

    def __init__(
        self,
        *,
        client_id,
        client_secret,
        redirect_uri="http://0.0.0.0:5001/get_auth_code",
        access_token_expiry_threshold=60,
        log_requests=False,
        creds_cache_path=None,
    ):
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            access_token_expiry_threshold=access_token_expiry_threshold,
            log_requests=log_requests,
            creds_cache_path=creds_cache_path,
        )

    def list_accounts(self, ignore_closed=True):
        """Gets a list of the user's accounts

        Args:
            ignore_closed (bool): whether to include closed accounts in the response

        Yields:
            Account: Account instances, containing all related info
        """
        res = self.get_json_response(
            "/accounts",
        )

        for account in res.get("accounts", []):
            if ignore_closed and account.get("closed", False) is True:
                continue
            yield Account(account, self)

    @property
    def access_token_has_expired(self):
        """Custom expiry check for Monzo client as JWT doesn't seem to include expiry
         time. Any errors/missing credentials result in a default value of True

        Returns:
            bool: expiry status of JWT
        """
        self._load_local_credentials()

        if not (access_token := self._credentials.get("access_token")):
            return True

        res = get(
            f"{self.BASE_URL}/ping/whoami",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        return res.json().get("authenticated", False) is False
