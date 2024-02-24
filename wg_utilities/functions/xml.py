"""Helper functions specifically for parsing/manipulating XML."""

from __future__ import annotations

from logging import DEBUG, getLogger

from lxml import etree

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


def get_nsmap(
    *,
    root: etree._Element | None = None,
    xml_doc: str | None = None,
    warn_on_defaults: bool = False,
) -> dict[str, str]:
    """Get the namespace map for an XML document.

    Args:
        root (Element): an lxml Element from an XML document
        xml_doc (str): a raw XML document
        warn_on_defaults (bool): log a warning when an empty prefix is found and converted to a default value

    Returns:
        dict: a namespace mapping for the provided XML

    Raises:
        ValueError: if neither argument is provided
    """
    if root is None:
        if xml_doc is None:
            raise ValueError("One of `root` or `xml_doc` should be non-null")

        root = etree.fromstring(xml_doc.encode())  # noqa: S320

    nsmap = {}
    default_count = 0
    processed_urls = set()

    prefix: str
    url: str
    for prefix, url in root.xpath(  # type: ignore[misc,assignment,union-attr]
        "//namespace::*",
    ):
        if url in processed_urls:
            continue

        if prefix:
            nsmap[prefix] = url
        else:
            default_prefix = f"default_{default_count}"
            default_count += 1
            if warn_on_defaults:
                LOGGER.warning(
                    "Adding namespace url `%s` with prefix key `%s`",
                    url,
                    default_prefix,
                )

            nsmap[default_prefix] = url

        processed_urls.add(url)

    return nsmap
