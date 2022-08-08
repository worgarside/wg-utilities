"""Custom client for interacting with Monzo's API"""
from __future__ import annotations

from datetime import datetime, timedelta
from logging import DEBUG, getLogger
from typing import Generator, Literal, TypedDict

from requests import get, put

from wg_utilities.clients._generic import OauthClient
from wg_utilities.functions import cleanse_string, user_data_dir

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class _MonzoAccountInfo(TypedDict):
    account_number: str
    balance: float
    balance_including_flexible_savings: float
    created: str
    description: str
    id: str
    sort_code: str
    spend_today: float
    total_balance: float


class _MonzoPotInfo(TypedDict):
    available_for_bills: bool
    balance: float
    charity_id: str
    cover_image_url: str
    created: str
    currency: str
    current_account_id: str
    deleted: bool
    goal_amount: float
    has_virtual_cards: bool
    id: str
    is_tax_pot: bool
    isa_wrapper: str
    locked: bool
    name: str
    product_id: str
    round_up: bool
    round_up_multiplier: float
    style: str
    type: str
    updated: str


class _BalanceVariablesInfo(TypedDict):
    balance: int
    balance_including_flexible_savings: int
    currency: Literal["GBP"]
    local_currency: str
    local_exchange_rate: int | float
    local_spend: dict[str, str | int]
    spend_today: int
    total_balance: int


class Account:
    """Class for managing individual bank accounts"""

    def __init__(
        self,
        json: _MonzoAccountInfo,
        monzo_client: MonzoClient,
        balance_update_threshold: int = 15,
    ):
        self.json = json
        self._monzo_client = monzo_client

        self._balance_variables: _BalanceVariablesInfo

        self.last_balance_update = datetime(1970, 1, 1)
        self.balance_update_threshold = balance_update_threshold

    def _get_balance_property(
        self,
        var_name: Literal[
            "balance",
            "balance_including_flexible_savings",
            "currency",
            "local_currency",
            "local_exchange_rate",
            "local_spend",
            "spend_today",
            "total_balance",
        ],
    ) -> str | float | dict[str, str | int] | None:
        """Gets a value for a balance-specific property, updating the values if
         necessary (i.e. if they don't already exist). This also has a check to see if
         property is relevant for the given entity type and if not it just returns None

        Args:
            var_name (str): the name of the variable

        Returns:
            str: the value of the balance property
        """

        if (
            hasattr(self, "_balance_variables")
            and var_name not in self._balance_variables
        ):
            # Assume it's not a valid value so there's no point polling the API again
            return None

        if self.last_balance_update <= (
            datetime.utcnow() - timedelta(minutes=self.balance_update_threshold)
        ):
            self.update_balance_variables()

        return self._balance_variables[var_name]

    def update_balance_variables(self) -> None:
        """Updates the balance-related instance attributes with the latest values from
        the API
        """
        # pylint: disable=line-too-long
        self._balance_variables = self._monzo_client.get_json_response(  # type: ignore[assignment]
            "/balance", params={"account_id": self.id}
        )

        # convert values from pence to pounds
        for key, value in self._balance_variables.items():
            if isinstance(value, (int, float)):
                # pylint: disable=line-too-long
                self._balance_variables[key] = value / 100  # type: ignore[literal-required]

        self.last_balance_update = datetime.utcnow()

    @property
    def account_number(self) -> str | None:
        """
        Returns:
            str: the account's account number
        """
        return self.json.get("account_number")

    @property
    def balance(self) -> float | None:
        """
        Returns:
            float: the currently available balance of the account
        """
        return self._get_balance_property("balance")  # type: ignore[return-value]

    @property
    def balance_including_flexible_savings(self) -> float | None:
        """
        Returns:
            float: the currently available balance of the account, including flexible
             savings pots
        """
        return self._get_balance_property(
            "balance_including_flexible_savings"
        )  # type: ignore[return-value]

    @property
    def created_datetime(self) -> datetime | None:
        """
        Returns:
            datetime: when the account was created
        """
        if "created" not in self.json:
            return None

        return datetime.strptime(self.json["created"], DATETIME_FORMAT)

    @property
    def description(self) -> str | None:
        """
        Returns:
            str: the description of the account
        """
        return self.json.get("description")

    @property
    def id(self) -> str | None:
        """
        Returns:
            str: the account's UUID
        """
        return self.json["id"]

    @property
    def sort_code(self) -> str | None:
        """
        Returns:
            str: the account's sort code
        """
        return self.json.get("sort_code")

    @property
    def spend_today(self) -> float | None:
        """
        Returns:
            float: the amount spent from this account today (considered from approx
             4am onwards)
        """
        return self._get_balance_property("spend_today")  # type: ignore[return-value]

    @property
    def total_balance(self) -> str | None:
        """
        Returns:
            str: the sum of the currently available balance of the account and the
             combined total of all the user’s pots
        """
        return self._get_balance_property("total_balance")  # type: ignore[return-value]


class Pot:
    """Read-only class for Monzo pots"""

    def __init__(self, json: _MonzoPotInfo):
        self.json = json

    @property
    def available_for_bills(self) -> bool | None:
        """
        Returns:
            bool: if the pot can be used directly for bills
        """
        return self.json.get("available_for_bills")

    @property
    def balance(self) -> float:
        """
        Returns:
            float: the pot's balance in GBP
        """
        return float(self.json.get("balance", 0)) / 100

    @property
    def charity_id(self) -> str | None:
        """
        Returns:
            str: not sure!
        """
        return self.json.get("charity_id")

    @property
    def cover_image_url(self) -> str | None:
        """
        Returns:
            str: URL for the cover image
        """
        return self.json.get("cover_image_url")

    @property
    def created_datetime(self) -> datetime | None:
        """
        Returns:
            datetime: when the pot was created
        """
        if "created" not in self.json:
            return None

        return datetime.strptime(self.json["created"], DATETIME_FORMAT)

    @property
    def currency(self) -> str | None:
        """
        Returns:
            str: the currency of the pot
        """
        return self.json.get("currency")

    @property
    def current_account_id(self) -> str | None:
        """
        Returns:
            str: the UUID of the parent account
        """
        return self.json.get("current_account_id")

    @property
    def deleted(self) -> bool | None:
        """
        Returns:
            bool: has the pot been deleted
        """
        return self.json.get("deleted")

    @property
    def goal_amount(self) -> float | None:
        """
        Returns:
            float: the user-set goal amount for the pot
        """
        if not (goal_amount := self.json.get("goal_amount")):
            return None

        return goal_amount / 100

    @property
    def has_virtual_cards(self) -> bool | None:
        """
        Returns:
            bool: if the pot has virtual cards attached
        """
        return self.json.get("has_virtual_cards")

    @property
    def id(self) -> str:
        """
        Returns:
            str: the pot's UUID
        """
        return self.json["id"]

    @property
    def is_tax_pot(self) -> bool | None:
        """
        Returns:
            bool: is the pot taxed? I'm not sure
        """
        return self.json.get("is_tax_pot")

    @property
    def isa_wrapper(self) -> str | None:
        """
        Returns:
            str: is the pot ISA-wrapped?
        """
        return self.json.get("isa_wrapper")

    @property
    def locked(self) -> bool | None:
        """
        Returns:
            bool: is the pot locked
        """
        return self.json.get("locked")

    @property
    def name(self) -> str:
        """
        Returns:
            str: the name of the pot
        """
        return self.json["name"]

    @property
    def product_id(self) -> str | None:
        """
        Returns:
            str: the ID of the product applied to the pot (e.g. savings)
        """
        return self.json.get("product_id")

    @property
    def round_up(self) -> bool | None:
        """
        Returns:
            bool: is the pot where all round ups go
        """
        return self.json.get("round_up")

    @property
    def round_up_multiplier(self) -> float | None:
        """
        Returns:
            float: the multiplier applied to the pot's round-ups
        """
        return self.json.get("round_up_multiplier")

    @property
    def style(self) -> str | None:
        """
        Returns:
            str: the pot background image
        """
        return self.json.get("style")

    @property
    def type(self) -> str | None:
        """
        Returns:
            str: the type of pot (e.g. flex saver)
        """
        return self.json.get("type")

    @property
    def updated_datetime(self) -> datetime | None:
        """
        Returns:
            datetime: when the pot was updated last
        """
        if "updated" not in self.json:
            return None

        return datetime.strptime(self.json["updated"], DATETIME_FORMAT)

    def __str__(self) -> str:
        return f"{self.name} | {self.id}"


class MonzoClient(OauthClient):
    """Custom client for interacting with Monzo's API"""

    ACCESS_TOKEN_ENDPOINT = "https://api.monzo.com/oauth2/token"
    BASE_URL = "https://api.monzo.com"
    CREDS_FILE_PATH = user_data_dir(file_name="monzo_api_creds.json")

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://0.0.0.0:5001/get_auth_code",
        access_token_expiry_threshold: int = 60,
        log_requests: bool = False,
        creds_cache_path: str | None = None,
    ):
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            base_url=self.BASE_URL,
            access_token_endpoint=self.ACCESS_TOKEN_ENDPOINT,
            redirect_uri=redirect_uri,
            access_token_expiry_threshold=access_token_expiry_threshold,
            log_requests=log_requests,
            creds_cache_path=creds_cache_path or self.CREDS_FILE_PATH,
        )

        self._current_account: Account | None = None

    def deposit_into_pot(
        self, pot: Pot, amount_pence: int, dedupe_id: str | None = None
    ) -> None:
        """Move money from an account owned by the currently authorised user into one
         of their pots

        Args:
            pot (Pot): the target pot
            amount_pence (int): the amount of money to deposit, in pence
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

    def list_accounts(
        self, ignore_closed: bool = True, account_type: str | None = None
    ) -> Generator[Account, None, None]:
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

    def list_pots(self, ignore_deleted: bool = True) -> Generator[Pot, None, None]:
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

    def get_pot_by_id(self, pot_id: str) -> Pot | None:
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

    def get_pot_by_name(self, pot_name: str, exact_match: bool = False) -> Pot | None:
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
            found_name = pot_name if exact_match else cleanse_string(pot.name).lower()
            if found_name.lower() == pot_name.lower():
                return pot

        return None

    @property
    def access_token_has_expired(self) -> bool:
        """Custom expiry check for Monzo client as JWT doesn't seem to include expiry
         time. Any errors/missing credentials result in a default value of True

        Returns:
            bool: expiry status of JWT
        """
        self._load_local_credentials()

        if not (access_token := self._credentials.get("access_token", False)):
            return True

        res = get(
            f"{self.BASE_URL}/ping/whoami",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        return res.json().get("authenticated", False) is False

    @property
    def current_account(self) -> Account:
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
