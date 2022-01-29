"""Generic Oauth client to allow for reusable authentication flows/checks etc."""
from json import load, dump, dumps
from logging import getLogger, DEBUG
from random import choice
from string import ascii_letters
from time import time
from webbrowser import open as open_browser

from jwt import decode, DecodeError
from requests import post, get

from wg_utilities.clients import TempAuthServer
from wg_utilities.functions import force_mkdir
from wg_utilities.loggers import add_stream_handler


class OauthClient:
    """Custom client for interacting with Oauth APIs, including all necessary/basic
    authentication functionality"""

    ACCESS_TOKEN_ENDPOINT = None
    BASE_URL = None
    CREDS_FILE_PATH = None

    def __init__(
        self,
        *,
        client_id,
        client_secret,
        redirect_uri="http://0.0.0.0:5001/get_auth_code",
        access_token_expiry_threshold=60,
        log_requests=False,
        creds_cache_path=None,
        logger=None,
    ):

        if not all([self.ACCESS_TOKEN_ENDPOINT, self.BASE_URL, self.CREDS_FILE_PATH]):
            missing_class_attrs = ", ".join(
                [
                    attr
                    for attr in (
                        self.ACCESS_TOKEN_ENDPOINT,
                        self.BASE_URL,
                        self.CREDS_FILE_PATH,
                    )
                    if not attr
                ]
            )
            raise ValueError(
                "All class attributes need to be set in child class:"
                f" {missing_class_attrs}"
            )

        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token_expiry_threshold = access_token_expiry_threshold
        self.log_requests = log_requests
        self.creds_cache_path = creds_cache_path or self.CREDS_FILE_PATH

        if logger:
            self.logger = logger
        else:
            self.logger = getLogger(__name__)
            self.logger.setLevel(DEBUG)
            add_stream_handler(self.logger)

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
            self.logger.debug(
                "GET %s with params %s", url, dumps(params or {}, default=str)
            )

        res = get(
            url,
            headers=self.request_headers,
            params=params or {},
        )

        res.raise_for_status()

        return res

    def _load_local_credentials(self):
        try:
            with open(self.creds_cache_path, encoding="UTF-8") as fin:
                self._credentials = load(fin).get(self.client_id, {})
        except FileNotFoundError:
            self.logger.info("Unable to find local creds file")
            self._credentials = {}

    def exchange_auth_code(self, code):
        """Allows first-time (or repeated) authentication

        Args:
            code (str): the authorization code returned from the auth flow
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

    def get_json_response(self, url, params=None):
        """Gets a simple JSON object from a URL

        Args:
            url (str): the API endpoint to GET
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            dict: the JSON from the response
        """
        return self._get(url, params=params).json()

    def refresh_access_token(self):
        """Uses the cached refresh token to submit a request to TL's API for a new
        access token"""

        self.logger.info("Refreshing access token")

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
    def credentials(self):
        """Attempts to retrieve credentials from local cache, creates new ones if
        they're not found.

        Returns:
            dict: the credentials for the chosen bank

        Raises:
            ValueError: if the state token returned from the request doesn't match the
             expected value
        """
        self._load_local_credentials()

        if not self._credentials:
            self.logger.info("Performing first time login")
            state_token = "".join(choice(ascii_letters) for _ in range(32))
            # pylint: disable=line-too-long
            auth_link = f"https://auth.monzo.com/?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&state={state_token}"
            self.logger.debug("Opening %s", auth_link)
            open_browser(auth_link)

            temp_server = TempAuthServer(__name__)

            request_args = temp_server.wait_for_request(
                "/get_auth_code", kill_on_request=True
            )

            if state_token != request_args.get("state"):
                raise ValueError(
                    "State token received in request doesn't match expected value"
                )

            code = request_args.get("code")

            self.exchange_auth_code(code)

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

        all_credentials[self.client_id] = self._credentials

        with open(self.creds_cache_path, "w", encoding="UTF-8") as fout:
            dump(all_credentials, fout)

    @property
    def request_headers(self):
        """
        Returns:
            dict: auth headers for HTTP requests
        """
        return {"Authorization": f"Bearer {self.access_token}"}

    @property
    def refresh_token(self):
        """
        Returns:
            str: the TL API refresh token
        """
        return self.credentials.get("refresh_token")
