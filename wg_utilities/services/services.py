from requests import post
from warnings import warn


def slack(webhook_url: str, m: str):
    """Send a Slack message to a Slackbot

    :param webhook_url: Webhook of Slackbot
    :param m: The message
    """

    post(webhook_url, headers={'Content-Type': 'application/json'}, json={'text': m})


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
