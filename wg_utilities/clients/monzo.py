"""Custom client for interacting with Monzo's API"""

from logging import getLogger, DEBUG

from datetime import datetime, timedelta
from requests import get, put

from wg_utilities.clients._generic import OauthClient
from wg_utilities.functions import user_data_dir, cleanse_string
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


# pylint: disable=too-many-public-methods
class Pot:
    """Read-only class for Monzo pots"""

    def __init__(self, json):
        self.json = json

    @property
    def available_for_bills(self):
        """
        Returns:
            bool: if the pot can be used directly for bills
        """
        return self.json.get("available_for_bills")

    @property
    def balance(self):
        """
        Returns:
            float: the pot's balance in GBP
        """
        return self.json.get("balance", 0) / 100

    @property
    def charity_id(self):
        """
        Returns:
            str: not sure!
        """
        return self.json.get("charity_id")

    @property
    def cover_image_url(self):
        """
        Returns:
            str: URL for the cover image
        """
        return self.json.get("cover_image_url")

    @property
    def created_datetime(self):
        """
        Returns:
            datetime: when the pot was created
        """
        if "created" not in self.json:
            return None

        return datetime.strptime(self.json["created"], DATETIME_FORMAT)

    @property
    def currency(self):
        """
        Returns:
            str: the currency of the pot
        """
        return self.json.get("currency")

    @property
    def current_account_id(self):
        """
        Returns:
            str: the UUID of the parent account
        """
        return self.json.get("current_account_id")

    @property
    def deleted(self):
        """
        Returns:
            bool: has the pot been deleted
        """
        return self.json.get("deleted")

    @property
    def goal_amount(self):
        """
        Returns:
            float: the user-set goal amount for the pot
        """
        if not (goal_amount := self.json.get("goal_amount")):
            return None

        return goal_amount / 100

    @property
    def has_virtual_cards(self):
        """
        Returns:
            bool: if the pot has virtual cards attached
        """
        return self.json.get("has_virtual_cards")

    @property
    def id(self):
        """
        Returns:
            str: the pot's UUID
        """
        return self.json.get("id")

    @property
    def is_tax_pot(self):
        """
        Returns:
            bool: is the pot taxed? I'm not sure
        """
        return self.json.get("is_tax_pot")

    @property
    def isa_wrapper(self):
        """
        Returns:
            str: is the pot ISA-wrapped?
        """
        return self.json.get("isa_wrapper")

    @property
    def locked(self):
        """
        Returns:
            bool: is the pot locked
        """
        return self.json.get("locked")

    @property
    def name(self):
        """
        Returns:
            str: the name of the pot
        """
        return self.json.get("name")

    @property
    def product_id(self):
        """
        Returns:
            str: the ID of the product applied to the pot (e.g. savings)
        """
        return self.json.get("product_id")

    @property
    def round_up(self):
        """
        Returns:
            bool: is the pot where all round ups go
        """
        return self.json.get("round_up")

    @property
    def round_up_multiplier(self):
        """
        Returns:
            int: the multiplier applied to the pot's round-ups
        """
        return self.json.get("round_up_multiplier")

    @property
    def style(self):
        """
        Returns:
            str: the pot background image
        """
        return self.json.get("style")

    @property
    def type(self):
        """
        Returns:
            str: the type of pot (e.g. flex saver)
        """
        return self.json.get("type")

    @property
    def updated_datetime(self):
        """
        Returns:
            datetime: when the pot was updated last
        """
        if "updated" not in self.json:
            return None

        return datetime.strptime(self.json["updated"], DATETIME_FORMAT)

    def __str__(self):
        return f"{self.name} | {self.id}"


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

        self._current_account = None

    def deposit_into_pot(self, pot, amount_pence, dedupe_id=None):
        """Move money from an account owned by the currently authorised user into one
         of their pots

        Args:
            pot (Pot): the target pot
            amount_pence (int): the amount of money to depoist, in pence
            dedupe_id (str): unique string used to de-duplicate deposits. Will be
             created if not provided
        """

        dedupe_id = dedupe_id or "|".join([pot.id, str(amount_pence)])

        res = put(
            f"{self.BASE_URL}/pots/{pot.id}/deposit",
            headers=self.request_headers,
            data={
                "source_account_id": self.current_account.id,
                "amount": amount_pence,
                "dedupe_id": dedupe_id,
            },
        )
        res.raise_for_status()

    def list_accounts(self, ignore_closed=True, account_type=None):
        """Gets a list of the user's accounts

        Args:
            ignore_closed (bool): whether to include closed accounts in the response
            account_type (str): the type of account(s) to find; submitted as param in
             request

        Yields:
            Account: Account instances, containing all related info
        """

        res = self.get_json_response(
            "/accounts", params={"account_type": account_type} if account_type else None
        )

        for account in res.get("accounts", []):
            if ignore_closed and account.get("closed", False) is True:
                continue
            yield Account(account, self)

    def list_pots(self, ignore_deleted=True):
        """Gets a list of the user's pots

        Args:
            ignore_deleted (bool): whether to include deleted pots in the response

        Yields:
            Pot: Pot instances, containing all related info
        """

        res = self.get_json_response(
            "/pots", params={"current_account_id": self.current_account.id}
        )

        for pot in res.get("pots", []):
            if ignore_deleted and pot.get("deleted", False) is True:
                continue
            yield Pot(pot)

    def get_pot_by_id(self, pot_id):
        """Get a pot from its ID

        Args:
            pot_id (str): the ID of the pot to find

        Returns:
            Pot: the Pot instance
        """
        for pot in self.list_pots():
            if pot.id == pot_id:
                return pot

        return None

    def get_pot_by_name(self, pot_name, exact_match=False):
        """Get a pot from its name

        Args:
            pot_name (str): the name of the pot to find
            exact_match (bool): if False, all pot names will be cleansed before
             evaluation

        Returns:
            Pot: the Pot instance
        """
        if not exact_match:
            pot_name = cleanse_string(pot_name)

        for pot in self.list_pots():
            found_name = (
                cleanse_string(pot.name).lower() if not exact_match else pot_name
            )
            if found_name.lower() == pot_name.lower():
                return pot

        return None

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

    @property
    def current_account(self):
        """Get the main account for the Monzo user. We assume there'll only be one
         main account per user

        Returns:
            Account: the user's main account, instantiated
        """
        if not self._current_account:
            self._current_account = list(self.list_accounts(account_type="uk_retail"))[
                0
            ]

        return self._current_account
