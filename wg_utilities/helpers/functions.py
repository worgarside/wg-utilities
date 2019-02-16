from requests import post
from warnings import warn
from os import path
from sys import stdout
from wg_utilities.references.constants import RETRIABLE_EXCEPTIONS, RETRIABLE_STATUS_CODES
from random import random
from time import sleep
from googleapiclient.errors import HttpError
from typing import Callable, Union


def pb_notify(m: str = None, t: str = None, token: str = None):
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


def get_envfile(abs_file_path: str, project_name: str):
    """Returns the path to the project's envfile

    :param abs_file_path: The path to the source file - should be `path.abspath(__file__)`
    :param project_name: Name of the project
    :return: File path to .env
    """
    curr_file_dir, _ = path.split(abs_file_path)
    project_dir = curr_file_dir[:curr_file_dir.find(project_name) + len(project_name)] + '/'
    envfile = f'{project_dir}secret_files/.env'

    if not path.isfile(envfile):
        raise FileNotFoundError(f'Unable to find {envfile}')

    return envfile


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
