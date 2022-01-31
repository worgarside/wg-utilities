"""Custom client for interacting with TrueLayer's API"""
from datetime import datetime, timedelta
from enum import Enum
from json import load, dump, dumps
from logging import getLogger, DEBUG
from os import getenv
from time import time
from webbrowser import open as open_browser

from jwt import decode, DecodeError
from requests import post, get, HTTPError

from wg_utilities.functions import user_data_dir, force_mkdir
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class Bank(Enum):
    """Enum for all banks supported by TrueLayer"""

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
    TESCO_BANK = "Tesco Bank"
    TIDE = "Tide"
    TSB = "TSB"
    ULSTER_BANK = "Ulster Bank"
    ULSTER_BUSINESS = "Ulster Business"
    VIRGIN_MONEY = "Virgin Money"
    WISE = "Wise"
    YORKSHIRE_BUILDING_SOCIETY = "Yorkshire Building Society"


class TransactionCategory(Enum):
    """Enum for TrueLayer transaction types, including an overridden __init__
    method for setting a description as well as the main value"""

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

    def __init__(self, value, description):
        self._value_ = value
        self.description = description


class TrueLayerEntity:
    """Parent class for all TrueLayer entities (accounts, cards, etc.)

    Args:
        json (dict): the JSON returned from the TrueLayer API which defines the
         entity
        truelayer_client (TrueLayerClient): a TrueLayer client, usually the one which
         retrieved this entity from the API
    """

    # Default value
    BALANCE_FIELDS = ()

    def __init__(self, json, truelayer_client=None, balance_update_threshold=15):
        self.json = json
        self._truelayer_client = truelayer_client

        self._available_balance = None
        self._current_balance = None
        self._overdraft = None
        self._credit_limit = None
        self._last_statement_balance = None
        self._last_statement_date = None
        self._payment_due = None
        self._payment_due_date = None

        self.entity_type = self.__class__.__name__.lower()

        self.last_balance_update = datetime(1970, 1, 1)
        self.balance_update_threshold = balance_update_threshold

    def get_transactions(self, from_datetime=None, to_datetime=None):
        """Polls the TL API to get all transactions under the given entity. If
        only one datetime parameter is provided, then the other is given a default
        value which maximises the range of results returned

        Args:
            from_datetime (datetime): lower range of transaction date range query
            to_datetime (datetime): upper range of transaction date range query

        Yields:
            Transaction: one instance per tx, including all metadata etc.
        """

        if from_datetime or to_datetime:
            from_datetime = from_datetime or datetime.utcnow() - timedelta(days=90)
            to_datetime = to_datetime or datetime.utcnow()

            params = {
                "from": from_datetime.strftime(DATETIME_FORMAT),
                "to": to_datetime.strftime(DATETIME_FORMAT),
            }
        else:
            params = None

        results = self._truelayer_client.get_json_response(
            f"/data/v1/{self.entity_type}s/{self.id}/transactions", params=params
        ).get("results", [])

        for result in results:
            yield Transaction(result, self, self._truelayer_client)

    def update_balance_values(self):
        """Updates the balance-related instance attributes with the latest values from
        the API
        """

        results = self._truelayer_client.get_json_response(
            f"/data/v1/{self.entity_type}s/{self.id}/balance"
        ).get("results")

        if len(results) != 1:
            raise ValueError(
                "Unexpected number of results when getting balance info:"
                f" {len(results)}",
            )

        balance_result = results[0]

        self._available_balance = balance_result.get("available")
        self._current_balance = balance_result.get("current")
        self._overdraft = balance_result.get("overdraft")
        self._credit_limit = balance_result.get("credit_limit")
        self._last_statement_balance = balance_result.get("last_statement_balance")
        self._last_statement_date = balance_result.get("last_statement_date")
        self._payment_due = balance_result.get("payment_due")
        self._payment_due_date = balance_result.get("payment_due_date")

        self.last_balance_update = datetime.utcnow()

    def _get_balance_property(self, prop_name):
        """Gets a value for a balance-specific property, updating the values if
         necessary (i.e. if they don't already exist). This also has a check to see if
         property is relevant for the given entity type and if not it just returns None

        Args:
            prop_name (str): the name of the property

        Returns:
            str: the value of the balance property
        """

        if prop_name not in self.BALANCE_FIELDS:
            return None

        if getattr(self, f"_{prop_name}") is None or self.last_balance_update <= (
            datetime.utcnow() - timedelta(minutes=self.balance_update_threshold)
        ):
            self.update_balance_values()

        return getattr(self, f"_{prop_name}")

    @property
    def available_balance(self):
        """
        Returns:
            float: the amount of money available to the bank account holder
        """
        return self._get_balance_property("available_balance")

    @property
    def current_balance(self):
        """
        Returns:
            float: the total amount of money in the account, including pending
             transactions
        """
        return self._get_balance_property("current_balance")

    @property
    def overdraft(self):
        """
        Returns:
            float: the overdraft limit of the account
        """
        return self._get_balance_property("overdraft")

    @property
    def credit_limit(self):
        """
        Returns:
            float: the credit limit available to the customer
        """
        return self._get_balance_property("credit_limit")

    @property
    def last_statement_balance(self):
        """
        Returns:
            float: the balance on the last statement
        """
        return self._get_balance_property("last_statement_balance")

    @property
    def last_statement_date(self):
        """
        Returns:
            date: the date the last statement was issued on
        """
        return self._get_balance_property("last_statement_date")

    @property
    def payment_due(self):
        """
        Returns:
            float: the amount of any due payment
        """
        return self._get_balance_property("payment_due")

    @property
    def payment_due_date(self):
        """
        Returns:
            date: the date on which the next payment is due
        """
        return self._get_balance_property("payment_due_date")

    @property
    def pretty_json(self):
        """
        Returns:
            str: a "pretty" version of the JSON, used for debugging etc.
        """
        return dumps(self.json, indent=4, default=str)

    @property
    def currency(self):
        """
        Returns:
            str: ISO 4217 alpha-3 currency code of this entity
        """
        return self.json.get("currency")

    @property
    def display_name(self):
        """
        Returns:
            str: human-readable name of the entity
        """
        return self.json.get("display_name")

    @property
    def id(self):
        """
        Returns:
            str: the unique ID for this entity
        """
        return self.json.get("account_id")

    @property
    def provider_name(self):
        """
        Returns:
            str: the name of the account provider
        """
        return self.json.get("provider", {}).get("display_name")

    @property
    def provider_id(self):
        """
        Returns:
            str: unique identifier for the provider
        """
        return self.json.get("provider", {}).get("provider_id")

    @property
    def provider_logo_uri(self):
        """
        Returns:
            str: url for the account provider's logo
        """
        return self.json.get("provider", {}).get("logo_uri")

    def __str__(self):
        return f"{self.display_name} | {self.provider_name}"


class Transaction:
    """Class for individual transactions for data manipulation etc.

    Args:
        parent_entity (TrueLayerEntity): the entity which this transaction was made
         under
    """

    def __init__(self, json, parent_entity, truelayer_client=None):
        self.json = json
        self._truelayer_client = truelayer_client
        self.parent_entity = parent_entity

    @property
    def pretty_json(self):
        """
        Returns:
            str: a "pretty" version of the JSON, used for debugging etc.
        """
        return dumps(self.json, indent=4, default=str)

    @property
    def id(self):
        """
        Returns:
            str: unique ID for this transaction, it may change between requests
        """
        return self.json.get("transaction_id")

    @property
    def currency(self):
        """
        Returns:
            str: ISO 4217 alpha-3 currency code of this entity
        """
        return self.json.get("currency")

    @property
    def timestamp(self):
        """
        Returns:
            datetime: the timestamp this transaction was made at
        """
        try:
            return datetime.strptime(
                self.json.get("timestamp"), "%Y-%m-%dT%H:%M:%S.%fZ"
            )
        except ValueError:
            return datetime.strptime(self.json.get("timestamp"), "%Y-%m-%dT%H:%M:%SZ")

    @property
    def description(self):
        """
        Returns:
            str: the description of this transaction
        """
        return self.json.get("description")

    @property
    def type(self):
        """
        Returns:
            str: the type of transaction
        """
        return self.json.get("transaction_type")

    @property
    def category(self):
        """
        Returns:
            str: the category of this transaction
        """
        return TransactionCategory[self.json.get("transaction_category", "UNKNOWN")]

    @property
    def classifications(self):
        """
        Returns:
            list: a list of classifications for this transaction
        """
        return self.json.get("transaction_classification")

    @property
    def merchant_name(self):
        """
        Returns:
            str: the name of the merchant with which this transaction was made
        """
        return self.json.get("merchant_name")

    @property
    def amount(self):
        """
        Returns:
            float: the amount this transaction is for
        """
        return self.json.get("amount")

    @property
    def provider_transaction_id(self):
        """
        Returns:
            str: the tx ID from the provider
        """
        return self.json.get("provider_transaction_id")

    @property
    def normalised_provider_transaction_id(self):
        """
        Returns:
            str: a normalised tx ID, less likely to change
        """
        return self.json.get("normalised_provider_transaction_id")

    @property
    def provider_category(self):
        """
        Returns:
            str: the provider transaction category
        """
        return self.json.get("meta", {}).get("provider_category")

    @property
    def provider_transaction_type(self):
        """
        Returns:
            str: the type of transaction, as seen by the provider?
        """
        return self.json.get("meta", {}).get("transaction_type")

    @property
    def counter_party_preferred_name(self):
        """
        Returns:
            str: the preferred name of the merchant
        """
        return self.json.get("meta", {}).get("counter_party_preferred_name")

    @property
    def provider_id(self):
        """
        Returns:
            str: seems to be the same as `self.provider_transaction_id`
        """
        return self.json.get("meta", {}).get("provider_id")

    @property
    def debtor_account_name(self):
        """
        Returns:
            str: the account name of the debtor, if the tx is inbound
        """
        return self.json.get("meta", {}).get("debtor_account_name")

    def __str__(self):
        return f"{self.description} | {self.amount} | {self.merchant_name}"


class Account(TrueLayerEntity):
    """Class for managing individual bank accounts"""

    BALANCE_FIELDS = ("available_balance", "current_balance", "overdraft")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def type(self):
        """
        Returns:
            str: type of the account
        """
        return self.json.get("account_type")

    @property
    def iban(self):
        """
        Returns:
            str: the International Bank Account Number for this account
        """
        return self.json.get("account_number", {}).get("iban")

    @property
    def swift_bic(self):
        """
        Returns:
            str: ISO 9362:2009 Business Identifier Codes.
        """
        return self.json.get("account_number", {}).get("swift_bic")

    @property
    def account_number(self):
        """
        Returns:
            str: the account's account number
        """
        return self.json.get("account_number", {}).get("number")

    @property
    def sort_code(self):
        """
        Returns:
            str: the account's sort code
        """
        return self.json.get("account_number", {}).get("sort_code")


class Card(TrueLayerEntity):
    """Class for managing individual cards"""

    BALANCE_FIELDS = (
        "available_balance",
        "current_balance",
        "credit_limit",
        "last_statement_balance",
        "last_statement_date",
        "payment_due",
        "payment_due_date",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def card_network(self):
        """
        Returns:
            str: card processor. For example, VISA
        """
        return self.json.get("card_network")

    @property
    def type(self):
        """
        Returns:
            str: type of card: credit, debit
        """
        return self.json.get("card_type")

    @property
    def partial_card_number(self):
        """
        Returns:
            str: last few digits of card number
        """
        return self.json.get("partial_card_number")

    @property
    def name_on_card(self):
        """
        Returns:
            str: the name on the card
        """
        return self.json.get("name_on_card")


class TrueLayerClient:
    """Custom client for interacting with TrueLayer's APIs, including all necessary
    authentication functionality

    Args:
        client_id (str): the client ID for the TrueLayer application
        client_secret (str): the client secret
        bank (Bank): the bank which we're working with
        redirect_uri (str): the redirect URI for the auth flow
        access_token_expiry_threshold (int): the number of seconds to subtract from
         the access token's expiry when checking its expiry status
        log_requests (bool): flag for choosing if to log all requests made
        creds_cache_path (str): file path for where to cache credentials
    """

    BASE_URL = "https://api.truelayer.com"
    ACCESS_TOKEN_ENDPOINT = "https://auth.truelayer.com/connect/token"
    CREDS_FILE_PATH = user_data_dir(file_name="truelayer_api_creds.json")

    def __init__(
        self,
        *,
        client_id,
        client_secret,
        bank,
        redirect_uri="https://console.truelayer.com/redirect-page",
        access_token_expiry_threshold=60,
        log_requests=False,
        creds_cache_path=None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.bank = bank
        self.redirect_uri = redirect_uri
        self.access_token_expiry_threshold = access_token_expiry_threshold
        self.log_requests = log_requests
        self.creds_cache_path = creds_cache_path or self.CREDS_FILE_PATH

        self.auth_code_env_var = f"TRUELAYER_{self.bank.name}_AUTH_CODE"

        self._credentials = None

    def _get(self, url, params=None):
        """Wrapper for GET requests which covers authentication, URL parsing, etc etc

        Args:
            url (str): the URL path to the endpoint (not necessarily including the
             base URL)
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            Response: the response from the HTTP request
        """

        if url.startswith("/"):
            url = f"{self.BASE_URL}{url}"

        if self.log_requests:
            LOGGER.debug("GET %s with params %s", url, dumps(params or {}, default=str))

        res = get(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            params=params or {},
        )

        res.raise_for_status()

        return res

    def _get_entity_by_id(self, entity_id, entity_class, entity_instance_kwargs=None):
        """Gets entity info based on a given ID

        Args:
            entity_id (str): the unique ID for the account/card
            entity_class (type): the class to instantiate with the returned info
            entity_instance_kwargs (dict): any kwargs to pass to the entity instance

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

        return entity_class(results[0], self, **entity_instance_kwargs or {})

    def get_json_response(self, url, params=None):
        """Gets a simple JSON object from a URL

        Args:
            url (str): the API endpoint to GET
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            dict: the JSON from the response
        """
        return self._get(url, params=params).json()

    def get_account_by_id(self, account_id, instance_kwargs=None):
        """Get an Account instance based on the ID

        Args:
            account_id (str): the ID of the card
            instance_kwargs (dict): any kwargs to pass to the Account instance

        Returns:
            Account: a Account instance, with all relevant info
        """
        return self._get_entity_by_id(account_id, Account, instance_kwargs)

    def get_card_by_id(self, card_id, instance_kwargs=None):
        """Get a Card instance based on the ID

        Args:
            card_id (str): the ID of the card
            instance_kwargs (dict): any kwargs to pass to the Card instance

        Returns:
            Card: a Card instance, with all relevant info
        """
        return self._get_entity_by_id(card_id, Card, instance_kwargs)

    def list_accounts(self):
        """Lists all accounts under the given bank account

        Yields:
            Account: Account instances, containing all related info

        Raises:
            HTTPError: if a HTTPError is raised by the _get method, but it's not a 501
        """
        try:
            res = self.get_json_response(
                "/data/v1/accounts",
            )
        except HTTPError as exc:
            if exc.response.json().get("error") == "endpoint_not_supported":
                LOGGER.warning("Accounts endpoint not supported by %s", self.bank.value)
                res = {}
            else:
                raise

        for result in res.get("results", []):
            yield Account(result, self)

    def list_cards(self):
        """Lists all accounts under the given bank account

        Yields:
            Account: Account instances, containing all related info

        Raises:
            HTTPError: if a HTTPError is raised by the _get method, but it's not a 501
        """
        try:
            res = self.get_json_response(
                "/data/v1/cards",
            )
        except HTTPError as exc:
            if exc.response.json().get("error") == "endpoint_not_supported":
                LOGGER.warning("Cards endpoint not supported by %s", self.bank.value)
                res = {}
            else:
                raise

        for result in res.get("results", []):
            yield Card(result, self)

    def refresh_access_token(self):
        """Uses the cached refresh token to submit a request to TL's API for a new
        access token"""

        LOGGER.info("Refreshing access token for %s", self.bank.value)

        res = post(
            self.ACCESS_TOKEN_ENDPOINT,
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self._credentials.get("refresh_token"),
            },
        )

        res.raise_for_status()

        # Maintain any existing credential values in the dictionary whilst updating
        # new ones
        self.credentials = {
            **self._credentials,
            **res.json(),
        }

    def authenticate_against_bank(self, code):
        """Allows first-time (or repeated) authentication against the given bank

        Args:
            code (str): the authorization code returned from the TrueLayer console
             auth flow
        """

        res = post(
            self.ACCESS_TOKEN_ENDPOINT,
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )

        res.raise_for_status()

        self.credentials = res.json()

    @property
    def authentication_link(self):
        """
        Returns:
            str: the authentication link, including the client ID
        """
        # pylint: disable=line-too-long
        return f"https://auth.truelayer.com/?response_type=code&client_id={self.client_id}&scope=info%20accounts%20balance%20cards%20transactions%20direct_debits%20standing_orders%20offline_access&redirect_uri={self.redirect_uri}&providers=uk-ob-all%20uk-oauth-all"  # noqa

    @property
    def credentials(self):
        """Attempts to retrieve credentials from local cache, creates new ones if
        they're not found.

        Returns:
            dict: the credentials for the chosen bank

        Raises:
            EOFError: when no data is successfully returned for the auth code (usually
             when running the script automatically)
            ValueError: if no auth code is provided (manually or via env var)
        """

        try:
            with open(self.creds_cache_path, encoding="UTF-8") as fin:
                self._credentials = (
                    load(fin).get(self.client_id, {}).get(self.bank.name)
                )
        except FileNotFoundError:
            LOGGER.info("Unable to find local creds file")
            self._credentials = {}

        if not self._credentials:
            LOGGER.info("Performing first time login for bank `%s`", self.bank.value)
            LOGGER.debug("Opening %s", self.authentication_link)
            open_browser(self.authentication_link)
            try:
                code = input(
                    "Enter the authorization code "
                    f"(or set as env var `{self.auth_code_env_var}`): "
                ) or getenv(self.auth_code_env_var)
            except EOFError:
                if not (code := getenv(self.auth_code_env_var)):
                    LOGGER.critical(
                        "Unable to retrieve auth code from environment variables "
                        "post-EOFError"
                    )
                    raise

            if not code:
                raise ValueError("No auth code provided")

            self.authenticate_against_bank(code)

        if self.access_token_has_expired:
            self.refresh_access_token()

        return self._credentials

    @credentials.setter
    def credentials(self, value):
        self._credentials = value

        try:
            with open(
                force_mkdir(self.creds_cache_path, path_is_file=True), encoding="UTF-8"
            ) as fin:
                all_credentials = load(fin)
        except FileNotFoundError:
            all_credentials = {}

        all_credentials.setdefault(self.client_id, {})[
            self.bank.name
        ] = self._credentials

        with open(self.creds_cache_path, "w", encoding="UTF-8") as fout:
            dump(all_credentials, fout)

    @property
    def access_token(self):
        """
        Returns:
            str: the access token for this bank's API
        """
        return self.credentials.get("access_token")

    @property
    def access_token_has_expired(self):
        """Decodes the JWT access token and evaluates the expiry time

        Returns:
            bool: has the access token expired?
        """
        try:
            expiry_epoch = decode(
                # can't use self.access_token here, as that uses self.credentials,
                # which in turn (recursively) checks if the access token has expired
                self._credentials.get("access_token"),
                options={"verify_signature": False},
            ).get("exp", 0)

            return (expiry_epoch - self.access_token_expiry_threshold) < int(time())
        except DecodeError:
            # treat invalid token as expired, so we get a new one
            return True

    @property
    def refresh_token(self):
        """
        Returns:
            str: the TL API refresh token
        """
        return self.credentials.get("refresh_token")

    @property
    def scope(self):
        """
        Returns:
            list: a list of active API scopes for the current application
        """
        return self.credentials.get("scope", "").split()
