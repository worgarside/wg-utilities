from os import path, system as os_system
from platform import system as plat_system
from random import random
from typing import Callable, Union

from googleapiclient.errors import HttpError
from sys import stdout
from time import sleep

from wg_utilities.references.constants import RETRIABLE_EXCEPTIONS, RETRIABLE_STATUS_CODES, OS


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
