"""Custom client for interacting with Monzo's API"""

from logging import getLogger, DEBUG

from requests import get

from wg_utilities.clients._generic_oauth import OauthClient
from wg_utilities.functions import user_data_dir
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


class MonzoClient(OauthClient):
    """Custom client for interacting with Monzo's API"""

    ACCESS_TOKEN_ENDPOINT = "https://api.monzo.com/oauth2/token"
    BASE_URL = "https://api.monzo.com"
    CREDS_FILE_PATH = user_data_dir(file_name="monzo_api_creds.json")

    def __init__(
        self,
        *,
        client_id,
        client_secret,
        redirect_uri="http://0.0.0.0:5001/get_auth_code",
        access_token_expiry_threshold=60,
        log_requests=False,
        creds_cache_path=None,
    ):
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            access_token_expiry_threshold=access_token_expiry_threshold,
            log_requests=log_requests,
            creds_cache_path=creds_cache_path,
        )

    @property
    def access_token_has_expired(self):
        """Custom expiry check for Monzo client as JWT doesn't seem to include expiry
         time. Any errors/missing credentials result in a default value of True

        Returns:
            bool: expiry status of JWT
        """
        self._load_local_credentials()

        if not (access_token := self._credentials.get("access_token")):
            return True

        res = get(
            f"{self.BASE_URL}/ping/whoami",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        return res.json().get("authenticated", False) is False
