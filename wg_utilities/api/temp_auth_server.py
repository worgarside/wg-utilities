"""Provide a class for creating a temporary server during an authentication flow."""
from __future__ import annotations

from textwrap import dedent
from threading import Thread
from time import sleep, time
from typing import Any, cast

from flask import Flask, Response, request
from werkzeug.serving import make_server


class TempAuthServer:
    """Temporary Flask server for auth flows.

    This allows the auth code to be retrieved without manual intervention

    Args:
        name (str): the name of the Flask application package (i.e. __name__)
        host (str): the hostname to listen on
        port (int): the port of the webserver
        debug (bool): if given, enable or disable debug mode
        auto_run (bool): automatically run the server on instantiation
    """

    class ServerThread(Thread):
        """Run a Flask app in a separate thread with shutdown control."""

        def __init__(self, app: Flask, host: str = "localhost", port: int = 0):
            super().__init__()

            if port == 0:
                for i in range(5001, 5021):
                    try:
                        self.server = make_server(host, i, app)
                        break
                    except (SystemExit, OSError):
                        continue
                else:
                    raise OSError("No available ports in range 5000-5020")
            else:
                self.server = make_server(host, port, app)

            self.ctx = app.app_context()
            self.ctx.push()

            self.host = self.server.host
            self.port = self.server.port

        def run(self) -> None:
            """Start the server."""
            self.server.serve_forever()

        def shutdown(self) -> None:
            """Shutdown the server."""
            self.server.shutdown()

    def __init__(
        self,
        name: str,
        host: str = "localhost",
        port: int = 0,
        *,
        debug: bool = False,
        auto_run: bool = False,
    ):
        self.host = host
        self._user_port = port
        self._actual_port: int
        self.debug = debug

        self.app = Flask(name)

        self._server_thread: TempAuthServer.ServerThread
        self._request_args: dict[str, dict[str, object]] = {}

        self.create_endpoints()

        if auto_run:
            self.start_server()

    def create_endpoints(self) -> None:
        """Create all necessary endpoints.

        This is an "endpoint factory" (rather than one decorated method per endpoint)
        because of the need to use `self.app` as the decorator
        """

        @self.app.route("/get_auth_code", methods=["GET"])
        def get_auth_code() -> Response:
            # TODO add 400 response for mismatch in state token
            """Endpoint for getting auth code from third party callback.

            Returns:
                dict: simple response dict
            """
            self._request_args[request.path] = request.args

            return cast(
                Response,
                self.app.response_class(
                    response=dedent(
                        """
                    <html lang="en">
                    <head>
                        <style>
                            body {
                                font-family: Verdana, sans-serif;
                                height: 100vh;
                            }
                        </style>
                        <title>Authentication Complete</title>
                    </head>
                    <body onclick="self.close()">
                        <h1>Authentication complete!</h1>
                        <span>Click anywhere to close this window.</span>
                    </body>
                    </html>
                """,
                    ).strip(),
                    status=200,
                ),
            )

    def wait_for_request(
        self,
        endpoint: str,
        max_wait: int = 300,
        *,
        kill_on_request: bool = False,
    ) -> dict[str, Any]:
        """Wait for a request.

        Wait for a request to come into the server for when it is needed in a
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

        if not self.is_running:
            self.start_server()

        start_time = time()
        while (
            time_elapsed := time() - start_time
        ) <= max_wait and not self._request_args.get(endpoint):
            sleep(0.5)

        if time_elapsed > max_wait:
            raise TimeoutError(
                f"No request received to {endpoint} within {max_wait} seconds",
            )

        if kill_on_request:
            self.stop_server()

        return dict(self._request_args[endpoint])

    def start_server(self) -> None:
        """Run the local server."""
        if not self.is_running:
            self.server_thread.start()

            self._actual_port = self.server_thread.port

    def stop_server(self) -> None:
        """Stop the local server by hitting its `/kill` endpoint.

        See Also:
            self.create_endpoints: `/kill` endpoint
        """
        # No point instantiating a new server if we're just going to kill it
        if hasattr(self, "_server_thread") and self.server_thread.is_alive():
            self.server_thread.shutdown()

            while self.server_thread.is_alive():
                pass

            del self._server_thread

    @property
    def get_auth_code_url(self) -> str:
        """Get the URL for the auth code endpoint.

        Returns:
            str: the URL for the auth code endpoint
        """
        return f"http://{self.host}:{self.port}/get_auth_code"

    @property
    def is_running(self) -> bool:
        """Return whether the server is is_running."""
        if not hasattr(self, "_server_thread"):
            return False

        return self.server_thread.is_alive()

    @property
    def port(self) -> int:
        """Port.

        Returns:
            int: the port of the server

        Raises:
            ValueError: if the server is not running
        """
        if not hasattr(self, "_actual_port"):
            raise ValueError("Server is not running")

        return self._actual_port

    @port.setter
    def port(self, port: int) -> None:
        """Port setter.

        Args:
            port (int): the port to set

        Raises:
            ValueError: if the server is already running
        """
        if self.is_running:
            raise ValueError("Cannot set port while server is running")

        self._user_port = port

    @property
    def server_thread(self) -> ServerThread:
        """Server thread.

        Returns:
            ServerThread: the server thread
        """
        if not hasattr(self, "_server_thread"):
            self._server_thread = self.ServerThread(
                self.app,
                host=self.host,
                port=self._user_port,
            )

        return self._server_thread
