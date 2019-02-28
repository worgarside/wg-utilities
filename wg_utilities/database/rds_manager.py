from ._database import Database
from pymysql import connect as mysql_connect
from sshtunnel import SSHTunnelForwarder
from time import time
from os import path
from warnings import warn


class ParameterWarning(Warning):
    """Custom warning class to be sued when missing parameters"""
    pass


class RDSManager(Database):
    """Extension of the Database class specifically for connecting to a MySQL AWS RDS"""

    def __init__(self, ssh_host: int = None, ssh_port: int = 22, ssh_username: str = None, pkey_path: str = None,
                 db_name: str = None, db_bind_address: str = None, db_host: str = '127.0.0.1', db_port: int = 3306,
                 db_user: str = None, db_password: str = None, *args, **kwargs):
        """Connects to a remote MySQL RDS though an SSH tunnel

        :param db_name: Name of the database to connect to
        :param ssh_host: Host IP of the SSH tunnel
        :param ssh_username: User for access to SSH tunnel
        :param pkey_path: Path to the .pem file containing the PKey
        :param db_bind_address: Binding address for the database
        :param db_user: MySQL username
        :param db_password: MySQL password
        :param db_host: Host IP for the database, usually 127.0.0.1 after SSH tunneling
        :param db_port: MySQL DB port, defaults to 3306
        :param ssh_port: SSH Tunnel port, defaults to 22
        """

        super().__init__()
        self.error_state = True  # Setting this to true here to suppress prints in case of int() TypeErrors
        self.server = None
        self.last_connected_time = None

        self.ssh_creds = {
            'ssh_host': ssh_host,
            'ssh_port': int(ssh_port),
            'ssh_username': ssh_username,
            'pkey_path': pkey_path
        }

        self.db_creds = {
            'db_name': db_name,
            'db_bind_address': db_bind_address,
            'db_host': db_host,
            'db_mysql_port': int(db_port),
            'db_user': db_user,
            'db_password': db_password
        }
        self.error_state = False
        self._validate(*args, **kwargs)

        self._open_ssh_tunnel()
        self._connect_to_db()

    def _validate(self, *args, **kwargs):
        if args:
            warn(f'Unexpected arguments passed to database: {args}', ParameterWarning)

        if kwargs:
            warn(f'Unexpected arguments passed to database: {kwargs}', ParameterWarning)

        missing_params = []
        for k, v in self.ssh_creds.items():
            if not v:
                missing_params.append(k)

        for k, v in self.db_creds.items():
            if not v:
                missing_params.append(k)

        if missing_params:
            self.error_state = True
            raise TypeError(f'Database instance missing params: {missing_params}')

        if not path.isfile(self.ssh_creds['pkey_path']):
            self.error_state = True
            raise IOError(f"{self.ssh_creds['pkey_path']} is not a valid file."
                          f" Make sure you have provided the absolute path")

    def _open_ssh_tunnel(self):
        connection_success = False

        while not connection_success:
            try:
                self.server = SSHTunnelForwarder(
                    (self.ssh_creds['ssh_host'], self.ssh_creds['ssh_port']),
                    ssh_username=self.ssh_creds['ssh_username'],
                    ssh_pkey=self.ssh_creds['pkey_path'],
                    remote_bind_address=(
                        self.db_creds['db_bind_address'], self.db_creds['db_mysql_port']
                    ),
                )
                connection_success = True
            except KeyboardInterrupt:
                self.close()

        self.server.start()

    def _connect_to_db(self):
        connection_success = False

        while not connection_success:
            try:
                self.conn = mysql_connect(
                    user=self.db_creds['db_user'],
                    passwd=self.db_creds['db_password'],
                    host=self.db_creds['db_host'],
                    database=self.db_creds['db_name'],
                    port=self.server.local_bind_port
                )
                connection_success = True
                self.cur = self.conn.cursor()
                self.last_connected_time = time()
            except KeyboardInterrupt:
                self.close()
