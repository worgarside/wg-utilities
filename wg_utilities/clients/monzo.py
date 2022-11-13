"""Custom client for interacting with Monzo's API."""
from __future__ import annotations

from datetime import datetime, timedelta
from logging import DEBUG, getLogger
from pathlib import Path
from random import choice
from string import ascii_letters
from typing import Any, Literal, TypedDict
from webbrowser import open as open_browser

from requests import get, put

from wg_utilities.clients.oauth_client import OAuthClient, OAuthCredentialsInfo
from wg_utilities.functions import DTU, cleanse_string, utcnow

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class _MonzoAccountInfo(TypedDict):
    account_number: str
    balance: float
    balance_including_flexible_savings: float
    closed: bool | None
    created: str
    description: str
    id: str
    sort_code: str
    spend_today: float
    total_balance: float


class _MonzoPotInfo(TypedDict):
    available_for_bills: bool
    balance: float
    charity_id: str | None
    cover_image_url: str
    created: str
    currency: str
    current_account_id: str
    deleted: bool
    goal_amount: float | None
    has_virtual_cards: bool
    id: str
    is_tax_pot: bool
    isa_wrapper: str
    locked: bool
    name: str
    product_id: str
    round_up: bool
    round_up_multiplier: float | None
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
    """Class for managing individual bank accounts."""

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
        # TODO overload(?) this too for typing stuff
        """Gets a value for a balance-specific property.

         Values are updated as necessary (i.e. if they don't already exist). This also
         has a check to see if property is relevant for the given entity type and if
         not it just returns None.

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
            LOGGER.debug(
                "Balance variable update threshold crossed, getting new values"
            )
            self.update_balance_variables()

        return self._balance_variables[var_name]

    def list_transactions(
        self,
        from_datetime: datetime | None = None,
        to_datetime: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Lists transactions for the account.

        Args:
            from_datetime (datetime, optional): the start of the time period to list
                transactions for. Defaults to None.
            to_datetime (datetime, optional): the end of the time period to list
                transactions for. Defaults to None.
            limit (int, optional): the maximum number of transactions to return.
                Defaults to 100.

        Returns:
            list[dict[str, object]]: the list of transactions
        """

        from_datetime = from_datetime or datetime.utcnow() - timedelta(days=89)
        to_datetime = to_datetime or datetime.utcnow()

        return self._monzo_client.get_json_response(
            "/transactions",
            params={
                "account_id": self.id,
                "since": from_datetime.isoformat() + "Z",
                "before": to_datetime.isoformat() + "Z",
                "limit": limit,
            },
        ).get("transactions", [])

    def update_balance_variables(self) -> None:
        """Updates the balance-related instance attributes.

        Latest values from the API are used. This is called automatically when
        a balance property is accessed and the last update was more than
        `balance_update_threshold` minutes ago, or if it is None. Can also be called
        manually if required.
        """
        # pylint: disable=line-too-long
        self._balance_variables = self._monzo_client.get_json_response(  # type: ignore[assignment]
            "/balance", params={"account_id": self.id}
        )

        self.last_balance_update = datetime.utcnow()

    @property
    def account_number(self) -> str | None:
        """Account number.

        Returns:
            str: the account's account number
        """
        return self.json.get("account_number")

    @property
    def balance(self) -> int | None:
        """Current balance of the account, in pence.

        Returns:
            float: the currently available balance of the account
        """
        return self._get_balance_property("balance")  # type: ignore[return-value]

    @property
    def balance_including_flexible_savings(self) -> int | None:
        """Balance including flexible savings, in pence.

        Returns:
            float: the currently available balance of the account, including flexible
             savings pots
        """
        return self._get_balance_property(
            "balance_including_flexible_savings"
        )  # type: ignore[return-value]

    @property
    def closed(self) -> bool:
        """Whether the account is closed.

        Returns:
            bool: the description of the account
        """
        return self.json.get("closed") or False

    @property
    def created_datetime(self) -> datetime | None:
        """When the account was created.

        Returns:
            datetime: when the account was created
        """
        if "created" not in self.json:
            return None

        return datetime.strptime(self.json["created"], DATETIME_FORMAT)

    @property
    def description(self) -> str | None:
        """Description of the account.

        Returns:
            str: the description of the account
        """
        return self.json.get("description")

    @property
    def id(self) -> str | None:
        """Account ID.

        Returns:
            str: the account's UUID
        """
        return self.json["id"]

    @property
    def sort_code(self) -> str | None:
        """Sort code.

        Returns:
            str: the account's sort code
        """
        return self.json.get("sort_code")

    @property
    def spend_today(self) -> int | None:
        """Amount spent today, in pence.

        Returns:
            int: the amount spent from this account today (considered from approx
             4am onwards)
        """
        return self._get_balance_property("spend_today")  # type: ignore[return-value]

    @property
    def total_balance(self) -> int | None:
        """Total balance of the account, in pence.

        Returns:
            str: the sum of the currently available balance of the account and the
             combined total of all the user’s pots
        """
        return self._get_balance_property("total_balance")  # type: ignore[return-value]

    def __eq__(self, other: object) -> bool:
        """Checks if two accounts are equal."""
        if not isinstance(other, Account):
            return NotImplemented

        return self.id == other.id

    def __repr__(self) -> str:
        """Representation of the account."""
        return f"<Account {self.id}>"


class Pot:
    """Read-only class for Monzo pots."""

    # TODO change this to Pydantic model

    def __init__(self, json: _MonzoPotInfo):
        self.json = json

    @property
    def available_for_bills(self) -> bool | None:
        """Whether the pot is available for bills.

        Returns:
            bool: if the pot can be used directly for bills
        """
        return self.json.get("available_for_bills")

    @property
    def balance(self) -> float:
        """Balance of the pot, in pence.

        Returns:
            float: the pot's balance in GBP
        """
        return float(self.json.get("balance", 0))

    @property
    def charity_id(self) -> str | None:
        """ID of the charity this Pot is for?

        Returns:
            str: not sure!
        """
        return self.json.get("charity_id")

    @property
    def cover_image_url(self) -> str | None:
        """Cover image URL for the pot.

        Returns:
            str: URL for the cover image
        """
        return self.json.get("cover_image_url")

    @property
    def created_datetime(self) -> datetime | None:
        """When the pot was created.

        Returns:
            datetime: when the pot was created
        """
        if "created" not in self.json:
            return None

        return datetime.strptime(self.json["created"], DATETIME_FORMAT)

    @property
    def currency(self) -> str | None:
        """Pot currency.

        Returns:
            str: the currency of the pot
        """
        return self.json.get("currency")

    @property
    def current_account_id(self) -> str | None:
        """UUID of the account the pot is linked to.

        Returns:
            str: the UUID of the parent account
        """
        return self.json.get("current_account_id")

    @property
    def deleted(self) -> bool | None:
        """Has the pot been deleted?

        Returns:
            bool: has the pot been deleted
        """
        return self.json.get("deleted")

    @property
    def goal_amount(self) -> float | None:
        """Goal amount of the pot, in pence.

        Returns:
            float: the user-set goal amount for the pot
        """
        if not (goal_amount := self.json.get("goal_amount")):
            return None

        return goal_amount

    @property
    def has_virtual_cards(self) -> bool | None:
        """Any pot with virtual cards will have this set to True.

        Returns:
            bool: if the pot has virtual cards attached
        """
        return self.json.get("has_virtual_cards")

    @property
    def id(self) -> str:
        """UUID of the pot.

        Returns:
            str: the pot's UUID
        """
        return self.json["id"]

    @property
    def is_tax_pot(self) -> bool | None:
        """Is this a tax pot?

        Returns:
            bool: is the pot taxed? I'm not sure
        """
        return self.json.get("is_tax_pot")

    @property
    def isa_wrapper(self) -> str | None:
        """Whether the pot is ISA-wrapped.

        Returns:
            str: is the pot ISA-wrapped?
        """
        return self.json.get("isa_wrapper")

    @property
    def locked(self) -> bool | None:
        """Boolean indicating whether the pot is locked.

        Returns:
            bool: is the pot locked
        """
        return self.json.get("locked")

    @property
    def name(self) -> str:
        """Name of the pot.

        Returns:
            str: the name of the pot
        """
        return self.json["name"]

    @property
    def product_id(self) -> str | None:
        """Product ID of the pot.

        Returns:
            str: the ID of the product applied to the pot (e.g. savings)
        """
        return self.json.get("product_id")

    @property
    def round_up(self) -> bool | None:
        """Target pot for round-ups.

        Returns:
            bool: is the pot where all round ups go
        """
        return self.json.get("round_up")

    @property
    def round_up_multiplier(self) -> float | None:
        """Multiplier for round ups.

        Returns:
            float: the multiplier applied to the pot's round-ups
        """
        return self.json.get("round_up_multiplier")

    @property
    def style(self) -> str | None:
        """Background style of the pot.

        Returns:
            str: the pot background image
        """
        return self.json.get("style")

    @property
    def type(self) -> str | None:
        """The type of pot.

        Returns:
            str: the type of pot (e.g. flex saver)
        """
        return self.json.get("type")

    @property
    def updated_datetime(self) -> datetime | None:
        """Datetime when the pot was last updated.

        Returns:
            datetime: when the pot was updated last
        """
        if "updated" not in self.json:
            return None

        return datetime.strptime(self.json["updated"], DATETIME_FORMAT)

    def __str__(self) -> str:
        return f"{self.name} | {self.id}"

    def __eq__(self, other: object) -> bool:
        """Checks if two accounts are equal."""
        if not isinstance(other, Pot):
            return NotImplemented

        return self.id == other.id

    def __repr__(self) -> str:
        """Representation of the account."""
        return f"<Pot {self.id}>"


class MonzoClient(OAuthClient):
    """Custom client for interacting with Monzo's API."""

    ACCESS_TOKEN_ENDPOINT = "https://api.monzo.com/oauth2/token"
    BASE_URL = "https://api.monzo.com"

    DEFAULT_PARAMS: dict[str, object] = {}

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://0.0.0.0:5001/get_auth_code",
        access_token_expiry_threshold: int = 60,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
    ):
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            base_url=self.BASE_URL,
            access_token_endpoint=self.ACCESS_TOKEN_ENDPOINT,
            redirect_uri=redirect_uri,
            access_token_expiry_threshold=access_token_expiry_threshold,
            log_requests=log_requests,
            creds_cache_path=creds_cache_path,
        )

        self._current_account: Account

    def get_items_from_url(self, *_: Any, **__: Any) -> None:
        """Not implemented."""
        raise NotImplementedError("This method is not implemented for Monzo.")

    def deposit_into_pot(
        self, pot: Pot, amount_pence: int, dedupe_id: str | None = None
    ) -> None:
        """Move money from the user's account into one of their pots.

        Args:
            pot (Pot): the target pot
            amount_pence (int): the amount of money to deposit, in pence
            dedupe_id (str): unique string used to de-duplicate deposits. Will be
             created if not provided
        """

        dedupe_id = dedupe_id or "|".join(
            [pot.id, str(amount_pence), str(utcnow(DTU.SECOND))]
        )

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
        self, *, include_closed: bool = False, account_type: str | None = None
    ) -> list[Account]:
        """Gets a list of the user's accounts.

        Args:
            include_closed (bool): whether to include closed accounts in the response
            account_type (str): the type of account(s) to find; submitted as param in
             request

        Returns:
            list: Account instances, containing all related info
        """

        res = self.get_json_response(
            "/accounts", params={"account_type": account_type} if account_type else None
        )

        return [
            Account(account, self)
            for account in res.get("accounts", [])
            if not account.get("closed", True) or include_closed
        ]

    def list_pots(self, *, include_deleted: bool = False) -> list[Pot]:
        """Gets a list of the user's pots.

        Args:
            include_deleted (bool): whether to include deleted pots in the response

        Returns:
            list: Pot instances, containing all related info
        """

        res = self.get_json_response(
            "/pots", params={"current_account_id": self.current_account.id}
        )

        return [
            Pot(pot)
            for pot in res.get("pots", [])
            if not pot.get("deleted", True) or include_deleted
        ]

    def get_pot_by_id(self, pot_id: str) -> Pot | None:
        """Get a pot from its ID.

        Args:
            pot_id (str): the ID of the pot to find

        Returns:
            Pot: the Pot instance
        """
        for pot in self.list_pots(include_deleted=True):
            if pot.id == pot_id:
                return pot

        return None

    def get_pot_by_name(self, pot_name: str, exact_match: bool = False) -> Pot | None:
        """Get a pot from its name.

        Args:
            pot_name (str): the name of the pot to find
            exact_match (bool): if False, all pot names will be cleansed before
             evaluation

        Returns:
            Pot: the Pot instance
        """
        if not exact_match:
            pot_name = cleanse_string(pot_name)

        for pot in self.list_pots(include_deleted=True):
            found_name = pot.name if exact_match else cleanse_string(pot.name)
            if found_name.lower() == pot_name.lower():
                return pot

        return None

    @property
    def access_token_has_expired(self) -> bool:
        """Custom expiry check for Monzo client.

         The JWT doesn't seem to include expiry time. Any errors/missing credentials
         result in a default value of True

        Returns:
            bool: expiry status of JWT
        """
        if not hasattr(self, "_credentials"):
            self._load_local_credentials()

        if not (access_token := self._credentials.get("access_token", False)):
            return True

        res = get(
            f"{self.BASE_URL}/ping/whoami",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        return res.json().get("authenticated", False) is False

    @property
    def credentials(self) -> OAuthCredentialsInfo:
        """Gets creds as necessary (including first time setup) and authenticates them.

        Returns:
            dict: the credentials for the chosen bank

        Raises:
            ValueError: if the state token returned from the request doesn't match the
             expected value
        """
        if not hasattr(self, "_credentials"):
            self._load_local_credentials()

        if not self._credentials:
            self.logger.info("Performing first time login")

            state_token = "".join(choice(ascii_letters) for _ in range(32))

            # pylint: disable=line-too-long
            auth_link = f"https://auth.monzo.com/?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&state={state_token}"  # noqa: E501
            self.logger.debug("Opening %s", auth_link)
            open_browser(auth_link)

            request_args = self.temp_auth_server.wait_for_request(
                "/get_auth_code", kill_on_request=True
            )

            if state_token != request_args.get("state"):
                raise ValueError(
                    "State token received in request doesn't match expected value: "
                    f"{request_args.get('state')} != {state_token}"
                )

            self.exchange_auth_code(request_args["code"])

        if self.access_token_has_expired:
            self.refresh_access_token()

        return self._credentials

    @credentials.setter
    def credentials(self, value: OAuthCredentialsInfo) -> None:
        """Setter for credentials.

        Args:
            value (dict): the new values to use for the creds for this project
        """
        self._set_credentials(value)

    @property
    def current_account(self) -> Account:
        """Get the main account for the Monzo user.

        We assume there'll only be one main account per user.

        Returns:
            Account: the user's main account, instantiated
        """
        if not hasattr(self, "_current_account"):
            self._current_account = self.list_accounts(account_type="uk_retail")[0]

        return self._current_account
