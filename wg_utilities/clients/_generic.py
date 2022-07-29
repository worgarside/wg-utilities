"""Generic Oauth client to allow for reusable authentication flows/checks etc."""
from datetime import datetime
from json import dump, dumps, load
from logging import DEBUG, Logger, getLogger
from pathlib import Path
from random import choice
from string import ascii_letters
from threading import Thread
from time import sleep, time
from typing import Any, Dict, Optional, TypedDict, Union
from webbrowser import open as open_browser

from flask import Flask, request
from jwt import DecodeError, decode
from requests import Response, get, post

from wg_utilities.functions import force_mkdir, user_data_dir


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
        name: str,
        host: str = "0.0.0.0",
        port: int = 5001,
        debug: bool = False,
        auto_run: bool = True,
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

        self._request_args: Dict[str, Dict[str, Any]] = {}

        self.create_endpoints()

        if auto_run:
            self.run_server()

    def create_endpoints(self) -> None:
        """Create all necessary endpoints. This is a single method (rather than one
        method per endpoint) because of the need to use `self.app` as the decorator
        """

        @self.app.route("/get_auth_code", methods=["GET"])
        def get_auth_code() -> str:
            """Endpoint for getting auth code from third party callback

            Returns:
                dict: simple response dict
            """
            self._request_args[request.path] = request.args
            return dumps(
                {
                    "statusCode": 200,
                }
            )

        @self.app.route("/kill", methods=["GET"])
        def kill() -> str:
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
            return dumps(
                {
                    "statusCode": 200,
                }
            )

    def wait_for_request(
        self, endpoint: str, max_wait: int = 300, kill_on_request: bool = False
    ) -> Dict[str, Any]:
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

    def run_server(self) -> None:
        """Run the local server"""
        self.app_thread.start()

    def stop_server(self) -> None:
        """Stops the local server by hitting its `/kill` endpoint

        See Also:
            self.create_endpoints: `/kill` endpoint
        """
        # noinspection HttpUrlsUsage
        get(f"http://{self.host}:{self.port}/kill")


class _OauthCredentialsInfo(TypedDict):
    access_token: str
    client_id: str
    expires_in: int
    refresh_token: str
    scope: str
    token_type: str
    user_id: str


class OauthClient:
    """Custom client for interacting with Oauth APIs, including all necessary/basic
    authentication functionality"""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        base_url: str,
        access_token_endpoint: str,
        redirect_uri: str = "http://0.0.0.0:5001/get_auth_code",
        access_token_expiry_threshold: int = 60,
        log_requests: bool = False,
        creds_cache_path: Optional[Union[str, Path]] = None,
        logger: Optional[Logger] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.access_token_endpoint = access_token_endpoint
        self.redirect_uri = redirect_uri
        self.access_token_expiry_threshold = access_token_expiry_threshold
        self.log_requests = log_requests
        self.creds_cache_path = creds_cache_path or user_data_dir(
            file_name=f"{client_id}.json"
        )

        if logger:
            self.logger = logger
        else:
            self.logger = getLogger(__name__)
            self.logger.setLevel(DEBUG)

        self._credentials: _OauthCredentialsInfo

        self.temp_auth_server: Optional[TempAuthServer] = None

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Response:
        """Wrapper for GET requests which covers authentication, URL parsing, etc. etc.

        Args:
            url (str): the URL path to the endpoint (not necessarily including the
             base URL)
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            Response: the response from the HTTP request
        """

        if url.startswith("/"):
            url = f"{self.base_url}{url}"

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

    def _load_local_credentials(self) -> None:
        with open(self.creds_cache_path, encoding="UTF-8") as fin:
            self._credentials = load(fin).get(self.client_id, {})

    def exchange_auth_code(self, code: str) -> None:
        """Allows first-time (or repeated) authentication

        Args:
            code (str): the authorization code returned from the auth flow
        """

        res = post(
            self.access_token_endpoint,
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

    def get_json_response(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Gets a simple JSON object from a URL

        Args:
            url (str): the API endpoint to GET
            params (dict): the parameters to be passed in the HTTP request

        Returns:
            dict: the JSON from the response
        """
        return self._get(url, params=params).json()  # type: ignore[no-any-return]

    def refresh_access_token(self) -> None:
        """Uses the cached refresh token to submit a request to TL's API for a new
        access token"""

        if not hasattr(self, "_credentials"):
            self._load_local_credentials()

        self.logger.info("Refreshing access token")

        res = post(
            self.access_token_endpoint,
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
            **self._credentials,  # type: ignore
            **res.json(),
        }

    @property
    def access_token(self) -> Optional[str]:
        """
        Returns:
            str: the access token for this bank's API
        """
        return self.credentials.get("access_token")

    @property
    def access_token_has_expired(self) -> bool:
        """Decodes the JWT access token and evaluates the expiry time

        Returns:
            bool: has the access token expired?
        """
        if not hasattr(self, "_credentials"):
            self._load_local_credentials()

        try:
            expiry_epoch = decode(
                # can't use self.access_token here, as that uses self.credentials,
                # which in turn (recursively) checks if the access token has expired
                self._credentials["access_token"],
                options={"verify_signature": False},
            ).get("exp", 0)

            return bool(
                (expiry_epoch - self.access_token_expiry_threshold) < int(time())
            )
        except (DecodeError, KeyError):
            # treat invalid token as expired, so we get a new one
            return True

    @property
    def credentials(self) -> _OauthCredentialsInfo:
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

            self.exchange_auth_code(request_args["code"])

        if self.access_token_has_expired:
            self.refresh_access_token()

        return self._credentials

    @credentials.setter
    def credentials(self, value: _OauthCredentialsInfo) -> None:
        """
        Args:
            value (dict): the new values to use for the creds for this project
        """
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
    def request_headers(self) -> Dict[str, str]:
        """
        Returns:
            dict: auth headers for HTTP requests
        """
        return {"Authorization": f"Bearer {self.access_token}"}

    @property
    def refresh_token(self) -> Optional[str]:
        """
        Returns:
            str: the API refresh token
        """
        return self.credentials.get("refresh_token")
