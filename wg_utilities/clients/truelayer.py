# pylint: disable=too-few-public-methods
"""Custom client for interacting with TrueLayer's API."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from enum import Enum, auto
from logging import DEBUG, getLogger
from os.path import sep
from pathlib import Path
from typing import Any, ClassVar, Literal, TypeAlias, TypedDict, TypeVar

from pydantic import Field, validator
from requests import HTTPError
from strenum import StrEnum  # type: ignore[import]

from wg_utilities.clients.oauth_client import (
    BaseModelWithConfig,
    GenericModelWithConfig,
    OAuthClient,
    StrBytIntFlt,
)
from wg_utilities.functions import user_data_dir
from wg_utilities.functions.file_management import force_mkdir

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


class AccountType(StrEnum):  # type: ignore[misc]
    """Possible TrueLayer account types."""

    TRANSACTION = auto()
    SAVINGS = auto()
    BUSINESS_TRANSACTION = auto()
    BUSINESS_SAVINGS = auto()


class Bank(Enum):
    """Enum for all banks supported by TrueLayer."""

    ALLIED_IRISH_BANK_CORPORATE = "Allied Irish Bank Corporate"
    AMEX = "Amex"
    BANK_OF_SCOTLAND = "Bank of Scotland"
    BANK_OF_SCOTLAND_BUSINESS = "Bank of Scotland Business"
    BARCLAYCARD = "Barclaycard"
    BARCLAYS = "Barclays"
    BARCLAYS_BUSINESS = "Barclays Business"
    CAPITAL_ONE = "Capital One"
    CHELSEA_BUILDING_SOCIETY = "Chelsea Building Society"
    DANSKE_BANK = "Danske Bank"
    DANSKE_BANK_BUSINESS = "Danske Bank Business"
    FIRST_DIRECT = "First Direct"
    HALIFAX = "Halifax"
    HSBC = "HSBC"
    HSBC_BUSINESS = "HSBC Business"
    LLOYDS = "Lloyds"
    LLOYDS_BUSINESS = "Lloyds Business"
    LLOYDS_COMMERCIAL = "Lloyds Commercial"
    M_S_BANK = "M&S Bank"
    MBNA = "MBNA"
    MONZO = "Monzo"
    NATIONWIDE = "Nationwide"
    NATWEST = "NatWest"
    NATWEST_BUSINESS = "NatWest Business"
    REVOLUT = "Revolut"
    ROYAL_BANK_OF_SCOTLAND = "Royal Bank of Scotland"
    ROYAL_BANK_OF_SCOTLAND_BUSINESS = "Royal Bank of Scotland Business"
    SANTANDER = "Santander"
    STARLING = "Starling"
    STARLING_JOINT = "Starling Joint"
    TESCO_BANK = "Tesco Bank"
    TIDE = "Tide"
    TSB = "TSB"
    ULSTER_BANK = "Ulster Bank"
    ULSTER_BUSINESS = "Ulster Business"
    VIRGIN_MONEY = "Virgin Money"
    WISE = "Wise"
    YORKSHIRE_BUILDING_SOCIETY = "Yorkshire Building Society"


class TransactionCategory(Enum):
    """Enum for TrueLayer transaction types.

    __init__ method is overridden to allow setting a description as well as the main
     value.
    """

    ATM = (
        "ATM",
        "Deposit or withdrawal of funds using an ATM (Automated Teller Machine)",
    )
    BILL_PAYMENT = "Bill Payment", "Payment of a bill"
    CASH = (
        "Cash",
        "Cash deposited over the branch counter or using Cash and Deposit Machines",
    )
    CASHBACK = (
        "Cashback",
        "An option retailers offer to withdraw cash while making a debit card purchase",
    )
    CHEQUE = (
        "Cheque",
        "A document ordering the payment of money from a bank account to another person"
        " or organisation",
    )
    CORRECTION = "Correction", "Correction of a transaction error"
    CREDIT = "Credit", "Funds added to your account"
    DIRECT_DEBIT = (
        "Direct Debit",
        "An automatic withdrawal of funds initiated by a third party at regular"
        " intervals",
    )
    DIVIDEND = "Dividend", "A payment to your account from shares you hold"
    DEBIT = "Debit", "Funds taken out from your account, uncategorised by the bank"
    FEE_CHARGE = "Fee Charge", "Fees or charges in relation to a transaction"
    INTEREST = "Interest", "Credit or debit associated with interest earned or incurred"
    OTHER = "Other", "Miscellaneous credit or debit"
    PURCHASE = "Purchase", "A payment made with your debit or credit card"
    STANDING_ORDER = (
        "Standing Order",
        "A payment instructed by the account-holder to a third party at regular"
        " intervals",
    )
    TRANSFER = "Transfer", "Transfer of money between accounts"
    UNKNOWN = "Unknown", "No classification of transaction category known"

    def __init__(self, value: tuple[str, str], description: tuple[str, str]):
        self._value_ = value
        self.description = description


class _AccountNumber(BaseModelWithConfig):
    iban: str | None
    number: str | None
    sort_code: str | None
    swift_bic: str


class _TrueLayerBaseEntityJson(TypedDict):
    account_id: str
    currency: str
    display_name: str
    provider: _TrueLayerEntityProvider
    update_timestamp: str


class AccountJson(_TrueLayerBaseEntityJson):
    """JSON representation of a TrueLayer Account."""

    account_number: _AccountNumber
    account_type: AccountType


class CardJson(_TrueLayerBaseEntityJson):
    """JSON representation of a Card."""

    card_network: str
    card_type: str
    partial_card_number: str
    name_on_card: str
    valid_from: date | None
    valid_to: date | None


class BalanceVariables(BaseModelWithConfig):
    """Variables for an account's balance summary."""

    available_balance: int
    current_balance: int
    overdraft: int
    credit_limit: int
    last_statement_balance: int
    last_statement_date: date
    payment_due: int
    payment_due_date: date


class _TrueLayerEntityProvider(BaseModelWithConfig):
    display_name: str
    logo_uri: str
    id: str = Field(alias="provider_id")


TrueLayerEntityJson: TypeAlias = AccountJson | CardJson

FJR = TypeVar("FJR", bound="TrueLayerEntity")


class TrueLayerEntity(GenericModelWithConfig):
    """Parent class for all TrueLayer entities (accounts, cards, etc.)."""

    BALANCE_FIELDS: ClassVar[Iterable[str]] = ()

    id: str = Field(alias="account_id")
    currency: str
    display_name: str
    provider: _TrueLayerEntityProvider
    update_timestamp: str

    _available_balance: float
    _current_balance: float
    _overdraft: float
    _credit_limit: float
    _last_statement_balance: float
    _last_statement_date: date
    _payment_due: float
    _payment_due_date: date

    truelayer_client: TrueLayerClient = Field(exclude=True)
    balance_update_threshold: timedelta = Field(timedelta(minutes=15), exclude=True)
    last_balance_update: datetime = Field(datetime(1970, 1, 1), exclude=True)
    _balance_variables: BalanceVariables

    @classmethod
    def from_json_response(
        cls: type[FJR], value: TrueLayerEntityJson, *, truelayer_client: TrueLayerClient
    ) -> FJR:
        """Create an account from a JSON response."""

        value_data: dict[str, Any] = {
            "truelayer_client": truelayer_client,
            **value,
        }

        instance = cls.parse_obj(value_data)

        instance._validate()  # pylint: disable=protected-access

        return instance

    def get_transactions(
        self,
        from_datetime: datetime | None = None,
        to_datetime: datetime | None = None,
    ) -> list[Transaction]:
        """Get transactions for this entity.

        Polls the TL API to get all transactions under the given entity. If
        only one datetime parameter is provided, then the other is given a default
        value which maximises the range of results returned

        Args:
            from_datetime (datetime): lower range of transaction date range query
            to_datetime (datetime): upper range of transaction date range query

        Returns:
            list[Transaction]: one instance per tx, including all metadata etc.
        """

        if from_datetime or to_datetime:
            from_datetime = from_datetime or datetime.utcnow() - timedelta(days=90)
            to_datetime = to_datetime or datetime.utcnow()

            params: dict[
                StrBytIntFlt,
                StrBytIntFlt | Iterable[StrBytIntFlt] | None,
            ] | None = {
                "from": from_datetime.isoformat(),
                "to": to_datetime.isoformat(),
            }
        else:
            params = None

        return [
            Transaction.parse_obj(result)
            for result in self.truelayer_client.get_json_response(
                f"/data/v1/{self.__class__.__name__.lower()}s/{self.id}/transactions",
                params=params,
            ).get("results", [])
        ]

    def update_balance_values(self) -> None:
        """Update the balance-related instance attributes.

        Uses the latest values from the API. This is called automatically when
        the balance-related attributes are accessed (if the attribute is None or
        was updated more than `self.balance_update_threshold`minutes ago), but
        can also be called manually.
        """

        results = self.truelayer_client.get_json_response(
            f"/data/v1/{self.__class__.__name__.lower()}s/{self.id}/balance"
        ).get("results", [])

        if len(results) != 1:
            raise ValueError(
                "Unexpected number of results when getting balance info:"
                f" {len(results)}",
            )

        balance_result = results[0]

        for k, v in balance_result.items():
            if k in (
                "available",
                "current",
            ):
                attr_name = f"_{k}_balance"
            elif k.endswith("_date"):
                attr_name = f"_{k}"
                if isinstance(v, str):
                    v = datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").date()
            else:
                attr_name = f"_{k}"

            if attr_name.lstrip("_") not in self.BALANCE_FIELDS:
                LOGGER.info("Skipping %s as it's not relevant for this entity type", k)
                continue

            LOGGER.info("Updating %s with value %s", attr_name, v)
            self._set_private_attr(attr_name, v)

        self.last_balance_update = datetime.utcnow()

    def _get_balance_property(
        self,
        prop_name: Literal[
            "available_balance",
            "current_balance",
            "overdraft",
            "credit_limit",
            "last_statement_balance",
            "last_statement_date",
            "payment_due",
            "payment_due_date",
        ],
    ) -> str | float | int | None:
        """Get a value for a balance-specific property.

        Updates the values if necessary (i.e. if they don't already exist). This also
        has a check to see if property is relevant for the given entity type and if not
        it just returns None.

        Args:
            prop_name (str): the name of the property

        Returns:
            str: the value of the balance property
        """

        if prop_name not in self.BALANCE_FIELDS:
            return None

        if (
            not hasattr(self, f"_{prop_name}")
            or getattr(self, f"_{prop_name}") is None
            or self.last_balance_update
            <= (datetime.utcnow() - self.balance_update_threshold)
        ):
            self.update_balance_values()

        return getattr(self, f"_{prop_name}", None)

    @property
    def available_balance(self) -> str | float | int | None:
        """Available balance for the entity.

        Returns:
            float: the amount of money available to the bank account holder
        """
        return self._get_balance_property("available_balance")

    @property
    def current_balance(self) -> str | float | int | None:
        """Current balance of the account.

        Returns:
            float: the total amount of money in the account, including pending
             transactions
        """
        return self._get_balance_property("current_balance")

    @property
    def overdraft(self) -> str | float | int | None:
        """Overdraft limit for the account.

        Returns:
            float: the overdraft limit of the account
        """
        return self._get_balance_property("overdraft")

    @property
    def credit_limit(self) -> str | float | int | None:
        """Credit limit of the account.

        Returns:
            float: the credit limit available to the customer
        """
        return self._get_balance_property("credit_limit")

    @property
    def last_statement_balance(self) -> str | float | int | None:
        """Balance of the account at the last statement date.

        Returns:
            float: the balance on the last statement
        """
        return self._get_balance_property("last_statement_balance")

    @property
    def last_statement_date(self) -> str | float | int | None:
        """Date of the last statement.

        Returns:
            date: the date the last statement was issued on
        """
        return self._get_balance_property("last_statement_date")

    @property
    def payment_due(self) -> str | float | int | None:
        """Amount due on the next statement.

        Returns:
            float: the amount of any due payment
        """
        return self._get_balance_property("payment_due")

    @property
    def payment_due_date(self) -> str | float | int | None:
        """Date of the next statement.

        Returns:
            date: the date on which the next payment is due
        """
        return self._get_balance_property("payment_due_date")

    def __str__(self) -> str:
        """Return a string representation of the entity."""
        return f"{self.display_name} | {self.provider.display_name}"


class Transaction(BaseModelWithConfig):
    """Class for individual transactions for data manipulation etc."""

    amount: float
    currency: str
    description: str
    id: str = Field(alias="transaction_id")
    merchant_name: str | None
    meta: dict[str, str]
    normalised_provider_transaction_id: str | None
    provider_transaction_id: str | None
    running_balance: dict[str, str | float] | None
    timestamp: datetime
    transaction_category: TransactionCategory
    transaction_classification: list[str]
    transaction_type: str

    @validator("transaction_category", pre=True)
    def validate_transaction_category(  # pylint: disable=no-self-argument
        cls, v: str  # noqa: N805
    ) -> TransactionCategory:
        """Validate the transaction category.

        The default Enum assignment doesn't work for some reason, so we have to do it
        here.

        This also helps to provide a meaningful error message if the category is
        invalid; Pydantic's doesn't include the invalid value unfortunately.
        """
        if v not in TransactionCategory.__members__:  # pragma: no cover
            raise ValueError(f"Invalid transaction category: {v}")

        return TransactionCategory[v]

    def __str__(self) -> str:
        """Return a string representation of the transaction."""
        return f"{self.description} | {self.amount} | {self.merchant_name}"


class Account(TrueLayerEntity):
    """Class for managing individual bank accounts."""

    BALANCE_FIELDS: ClassVar[Iterable[str]] = (
        "available_balance",
        "current_balance",
        "overdraft",
    )
    account_number: _AccountNumber
    account_type: AccountType

    @validator("account_type", pre=True)
    def validate_account_type(  # pylint: disable=no-self-argument
        cls, value: str  # noqa: N805
    ) -> AccountType:
        """Validate `account_type` and parse it into an `AccountType` instance."""
        if isinstance(value, AccountType):
            return value

        if value not in AccountType.__members__:  # pragma: no cover
            raise ValueError(f"Invalid account type: `{value}`")

        return AccountType[value.upper()]  # type: ignore[no-any-return,misc]


class Card(TrueLayerEntity):
    """Class for managing individual cards."""

    BALANCE_FIELDS: ClassVar[Iterable[str]] = (
        "available_balance",
        "current_balance",
        "credit_limit",
        "last_statement_balance",
        "last_statement_date",
        "payment_due",
        "payment_due_date",
    )

    card_network: str
    card_type: str
    partial_card_number: str
    name_on_card: str
    valid_from: date | None
    valid_to: date | None


AccountOrCard = TypeVar("AccountOrCard", Account, Card)


class TrueLayerClient(OAuthClient[dict[Literal["results"], list[TrueLayerEntityJson]]]):
    """Custom client for interacting with TrueLayer's APIs."""

    AUTH_LINK_BASE = "https://auth.truelayer.com/"
    ACCESS_TOKEN_ENDPOINT = "https://auth.truelayer.com/connect/token"
    BASE_URL = "https://api.truelayer.com"

    DEFAULT_SCOPES = [
        "info",
        "accounts",
        "balance",
        "cards",
        "transactions",
        "direct_debits",
        "standing_orders",
        "offline_access",
    ]

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        log_requests: bool = False,
        creds_cache_path: Path | None = None,
        scopes: list[str] | None = None,
        oauth_login_redirect_host: str = "localhost",
        oauth_redirect_uri_override: str | None = None,
        headless_auth_link_callback: Callable[[str], None] | None = None,
        use_existing_credentials_only: bool = False,
        bank: Bank,
    ):
        if not creds_cache_path:
            if self.DEFAULT_CACHE_DIR:
                creds_cache_path = Path(self.DEFAULT_CACHE_DIR).joinpath(
                    type(self).__name__, client_id, f"{bank.name.lower()}.json"
                )
            else:
                creds_cache_path = user_data_dir(
                    file_name=sep.join(
                        [
                            "oauth_credentials",
                            type(self).__name__,
                            client_id,
                            f"{bank.name.lower()}.json",
                        ]
                    )
                )

        force_mkdir(creds_cache_path, path_is_file=True)

        super().__init__(
            base_url=self.BASE_URL,
            access_token_endpoint=self.ACCESS_TOKEN_ENDPOINT,
            auth_link_base=self.AUTH_LINK_BASE,
            client_id=client_id,
            client_secret=client_secret,
            log_requests=log_requests,
            # TrueLayer shares the same Client ID for all banks, so override the
            # default to separate by bank
            creds_cache_path=creds_cache_path,
            scopes=scopes or self.DEFAULT_SCOPES,
            oauth_login_redirect_host=oauth_login_redirect_host,
            oauth_redirect_uri_override=oauth_redirect_uri_override,
            headless_auth_link_callback=headless_auth_link_callback,
            use_existing_credentials_only=use_existing_credentials_only,
        )

        self.bank = bank

    def _get_entity_by_id(
        self,
        entity_id: str,
        entity_class: type[AccountOrCard],
    ) -> AccountOrCard | None:
        """Get entity info based on a given ID.

        Args:
            entity_id (str): the unique ID for the account/card
            entity_class (type): the class to instantiate with the returned info

        Returns:
            Union([Account, Card]): a Card instance with associated info

        Raises:
            HTTPError: if a HTTPError is raised by the request, and it's not because
             the ID wasn't found
            ValueError: if >1 result is returned from the TrueLayer API
        """
        try:
            results = self.get_json_response(
                f"/data/v1/{entity_class.__name__.lower()}s/{entity_id}"
            ).get("results", [])
        except HTTPError as exc:
            if exc.response.json().get("error") == "account_not_found":
                return None
            raise

        if len(results) != 1:
            raise ValueError(
                f"Unexpected number of results when getting {entity_class.__name__}:"
                f" {len(results)}",
            )

        return entity_class.from_json_response(results[0], truelayer_client=self)

    def _list_entities(self, entity_class: type[AccountOrCard]) -> list[AccountOrCard]:
        """List all accounts/cards under the given bank account.

        Args:
            entity_class (type): the class to instantiate with the returned info

        Returns:
            list[Union([Account, Card])]: a list of Account/Card instances with
             associated info

        Raises:
            HTTPError: if a HTTPError is raised by the `_get` method, but it's not a 501
        """
        try:
            res = self.get_json_response(f"/data/v1/{entity_class.__name__.lower()}s")
        except HTTPError as exc:
            if exc.response.json().get("error") == "endpoint_not_supported":
                LOGGER.warning(
                    "{entity_class.__name__}s endpoint not supported by %s",
                    self.bank.value,
                )
                res = {}
            else:
                raise

        return [
            entity_class.from_json_response(result, truelayer_client=self)
            for result in res.get("results", [])
        ]

    def get_account_by_id(
        self,
        account_id: str,
    ) -> Account | None:
        """Get an Account instance based on the ID.

        Args:
            account_id (str): the ID of the card

        Returns:
            Account: an Account instance, with all relevant info
        """
        return self._get_entity_by_id(account_id, Account)

    def get_card_by_id(
        self,
        card_id: str,
    ) -> Card | None:
        """Get a Card instance based on the ID.

        Args:
            card_id (str): the ID of the card

        Returns:
            Card: a Card instance, with all relevant info
        """
        return self._get_entity_by_id(card_id, Card)

    def list_accounts(self) -> list[Account]:
        """List all accounts under the given bank account.

        Returns:
            list[Account]: Account instances, containing all related info
        """
        return self._list_entities(Account)

    def list_cards(self) -> list[Card]:
        """List all accounts under the given bank account.

        Returns:
            list[Account]: Account instances, containing all related info
        """
        return self._list_entities(Card)


Account.update_forward_refs()
Card.update_forward_refs()
TrueLayerEntity.update_forward_refs()
