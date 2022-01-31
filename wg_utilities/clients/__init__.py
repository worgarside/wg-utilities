"""Useful clients for commonly accessed APIs/services"""
from datetime import datetime
from threading import Thread
from time import sleep

from flask import Flask, request
from requests import get

from .google import GoogleClient
from .spotify import SpotifyClient
from .truelayer import TrueLayerClient
from .monzo import MonzoClient


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
            print("waiting", time_elapsed)
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
