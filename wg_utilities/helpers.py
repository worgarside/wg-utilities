from requests import post
from warnings import warn


def pb_notify(t: str = None, m: str = None, token: str = None):
    if not t:
        warn('Notification title not set.')

    if not m:
        warn('Notification message not set.')

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
