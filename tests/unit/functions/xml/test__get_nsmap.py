"""Unit Tests for `wg_utilities.functions.xml`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pytest import LogCaptureFixture, raises

from wg_utilities.functions.xml import get_nsmap

SAMPLE_XML_DOC = """
<root xmlns:h="http://www.w3.org/TR/html4/"
      xmlns:f="https://www.w3schools.com/furniture">
    <f:table>
        <f:name>IKEA Cardboard Table</f:name>
        <f:width>150</f:width>
        <f:length>75</f:length>
    </f:table>
    <h:table>
        <h:tr>
            <h:td>Apples</h:td>
            <h:td>Bananas</h:td>
        </h:tr>
    </h:table>
    <f:table>
        <f:name>African Coffee Table</f:name>
        <f:width>80</f:width>
        <f:length>120</f:length>
    </f:table>
    <f:table>
        <f:name>Bed</f:name>
        <f:width>1500</f:width>
        <f:length>1500</f:length>
    </f:table>
    <h:table>
        <h:tr>
            <h:td>Charlie</h:td>
            <h:td>Dave</h:td>
        </h:tr>
    </h:table>
</root>
""".strip()

SAMPLE_XML_DOC_NO_PREFIX = """
<root>
    <table xmlns="https://www.w3schools.com/furniture">
        <name>IKEA Cardboard Table</name>
        <width>150</width>
        <length>75</length>
    </table>
    <table xmlns="http://www.w3.org/TR/html4/">
        <tr>
            <td>Apples</td>
            <td>Bananas</td>
        </tr>
    </table>
    <table xmlns="https://www.w3schools.com/furniture">
        <name>African Coffee Table</name>
        <width>80</width>
        <length>120</length>
    </table>
    <table xmlns="https://www.w3schools.com/furniture">
        <name>Bed</name>
        <width>1500</width>
        <length>1500</length>
    </table>
    <table xmlns="http://www.w3.org/TR/html4/">
        <tr>
            <td>Charlie</td>
            <td>Dave</td>
        </tr>
    </table>
</root>
""".strip()


@patch("lxml.etree.fromstring")
def test_xml_doc_is_parsed_when_root_is_none(mock_fromstring: MagicMock) -> None:
    """Test that the XML document is parsed when the root is None."""

    get_nsmap(xml_doc=SAMPLE_XML_DOC)

    mock_fromstring.assert_called_once_with(SAMPLE_XML_DOC.encode())


def test_value_error_is_thrown_when_root_and_xml_doc_are_none() -> None:
    """Test that a ValueError is thrown when both root and xml_doc are None."""
    with raises(ValueError) as exc_info:
        get_nsmap()

    assert str(exc_info.value) == "One of `root` or `xml_doc` should be non-null"


def test_xml_doc_nsmap_extraction() -> None:
    """Test that the namespace map is extracted from the XML document."""

    nsmap = get_nsmap(xml_doc=SAMPLE_XML_DOC)

    assert nsmap == {
        "h": "http://www.w3.org/TR/html4/",
        "f": "https://www.w3schools.com/furniture",
        "xml": "http://www.w3.org/XML/1998/namespace",
    }


def test_xml_doc_nsmap_extraction_defaults(caplog: LogCaptureFixture) -> None:
    """Test that namespaces with no prefix are given default values.

    If a namespace has no prefix, it is given a default value of `default_{n}`. This
    test ensures that the default values are generated correctly: `n` should increment
    each time a new namespace is found, and known namespaces should not be re-added.
    """

    nsmap = get_nsmap(xml_doc=SAMPLE_XML_DOC_NO_PREFIX, warn_on_defaults=True)

    assert nsmap == {
        "default_0": "https://www.w3schools.com/furniture",
        "default_1": "http://www.w3.org/TR/html4/",
        "xml": "http://www.w3.org/XML/1998/namespace",
    }

    assert len(caplog.records) == 2

    for i, record in enumerate(caplog.records):
        assert record.levelname == "WARNING"
        assert (
            record.message
            == f"Adding namespace url `{nsmap[f'default_{i}']}` with prefix key"
            f" `default_{i}`"
        )
