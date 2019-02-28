# noinspection PyProtectedMember
from os import _exit as os_exit
from pandas import read_sql_query, DataFrame
from typing import Union, Iterable, List, Tuple, Dict


class Database(object):
    """Base database class to be extended when connecting to MySQL or PostgreSQL databases"""

    def __init__(self):
        self.conn = None
        self.cur = None
        self.error_state = False

    def query(self, sql: str, commit: bool = True):
        """Executes a query passed in by using the DatabaseManager object

        :param sql: The sql query to be executed by the Cursor object
        :param commit: Committing on queries can be disabled for rapid writing (e.g. q_one commit at end)
        :return: the Cursor object
        """

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

        df: DataFrame = read_sql_query(stmt, self.conn, index_col=index_col, coerce_float=coerce_float, params=params,
                                       parse_dates=parse_dates, chunksize=chunksize)
        return df

    def executemany(self, stmt: str, data):
        """Executes a query passed in by using the DatabaseManager object

        :param stmt: The query to be executed by the Cursor object
        :param data: The data to be processed
        :return: the Cursor object
        """

        self.cur.executemany(stmt, data)
        return self.cur

    def commit(self):
        """Commits all changes to database

        :return: the Cursor object
        """

        self.conn.commit()
        return self.cur

    def close(self, force_exit: bool = False):
        """Terminates the database connection

        :param force_exit: Tells the db to completely quit the program
        """
        self.__del__()
        if force_exit:
            os_exit(0)

    def __del__(self):
        """Overrides the close method for the cursor, and ensure proper disconnection from the database"""
        try:
            try:
                self.commit()
            except Exception as err:
                if not self.error_state:
                    print(f'Unable to commit before closing: {err}')
            self.conn.close()
            if not self.error_state:
                print('Connection closed.')
        except AttributeError:
            if not self.error_state:
                print('Unable to close connection.')
