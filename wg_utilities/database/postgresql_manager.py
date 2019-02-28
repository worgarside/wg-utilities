from psycopg2 import connect as psql_connect
from ._database import Database


class PostgreSQLManager(Database):
    def __init__(self, url: str):
        """Creates a Cursor object for use throughout the program.

        :param url: The URL of the PostgreSQL instance
        """
        super().__init__()
        try:
            self.conn = psql_connect(url)
        except TypeError:
            exit(f'Invalid URL passed to DB Manager: {url}')
        self.commit()
        self.cur = self.conn.cursor()
