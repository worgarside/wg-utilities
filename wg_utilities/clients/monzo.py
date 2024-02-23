"""Custom client for interacting with Monzo's API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from logging import DEBUG, getLogger
from typing import TYPE_CHECKING, Any, ClassVar, Literal, final

from pydantic import Field, field_validator
from requests import put
from typing_extensions import TypedDict

from wg_utilities.clients.oauth_client import BaseModelWithConfig, OAuthClient
from wg_utilities.functions import DTU, cleanse_string, utcnow

if TYPE_CHECKING:
    from collections.abc import Iterable

    from wg_utilities.clients.json_api_client import StrBytIntFlt

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


@final
class AccountJson(TypedDict):
    """JSON representation of a Monzo account."""

    account_number: str | None
    balance: float
    balance_including_flexible_savings: float
    closed: bool | None
    country_code: str
    created: str
    currency: Literal["GBP"]
    description: str
    id: str
    owners: list[AccountOwner]
    payment_details: dict[str, dict[str, str]] | None
    sort_code: str | None
    spend_today: float
    total_balance: float
    type: Literal["uk_monzo_flex", "uk_retail", "uk_retail_joint"]


@final
class PotJson(TypedDict):
    """JSON representation of a pot.

    Yes, this and the `Pot` class could've been replaced by Pydantic's
    `create_model_from_typeddict`, but it doesn't play nice with mypy :(
    """

    available_for_bills: bool
    balance: float
    charity_id: str | None
    cover_image_url: str
    created: datetime  # N.B. `str` actually, just parsed as `datetime`
    currency: str
    current_account_id: str
    deleted: bool
    goal_amount: float | None
    has_virtual_cards: bool
    id: str
    is_tax_pot: bool
    isa_wrapper: str
    lock_type: Literal["until_date"] | None
    locked: bool
    locked_until: datetime | None
    name: str
    product_id: str
    round_up: bool
    round_up_multiplier: float | None
    style: str
    type: str
    updated: datetime  # N.B. `str` actually, just parsed as `datetime`


TransactionCategory = Literal[
    "bills",
    "cash",
    "charity",
    "eating_out",
    "entertainment",
    "general",
    "gifts",
    "groceries",
    "holidays",
    "income",
    "personal_care",
    "savings",
    "shopping",
    "transfers",
    "transport",
]


@final
class TransactionJson(TypedDict):
    """JSON representation of a transaction.

    Same as above RE: Pydantic's `create_model_from_typeddict`.
    """

    account_id: str
    amount: int
    amount_is_pending: bool
    atm_fees_detailed: dict[str, int | str | None] | None
    attachments: None
    can_add_to_tab: bool
    can_be_excluded_from_breakdown: bool
    can_be_made_subscription: bool
    can_match_transactions_in_categorization: bool
    can_split_the_bill: bool
    categories: dict[
        TransactionCategory,
        int,
    ]
    category: TransactionCategory
    counterparty: dict[str, str]
    created: datetime
    currency: str
    decline_reason: str | None
    dedupe_id: str
    description: str
    fees: dict[str, Any] | None
    id: str
    include_in_spending: bool
    international: bool | None
    is_load: bool
    labels: list[str] | None
    local_amount: int
    local_currency: str
    merchant: str | None
    merchant_feedback_uri: str | None
    metadata: dict[str, str]
    notes: str
    originator: bool
    parent_account_id: str
    scheme: str
    settled: str
    tab: dict[str, object] | None
    updated: datetime
    user_id: str


class Transaction(BaseModelWithConfig):
    """Pydantic representation of a transaction."""

    account_id: str
    amount: int
    amount_is_pending: bool
    atm_fees_detailed: dict[str, int | str | None] | None = None
    attachments: None = None
    can_add_to_tab: bool
    can_be_excluded_from_breakdown: bool
    can_be_made_subscription: bool
    can_match_transactions_in_categorization: bool
    can_split_the_bill: bool
    categories: dict[
        TransactionCategory,
        int,
    ]
    category: TransactionCategory
    counterparty: dict[str, str]
    created: datetime
    currency: str
    decline_reason: str | None = None
    dedupe_id: str
    description: str
    fees: dict[str, Any] | None = None
    id: str
    include_in_spending: bool
    international: bool | None = None
    is_load: bool
    labels: list[str] | None = None
    local_amount: int
    local_currency: str
    merchant: str | None
    merchant_feedback_uri: str | None = None
    metadata: dict[str, str]
    notes: str
    originator: bool
    parent_account_id: str
    scheme: str
    settled: str
    tab: dict[str, object] | None = None
    updated: datetime
    user_id: str


class BalanceVariables(BaseModelWithConfig):
    """Variables for an account's balance summary."""

    balance: int
    balance_including_flexible_savings: int
    currency: Literal["GBP"]
    local_currency: str
    local_exchange_rate: int | float | None | Literal[""]
    local_spend: list[dict[str, int | str]]
    spend_today: int
    total_balance: int


class AccountOwner(TypedDict):
    """The owner of a Monzo account."""

    preferred_first_name: str
    preferred_name: str
    user_id: str


SORT_CODE_LEN = 6


class Account(BaseModelWithConfig):
    """Class for managing individual bank accounts."""

    account_number: str
    closed: bool
    country_code: str
    created: datetime
    currency: Literal["GBP"]
    description: str
    id: str
    initial_balance: int | None = Field(None, validation_alias="balance")
    initial_balance_including_flexible_savings: int | None = Field(
        None,
        validation_alias="balance_including_flexible_savings",
    )
    initial_spend_today: int | None = Field(None, validation_alias="spend_today")
    initial_total_balance: int | None = Field(None, validation_alias="total_balance")
    owners: list[AccountOwner]
    payment_details: dict[str, dict[str, str]] | None = None
    sort_code: str = Field(min_length=6, max_length=6)
    type: Literal["uk_monzo_flex", "uk_retail", "uk_retail_joint"]

    monzo_client: MonzoClient = Field(exclude=True)
    balance_update_threshold: int = Field(15, exclude=True)
    last_balance_update: datetime = Field(datetime(1970, 1, 1), exclude=True)
    _balance_variables: BalanceVariables

    @field_validator("sort_code", mode="before")
    @classmethod
    def validate_sort_code(cls, sort_code: str | int) -> str:
        """Ensure that the sort code is a 6-digit integer.

        Represented as a string so leading zeroes aren't lost.
        """

        if isinstance(sort_code, int):
            sort_code = str(sort_code)

        if len(sort_code) != SORT_CODE_LEN:
            sort_code.ljust(SORT_CODE_LEN, "0")

        if not sort_code.isdigit():
            raise ValueError("Sort code must be a 6-digit integer")

        return sort_code

    @classmethod
    def from_json_response(
        cls,
        value: AccountJson,
        monzo_client: MonzoClient,
    ) -> Account:
        """Create an account from a JSON response."""

        value_data: dict[str, Any] = {
            "monzo_client": monzo_client,
            **value,
        }

        return cls.model_validate(value_data)

    def list_transactions(
        self,
        from_datetime: datetime | None = None,
        to_datetime: datetime | None = None,
        limit: int = 100,
    ) -> list[Transaction]:
        """List transactions for the account.

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

        from_datetime = (
            from_datetime or (datetime.now(UTC) - timedelta(days=89))
        ).replace(microsecond=0, tzinfo=None)
        to_datetime = (to_datetime or datetime.now(UTC)).replace(
            microsecond=0,
            tzinfo=None,
        )

        return [
            Transaction(**item)
            for item in self.monzo_client.get_json_response(
                "/transactions",
                params={
                    "account_id": self.id,
                    "since": from_datetime.isoformat() + "Z",
                    "before": to_datetime.isoformat() + "Z",
                    "limit": limit,
                },
            )["transactions"]
        ]

    def update_balance_variables(self) -> None:
        """Update the balance-related instance attributes.

        Latest values from the API are used. This is called automatically when
        a balance property is accessed and the last update was more than
        `balance_update_threshold` minutes ago, or if it is None. Can also be called
        manually if required.
        """

        if not hasattr(self, "_balance_variables") or self.last_balance_update <= (
            datetime.now(UTC) - timedelta(minutes=self.balance_update_threshold)
        ):
            LOGGER.debug("Balance variable update threshold crossed, getting new values")

            self._balance_variables = BalanceVariables.model_validate(
                self.monzo_client.get_json_response(f"/balance?account_id={self.id}"),
            )

            self.last_balance_update = datetime.now(UTC)

    @property
    def balance(self) -> int | None:
        """Current balance of the account, in pence.

        Returns:
            float: the currently available balance of the account
        """
        return self.balance_variables.balance

    @property
    def balance_variables(self) -> BalanceVariables:
        """The balance variables for the account.

        Returns:
            BalanceVariables: the balance variables
        """
        self.update_balance_variables()

        return self._balance_variables

    @property
    def balance_including_flexible_savings(self) -> int | None:
        """Balance including flexible savings, in pence.

        Returns:
            float: the currently available balance of the account, including flexible
                savings pots
        """
        return self.balance_variables.balance_including_flexible_savings

    @property
    def spend_today(self) -> int | None:
        """Amount spent today, in pence.

        Returns:
            int: the amount spent from this account today (considered from approx
                4am onwards)
        """
        return self.balance_variables.spend_today

    @property
    def total_balance(self) -> int | None:
        """Total balance of the account, in pence.

        Returns:
            str: the sum of the currently available balance of the account and the
                combined total of all the user's pots
        """
        return self.balance_variables.total_balance

    def __eq__(self, other: object) -> bool:
        """Check if two accounts are equal."""
        if not isinstance(other, Account):
            return NotImplemented

        return self.id == other.id

    def __repr__(self) -> str:
        """Representation of the account."""
        return f"<Account {self.id}>"


class Pot(BaseModelWithConfig):
    """Read-only class for Monzo pots."""

    available_for_bills: bool
    balance: float
    charity_id: str | None = None
    cover_image_url: str
    created: datetime
    currency: str
    current_account_id: str
    deleted: bool
    goal_amount: float | None = None
    has_virtual_cards: bool
    id: str
    is_tax_pot: bool
    isa_wrapper: str
    lock_type: Literal["until_date"] | None = None
    locked: bool
    locked_until: datetime | None = None
    name: str
    product_id: str
    round_up: bool
    round_up_multiplier: float | None = None
    style: str
    type: str
    updated: datetime


class MonzoGJR(TypedDict):
    """The response type for `MonzoClient.get_json_response`."""

    accounts: list[AccountJson]
    pots: list[PotJson]
    transactions: list[TransactionJson]


class MonzoClient(OAuthClient[MonzoGJR]):
    """Custom client for interacting with Monzo's API."""

    ACCESS_TOKEN_ENDPOINT = "https://api.monzo.com/oauth2/token"  # noqa: S105
    AUTH_LINK_BASE = "https://auth.monzo.com"
    BASE_URL = "https://api.monzo.com"

    DEFAULT_PARAMS: ClassVar[
        dict[StrBytIntFlt, StrBytIntFlt | Iterable[StrBytIntFlt] | None]
    ] = {}

    _current_account: Account

    def deposit_into_pot(
        self,
        pot: Pot,
        amount_pence: int,
        dedupe_id: str | None = None,
    ) -> None:
        """Move money from the user's account into one of their pots.

        Args:
            pot (Pot): the target pot
            amount_pence (int): the amount of money to deposit, in pence
            dedupe_id (str): unique string used to de-duplicate deposits. Will be
                created if not provided
        """

        dedupe_id = dedupe_id or "|".join(
            [pot.id, str(amount_pence), str(utcnow(DTU.SECOND))],
        )

        res = put(
            f"{self.BASE_URL}/pots/{pot.id}/deposit",
            headers=self.request_headers,
            data={
                "source_account_id": self.current_account.id,
                "amount": amount_pence,
                "dedupe_id": dedupe_id,
            },
            timeout=10,
        )
        res.raise_for_status()

    def list_accounts(
        self,
        *,
        include_closed: bool = False,
        account_type: str | None = None,
    ) -> list[Account]:
        """Get a list of the user's accounts.

        Args:
            include_closed (bool): whether to include closed accounts in the response
            account_type (str): the type of account(s) to find; submitted as param in
                request

        Returns:
            list: Account instances, containing all related info
        """

        res = self.get_json_response(
            "/accounts",
            params={"account_type": account_type} if account_type else None,
        )

        return [
            Account.from_json_response(account, self)
            for account in res.get("accounts", [])
            if not account.get("closed", True) or include_closed
        ]

    def list_pots(self, *, include_deleted: bool = False) -> list[Pot]:
        """Get a list of the user's pots.

        Args:
            include_deleted (bool): whether to include deleted pots in the response

        Returns:
            list: Pot instances, containing all related info
        """

        res = self.get_json_response(
            "/pots",
            params={"current_account_id": self.current_account.id},
        )

        return [
            Pot(**pot)
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

    def get_pot_by_name(
        self,
        pot_name: str,
        *,
        exact_match: bool = False,
        include_deleted: bool = False,
    ) -> Pot | None:
        """Get a pot from its name.

        Args:
            pot_name (str): the name of the pot to find
            exact_match (bool): if False, all pot names will be cleansed before
                evaluation
            include_deleted (bool): whether to include deleted pots in the response

        Returns:
            Pot: the Pot instance
        """
        if not exact_match:
            pot_name = cleanse_string(pot_name)

        for pot in self.list_pots(include_deleted=include_deleted):
            found_name = pot.name if exact_match else cleanse_string(pot.name)
            if found_name.lower() == pot_name.lower():
                return pot

        return None

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

    @property
    def request_headers(self) -> dict[str, str]:
        """Header to be used in requests to the API.

        Returns:
            dict: auth headers for HTTP requests
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
        }


Account.model_rebuild()
