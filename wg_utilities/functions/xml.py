"""Helper functions specifically for parsing/manipulating XML"""
from logging import getLogger, DEBUG
from lxml.etree import fromstring

from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


def get_nsmap(*, root=None, xml_doc=None, warn_on_defaults=False):
    """Get the namespace map for an XML document

    Args:
        root (Element): an lxml Element from an XML document
        xml_doc (str): a raw XML document
        warn_on_defaults (bool): log a warning when an empty prefix is found and
         converted to a default value

    Returns:
        dict: a namespace mapping for the provided XML

    Raises:
        ValueError: if neither argument is provided
    """
    if not (root or xml_doc):
        raise ValueError("One of `root` or `xml_doc` should be non-null")

    root = root or fromstring(xml_doc.encode())
    nsmap = {}

    default_count = 0
    processed_urls = set()
    for prefix, url in root.xpath("//namespace::*"):
        if url in processed_urls:
            continue

        if prefix is None:
            prefix = f"default_{default_count}"
            default_count += 1
            if warn_on_defaults:
                LOGGER.warning(
                    "Adding namespace url `%s` with prefix key `%s`", url, prefix
                )

        nsmap[prefix] = url
        processed_urls.add(url)

    return nsmap
