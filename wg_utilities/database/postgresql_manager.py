#!/usr/bin/env python
"""Provides the PostgreSQLManager class to connect to a PostgreSQL instance"""
from psycopg2 import connect
from sqlalchemy.engine.url import URL

from ._database import Database

__author__ = 'Will Garside'
__email__ = 'worgarside@gmail.com'
__status__ = 'Production'


class PostgreSQLManager(Database):
    """Extension of the Database class specifically for connecting to a PostgreSQL instance"""

    def setup(self):
        """Setup the SSH Tunnel and Database connection"""
        self.dialect = 'postgresql'
        self.required_creds = {'db_user', 'db_password', 'db_name'}
        self.db_port = 5432 if not self.db_port else self.db_port

    def connect_to_db(self):
        """Open the connection to the database"""

        self.conn = connect(URL(
            drivername=self.dialect,
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).__str__())
        self.cur = self.conn.cursor()
