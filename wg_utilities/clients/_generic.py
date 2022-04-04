"""Generic Oauth client to allow for reusable authentication flows/checks etc."""
from copy import deepcopy
from datetime import datetime
from json import dump, load, dumps
from logging import getLogger, DEBUG
from os import remove
from random import choice
from string import ascii_letters
from threading import Thread
from time import sleep
from time import time
from webbrowser import open as open_browser

from flask import Flask, request

# noinspection PyPackageRequirements
from google.auth.transport.requests import AuthorizedSession

# noinspection PyPackageRequirements
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from jwt import decode, DecodeError
from requests import get, post

from wg_utilities.functions import user_data_dir, force_mkdir
from wg_utilities.loggers import add_stream_handler


class TempAuthServer:
    """Temporary Flask server for auth flows, allowing the auth code to be retrieved
    without manual intervention

    Args:
        name (str): the name of the application package
        host (str): the hostname to listen on
        port (int): the port of the webserver
        debug (bool): if given, enable or disable debug mode
        auto_run (bool): automatically run the server on instantiation
    """

    def __init__(
        self,
        name,
        host="0.0.0.0",
        port=5001,
        debug=False,
        auto_run=True,
    ):
        self.host = host
        self.port = port
        self.debug = debug

        self.app = Flask(name)
        self.app_thread = Thread(
            target=lambda: self.app.run(
                host=self.host, port=self.port, debug=self.debug, use_reloader=False
            )
        )

        self._request_args = {}

        self.create_endpoints()

        if auto_run:
            self.run_server()

    def create_endpoints(self):
        """Create all necessary endpoints. This is a single method (rather than one
        method per endpoint) because of the need to use `self.app` as the decorator
        """

        @self.app.route("/get_auth_code", methods=["GET"])
        def get_auth_code():
            """Endpoint for getting auth code from third party callback

            Returns:
                dict: simple response dict
            """
            self._request_args[request.path] = request.args
            return {
                "status_code": 200,
            }

        @self.app.route("/kill", methods=["GET"])
        def kill():
            """Workaround endpoint for killing the server from within a script

            Returns:
                dict: simple response dict

            Raises:
                RuntimeError: if the server can't be killed due to the runtime
                 environment
            """
            if (func := request.environ.get("werkzeug.server.shutdown")) is None:
                raise RuntimeError("Not running with the Werkzeug Server")
            func()
            return {
                "status_code": 200,
            }

    def wait_for_request(self, endpoint, max_wait=300, kill_on_request=False):
        """Wait for a request to come into the server for when it is needed in a
         synchronous flow

        Args:
            endpoint (str): the endpoint path to wait for a request to
            max_wait (int): how many seconds to wait before timing out
            kill_on_request (bool): kill/stop the server when a request comes through

        Returns:
            dict: the args which were sent with the request

        Raises:
            TimeoutError: if no request is received within the timeout limit
        """
        self._request_args[endpoint] = None

        start_time = datetime.now()
        while (
            time_elapsed := (datetime.now() - start_time).seconds
        ) < max_wait and not self._request_args.get(endpoint):
            sleep(1)

        if time_elapsed > max_wait:
            raise TimeoutError(
                f"No request received to {endpoint} within {max_wait} seconds"
            )

        if kill_on_request:
            self.stop_server()

        return self._request_args[endpoint]

    def run_server(self):
        """Run the local server"""
        self.app_thread.start()

    def stop_server(self):
        """Stops the local server by hitting its `/kill` endpoint

        See Also:
            self.create_endpoints: `/kill` endpoint
        """
        # noinspection HttpUrlsUsage
        get(f"http://{self.host}:{self.port}/kill")


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

        self.temp_auth_server = None

    def _get(self, url, params=None):
        """Wrapper for GET requests which covers authentication, URL parsing, etc. etc.

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
            auth_link = f"https://auth.monzo.com/?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&state={state_token}"  # noqa E501
            self.logger.debug("Opening %s", auth_link)
            open_browser(auth_link)

            self.temp_auth_server = TempAuthServer(__name__)

            request_args = self.temp_auth_server.wait_for_request(
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


class GoogleClient:
    """Custom client for interacting with the Google APIs

    Args:
        project (str): the name of the project which this client is being used for
        scopes (list): a list of scopes the client can be given
        client_id_json_path (str): the path to the `client_id.json` file downloaded
         from Google's API Console
        creds_cache_path (str): file path for where to cache credentials
        access_token_expiry_threshold (int): the threshold for when the access token is
         considered expired
        logger (RootLogger): a logger to use throughout the client functions
    """

    DEFAULT_PARAMS = {
        "pageSize": "50",
    }

    def __init__(
        self,
        project,
        scopes=None,
        client_id_json_path=None,
        creds_cache_path=None,
        access_token_expiry_threshold=60,
        logger=None,
    ):
        self.project = project
        self.scopes = scopes or []
        self.client_id_json_path = client_id_json_path
        self.creds_cache_path = creds_cache_path or user_data_dir(
            file_name="google_api_creds.json"
        )
        self.access_token_expiry_threshold = access_token_expiry_threshold

        if logger:
            self.logger = logger
        else:
            self.logger = getLogger(__name__)
            self.logger.setLevel(DEBUG)
            add_stream_handler(self.logger)

        if not scopes:
            self.logger.warning(
                "No scopes set for Google client. Functionality will be limited."
            )

        self._all_credentials_json = {}
        self._session = None

        self.temp_auth_server = None

    def _list_items(self, method, url, list_key, *, params=None):
        """Generic method for listing items on Google's API(s)

        Args:
            method (callable): the Google client session method to use
            url (str): the API endpoint to send a request to
            list_key (str): the key to use in extracting the data from the response
            params (dict): any extra params to be passed in the request

        Returns:
            list: a list of dicts, each representing an item from the API
        """
        params = (
            {**self.DEFAULT_PARAMS, **params}
            if params
            else deepcopy(self.DEFAULT_PARAMS)
        )
        self.logger.info(
            "Listing all items at endpoint `%s` with params %s", url, dumps(params)
        )

        res = method(url, params=params)

        res.raise_for_status()

        item_list = res.json().get(list_key, [])

        while next_token := res.json().get("nextPageToken"):
            res = method(
                url,
                params={**params, "pageToken": next_token},
            )
            res.raise_for_status()
            item_list.extend(res.json().get(list_key, []))
            self.logger.debug("Found %i items so far", len(item_list))

        return item_list

    def delete_creds_file(self):
        """Delete the local creds file"""
        try:
            remove(self.creds_cache_path)
        except FileNotFoundError:
            pass

    def get_items(self, url, list_key="items", *, params=None):
        """Wrapper method for getting a list of items

        See Also:
            self._list_items: main worker method for this functionality
        """

        return self._list_items(self.session.get, url, list_key, params=params)

    def refresh_access_token(self):
        """Uses the cached refresh token to submit a request to TL's API for a new
        access token"""

        self.logger.info("Refreshing access token")

        res = post(
            "https://accounts.google.com/o/oauth2/token",
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
            **self._all_credentials_json[self.project],
            **res.json(),
        }

    @property
    def access_token_has_expired(self):
        """Decodes the JWT access token and evaluates the expiry time

        Returns:
            bool: has the access token expired?
        """

        if self.project not in self._all_credentials_json:
            return True

        try:
            expiry_epoch = decode(
                # can't use self.access_token here, as that uses self.credentials,
                # which in turn (recursively) checks if the access token has expired
                self._all_credentials_json[self.project].get("access_token"),
                options={"verify_signature": False},
            ).get("exp", 0)

            return (expiry_epoch - self.access_token_expiry_threshold) < int(time())
        except DecodeError:
            # treat invalid token as expired, so we get a new one
            return True

    @property
    def client_id(self):
        """
        Returns:
            str: the current client ID
        """
        return self._all_credentials_json.get(self.project, {}).get("client_id")

    @property
    def client_secret(self):
        """
        Returns:
            str: the current client secret
        """
        return self._all_credentials_json.get(self.project, {}).get("client_secret")

    @property
    def credentials(self):
        """Gets creds as necessary (including first time setup) and authenticates them

        Returns:
            Credentials: authorized credentials for use in creating a session

        Raises:
            EOFError: when no data is successfully returned for the auth code (usually
             when running the script automatically)
            ValueError: same as above, but if the EOFError isn't raised
        """

        try:
            with open(
                force_mkdir(self.creds_cache_path, path_is_file=True), encoding="UTF-8"
            ) as fin:
                self._all_credentials_json = load(fin)
        except FileNotFoundError:
            self.logger.info("Unable to find local creds file")
            self._all_credentials_json = {}

        if self.project not in self._all_credentials_json:
            self.logger.info(
                "Performing first time login for project `%s`", self.project
            )

            self.client_id_json_path = self.client_id_json_path or input(
                "Download your Client ID JSON from https://console.cloud.google.com/"
                f"apis/credentials?project={self.project} and paste the file path"
                " here: "
            )

            flow = Flow.from_client_secrets_file(
                self.client_id_json_path,
                scopes=self.scopes,
                redirect_uri="http://localhost:5001/get_auth_code",
            )

            auth_url, _ = flow.authorization_url(access_type="offline")
            self.logger.debug("Opening %s", auth_url)
            open_browser(auth_url)

            self.temp_auth_server = TempAuthServer(__name__)

            request_args = self.temp_auth_server.wait_for_request(
                "/get_auth_code", kill_on_request=True
            )

            flow.fetch_token(code=request_args.get("code"))

            self.credentials = {
                "token": flow.credentials.token,
                "refresh_token": flow.credentials.refresh_token,
                "id_token": flow.credentials.id_token,
                "scopes": flow.credentials.scopes,
                "token_uri": flow.credentials.token_uri,
                "client_id": flow.credentials.client_id,
                "client_secret": flow.credentials.client_secret,
            }

        if self.access_token_has_expired:
            self.refresh_access_token()

        return Credentials.from_authorized_user_info(
            self._all_credentials_json[self.project], self.scopes
        )

    @credentials.setter
    def credentials(self, value):
        """
        Args:
            value (dict): the new values to use for the creds for this project
        """
        self._all_credentials_json[self.project] = value

        with open(
            force_mkdir(self.creds_cache_path, path_is_file=True), "w", encoding="UTF-8"
        ) as fout:
            dump(self._all_credentials_json, fout)

    @property
    def refresh_token(self):
        """
        Returns:
            str: the current refresh token
        """
        return self._all_credentials_json.get(self.project, {}).get("refresh_token")

    @property
    def session(self):
        """Uses the Credentials object to sign in to an authorized Google API session

        Returns:
            AuthorizedSession: an active, authorized Google API session
        """
        if not self._session:
            self._session = AuthorizedSession(self.credentials)

        return self._session
