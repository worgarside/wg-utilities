from requests import post
from warnings import warn
from os import path
from sys import stdout
from wg_utilities.references.constants import RETRIABLE_EXCEPTIONS, RETRIABLE_STATUS_CODES
from random import random
from time import sleep
from googleapiclient.errors import HttpError
from typing import Callable, Union


def pb_notify(m: str = None, t: str = None, token: str = None, print_flag: bool = False):
    if print_flag:
        print(m)

    if not m:
        warn('Notification message not set.')

    if not t:
        warn('Notification title not set.')

    if not token:
        raise TypeError('PushBullet token not set, unable to send message.')

    post(
        'https://api.pushbullet.com/v2/pushes',
        headers={
            'Access-Token': token,
            'Content-Type': 'application/json'
        },
        json={
            'body': m,
            'title': t,
            'type': 'note'
        }
    )

    return True


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
    secret_files_dir = f'{project_dir}secret_files/'
    env_file = f'{secret_files_dir}.env'

    for loc in [project_dir, secret_files_dir, env_file]:
        if not path.exists(loc):
            raise ValueError(f'Unable to find {loc}')

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
