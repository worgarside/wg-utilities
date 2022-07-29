"""Helper functions specifically for parsing/manipulating XML"""


from logging import DEBUG, getLogger
from typing import Dict, Optional

from lxml import etree

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


def get_nsmap(
    *,
    root: Optional[etree._Element] = None,
    xml_doc: Optional[str] = None,
    warn_on_defaults: bool = False,
) -> Dict[str, str]:
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

    root = root or etree.fromstring(xml_doc.encode())  # type: ignore
    nsmap = {}

    default_count = 0
    processed_urls = set()

    prefix: str
    url: str
    for prefix, url in root.xpath("//namespace::*"):  # type: ignore
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
