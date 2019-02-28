from http.client import NotConnected, IncompleteRead, ImproperConnectionState, CannotSendRequest, CannotSendHeader, \
    ResponseNotReady, BadStatusLine
from httplib2 import HttpLib2Error
from wg_utilities.helpers.dict_to_object import DictToObject

HASS_DIR = '/home/hass/.homeassistant/'
INDENT = '    '

HOMEASSISTANT = '.homeassistant'
WGUTILS = 'wg-utils'
WGSCRIPTS = 'wg-scripts'

BS4_PARSER = 'html.parser'

RETRIABLE_EXCEPTIONS = (HttpLib2Error, IOError, NotConnected,
                        IncompleteRead, ImproperConnectionState,
                        CannotSendRequest, CannotSendHeader,
                        ResponseNotReady, BadStatusLine)

RETRIABLE_STATUS_CODES = (500, 502, 503, 504)

OS = DictToObject({
    'WINDOWS': 'Windows',
    'MAC_OS': 'Darwin',
    'LINUX': 'Linux',
    'JAVA': 'Java'
})
