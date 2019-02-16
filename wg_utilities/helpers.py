from requests import post
from warnings import warn
from os import path


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
