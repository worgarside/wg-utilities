"""Custom client for interacting with TrueLayer's API"""
from enum import Enum
from json import load, dump
from logging import getLogger, DEBUG
from os import getenv
from time import time
from webbrowser import open as open_browser

from jwt import decode, DecodeError
from requests import post

from wg_utilities.functions import user_data_dir, force_mkdir
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


class TrueLayerBank(Enum):
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


class TrueLayerClient:
    """Custom client for interacting with TrueLayer's APIs, including all necessary
    authentication functionality

    Args:
        client_id (str): the client ID for the TrueLayer application
        client_secret (str): the client secret
        bank (TrueLayerBank): the bank which we're working with
        redirect_uri (str): the redirect URI for the auth flow
        access_token_expiry_threshold (int): the number of seconds to subtract from
         the access token's expiry when checking its expiry status
    """

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
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.bank = bank
        self.redirect_uri = redirect_uri
        self.access_token_expiry_threshold = access_token_expiry_threshold

        self.auth_code_env_var = f"TRUELAYER_{self.bank.name}_AUTH_CODE"

        self._all_credentials_json = None
        self._credentials = None

    def refresh_access_token(self):
        """Uses the cached refresh token to submit a request to TL's API for a new
        access token"""

        res = post(
            self.ACCESS_TOKEN_ENDPOINT,
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
            },
        )

        res.raise_for_status()

        # Maintain any existing credential values in the dictionary whilst updating
        # new ones
        self.credentials = {
            **self.credentials,
            **res.json(),
        }

    @property
    def authentication_link(self):
        """
        Returns:
            str: the authentication link, including the client ID
        """
        # pylint: disable=line-too-long
        return f"https://auth.truelayer.com/?response_type=code&client_id={self.client_id}&scope=info%20accounts%20balance%20cards%20transactions%20direct_debits%20standing_orders%20offline_access&redirect_uri=https://console.truelayer.com/redirect-page&providers=uk-ob-all%20uk-oauth-all"

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
            with open(self.CREDS_FILE_PATH, encoding="UTF-8") as fin:
                self._all_credentials_json = load(fin)
        except FileNotFoundError:
            LOGGER.info("Unable to find local creds file")
            self._all_credentials_json = {}

        if self.bank.name not in self._all_credentials_json:
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

        if self.access_token_has_expired:
            self.refresh_access_token()

        return self._all_credentials_json[self.bank.name]

    @credentials.setter
    def credentials(self, value):
        self._all_credentials_json[self.bank.name] = value

        with open(
            force_mkdir(self.CREDS_FILE_PATH, path_is_file=True), "w", encoding="UTF-8"
        ) as fout:
            dump(self._all_credentials_json, fout)

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
                self.access_token, options={"verify_signature": False}
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
