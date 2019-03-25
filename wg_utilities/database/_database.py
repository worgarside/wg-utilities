#!/usr/bin/env python
"""Extendable Database class for connecting to different database types"""

from os import path
from typing import Union, Iterable, List, Tuple, Dict
from warnings import warn

from pandas import read_sql_query, DataFrame
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL

__author__ = 'Will Garside'
__email__ = 'worgarside@gmail.com'
__status__ = 'Production'


class Database(object):
    """Base database class to be extended when connecting to MySQL or PostgreSQL databases"""

    def __init__(self, ssh_host: str = None, ssh_port: int = 22, ssh_username: str = None, pkey_path: str = None,
                 db_name: str = None, db_bind_address: str = None, db_host: str = '127.0.0.1', db_port: int = None,
                 db_user: str = None, db_password: str = None, stubbed: bool = False, max_idle_time: int = 30):
        """Connects to a remote MySQL RDS though an SSH tunnel

        :param db_name: Name of the database to connect to
        :param ssh_host: Host IP of the SSH tunnel
        :param ssh_username: User for access to SSH tunnel
        :param pkey_path: Path to the .pem file containing the PKey
        :param db_bind_address: Binding address for the database
        :param db_user: MySQL username
        :param db_password: MySQL password
        :param db_host: Host IP for the database, usually 127.0.0.1 after SSH tunneling
        :param db_port: DB port
        :param ssh_port: SSH Tunnel port, defaults to 22
        :param max_idle_time: Maximum time connection can idle before being disconnected
        """
        self.conn = None
        self.cur = None
        self.server = None
        self.dialect = None
        self.driver = None

        self.error_state = False
        self.stubbed = stubbed
        self.max_idle_time = max_idle_time  # TODO: implement this!

        self.db_user = db_user
        self.db_password = db_password
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_bind_address = db_bind_address

        self.ssh_host = ssh_host
        self.ssh_port = int(ssh_port)
        self.ssh_username = ssh_username
        self.pkey_path = pkey_path

        self.required_creds = {}

        if self.stubbed:
            print('\033[31mWarning: Connection to \033[1m{}\033[31m is stubbed. '
                  'No data will be affected.\033[0m'.format(self.db_name))

        self.setup()
        self.validate_setup()
        self.connect_to_db()

    def setup(self):
        """Allows each database subclass to be setup differently according to the relevant dialect and driver"""
        pass

    def connect_to_db(self):
        """Placeholder method for the actual connection to the DB"""
        pass

    def validate_setup(self):
        """Validate the setup of the database: args, connections etc."""

        missing_params = [k for k, v in self.__dict__.items() if not v and k in self.required_creds]

        if missing_params:
            self.error_state = True
            raise TypeError('Database instance missing params: {}'.format(missing_params))

        if self.pkey_path and not path.isfile(self.pkey_path):
            self.error_state = True
            raise IOError("{} is not a valid file. "
                          "Make sure you have provided the absolute path".format(self.pkey_path))

    def query(self, sql: str, commit: bool = True):
        """Executes a query passed in by using the DatabaseManager object

        :param sql: The sql query to be executed by the Cursor object
        :param commit: Committing on queries can be disabled for rapid writing (e.g. q_one commit at end)
        :return: the Cursor object
        """
        if self.stubbed:
            return self.cur

        self.cur.execute(sql)
        if commit:
            self.commit()
        return self.cur

    def df_from_query(self, stmt: str, index_col: Union[Iterable[str], str] = None, coerce_float: bool = True,
                      params: Union[List, Tuple, Dict] = None, parse_dates: Union[List, Dict] = None,
                      chunksize: int = None):
        """Returns a pandas dataframe from an SQL query. All parameter defaults match those of read_sql_query.

        :param stmt:  The sql query to be executed by the Cursor object
        :param index_col: Column(s) to set as index(MultiIndex).
        :param coerce_float: Attempts to convert values of non-string, non-numeric objects (like decimal.Decimal) to
            floating point. Useful for SQL result sets.
        :param params: List of parameters to pass to execute method.  The syntax used to pass parameters is database
            driver dependent.
        :param parse_dates:
            - List of column names to parse as dates.
            - Dict of ``{column_name: format string}`` where format string is
              strftime compatible in case of parsing string times, or is one of
              (D, s, ns, ms, us) in case of parsing integer timestamps.
            - Dict of ``{column_name: arg dict}``, where the arg dict corresponds
              to the keyword arguments of :func:`pandas.to_datetime`
              Especially useful with databases without native Datetime support,
              such as SQLite.
        :param chunksize: If specified, return an iterator where `chunksize` is the number of rows to include in
            each chunk.
        :return: DataFrame object
        """

        if self.stubbed:
            return DataFrame()

        df = read_sql_query(stmt, self.conn, index_col=index_col, coerce_float=coerce_float, params=params,
                            parse_dates=parse_dates, chunksize=chunksize)
        return df

    def df_to_table(self, df: DataFrame, name: str, schema: str = None, if_exists: str = 'fail', index: bool = True,
                    index_label: Union[str, List] = None, chunksize: int = None, dtype: dict = None,
                    method: Union[None, str, callable] = None):
        """Write records stored in a DataFrame to a SQL database.

        :param df: DataFrame to convert
        :param name: Name of table to be created
        :param schema: Specify the schema (if database flavor supports this)
        :param if_exists: How to behave if the table already exists
        :param index: Write DataFrame index as a column. Uses index_label as the column name in the table.
        :param index_label: Column label for index column(s). If None is given (default) and index is True, then the
            index names are used. A sequence should be given if the DataFrame uses MultiIndex.
        :param chunksize: Rows will be written in batches of this size at a time. By default, all rows will be written
            at once.
        :param dtype: Specifying the datatype for columns. The keys should be the column names and the values should be
            the SQLAlchemy types or strings for the sqlite3 legacy mode.
        :param method: Controls the SQL insertion clause used:
            None : Uses standard SQL INSERT clause (one per row).
            ‘multi’: Pass multiple values in a single INSERT clause.
            callable with signature (pd_table, conn, keys, data_iter)
        """

        if self.stubbed:
            return

        if if_exists not in {None, 'fail', 'replace', 'append'}:
            warn('Parameter if_exists has invalid value: {}. '
                 'Should be one of {{None, \'fail\', \'replace\', \'append\'}}'.format(if_exists))
            if_exists = None

        if isinstance(method, str) and not method == 'multi':
            warn("Parameter method has invalid value: {}. Should be one of {{None, 'multi', callable}}".format(method))
            method = None

        engine = create_engine(
            URL(
                drivername='{}+{}'.format(self.dialect, self.driver),
                username=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.server.local_bind_port,
                database=self.db_name
            )
        )

        df.to_sql(name=name, con=engine, schema=schema, if_exists=if_exists, index=index, index_label=index_label,
                  chunksize=chunksize, dtype=dtype, method=method)

    def executemany(self, stmt: str, data):
        """Executes a query passed in by using the DatabaseManager object

        :param stmt: The query to be executed by the Cursor object
        :param data: The data to be processed
        :return: the Cursor object
        """

        if self.stubbed:
            return self.cur

        self.cur.executemany(stmt, data)
        return self.cur

    def commit(self):
        """Commits all changes to database

        :return: the Cursor object
        """

        self.conn.commit()
        return self.cur

    def disconnect(self, silent: bool = False):
        """Terminates the database connection
        :param silent: Disables final print
        """
        self.conn.close()
        if self.server:
            self.server = None
        if not silent:
            print('{} disconnected.'.format(self.db_name if self.db_name else 'Database'))
