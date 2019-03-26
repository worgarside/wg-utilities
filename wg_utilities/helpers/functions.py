from datetime import datetime
from json import dumps
from os import path
from os import system as os_system
from platform import system as plat_system
from random import random
from socket import gethostname
from sys import stdout
from time import sleep
from typing import Callable, Union

from googleapiclient.errors import HttpError

from wg_utilities.database.postgresql_manager import PostgreSQLManager
from wg_utilities.references.constants import OS
from wg_utilities.references.constants import RETRIABLE_EXCEPTIONS, RETRIABLE_STATUS_CODES


def log(db_creds=None, db_obj=None, script=None, description=None, text_content=None, json_content: dict = None,
        numeric_content=None, boolean_content=None):
    if not (db_creds or db_obj.conn):
        raise ValueError('Unable to log. No database arguments passed.')

    if not (description or text_content or json_content or numeric_content or boolean_content is not None):
        raise ValueError('No content passed to logger. No entry made.')

    db_obj = PostgreSQLManager(**db_creds) if not db_obj else db_obj

    if bool(db_obj.conn.closed):
        db_obj.connect_to_db()

    query = """INSERT INTO darillium.public.logs (source,
                                   timestamp,
                                   script,
                                   description,
                                   text_content,
                                   json_content,
                                   numeric_content,
                                   boolean_content)
    VALUES ('{}', TIMESTAMP '{}', '{}', '{}', '{}', '{}', {}, {})""".format(
        gethostname(),
        datetime.now(),
        script,
        description,
        text_content,
        dumps(json_content),
        numeric_content if numeric_content is not None else 'NULL',
        boolean_content if boolean_content is not None else 'NULL'
    )

    db_obj.query(query)


def output(m: str = ''):
    try:
        print(m)
        stdout.flush()
    except Exception as e:
        print(e)


def get_proj_dirs(abs_file_path: str, project_name: str):
    """Returns the path to the project's envfile

    :param abs_file_path: The path to the source file - should be `path.abspath(__file__)`
    :param project_name: Name of the project
    :return: Root project directory, secret files directory, and env file path
    """
    curr_file_dir, _ = path.split(abs_file_path)
    project_dir = curr_file_dir[:curr_file_dir.find(project_name) + len(project_name)] + '/'
    secret_files_dir = '{}secret_files/'.format(project_dir)
    env_file = '{}.env'.format(secret_files_dir)

    for loc in [project_dir, secret_files_dir, env_file]:
        if not path.exists(loc):
            raise ValueError('Unable to find {}'.format(loc))

    return project_dir, secret_files_dir, env_file


def exponential_backoff(func: Callable, max_retries: int = 10, retriable_exceptions: tuple = RETRIABLE_EXCEPTIONS,
                        retriable_status_codes: tuple = RETRIABLE_STATUS_CODES, max_backoff: Union[int, float] = 64,
                        output_flag: bool = True):
    retry = 0
    while retry < max_retries:
        try:
            return func()
        except HttpError as e:
            if e.resp.status in retriable_status_codes:
                error = 'A retriable HTTP error {:d} occurred:\n{}'.format(e.resp.status, e.content)
            else:
                raise
        except retriable_exceptions as e:
            error = 'A retriable error occurred: {}'.format(e)

        if error is not None:
            output(error) if output_flag else None
            retry += 1
            sleep_seconds = min(random() * (2 ** retry), max_backoff)
            output('Sleeping {:f} seconds and then retrying...'.format(sleep_seconds)) if output_flag else None
            sleep(sleep_seconds)


def clear_screen():
    os_system('cls') if plat_system() == OS.WINDOWS else os_system('clear')
