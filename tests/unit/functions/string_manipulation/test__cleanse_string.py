""""Unit Tests for `wg_utilities.functions.string_manipulation.cleanse_string`."""
from __future__ import annotations

from json import dumps
from re import sub

from pytest import mark

from tests.unit.functions import random_nested_json
from wg_utilities.functions import cleanse_string


@mark.parametrize(
    "in_str,expected",
    [
        ("   ", ""),
        ("@bcd3fgh!jk|MNØPQRST∪VWXYZ", "bcd3fghjkMNPQRSTVWXYZ"),  # noqa: RUF001
        ("abcdefghijABCDEFGHIJ1234567890", "abcdefghijABCDEFGHIJ1234567890"),
        ("!QAZ@WSX#EDC$RFV%TGB^YHN&UJM*IK<OL>?:P{}|", "QAZWSXEDCRFVTGBYHNUJMIKOLP"),
        (
            "!QAZ   @WSX#EDC$RFV%     TGB^YHN&UJM   *IK<O L > ?:P{}|",
            "QAZWSXEDCRFVTGBYHNUJMIKOLP",
        ),
        (
            "~/`1234567890-=qwertyuiop[]\\asdfghjkl;'zxcvbnm,./",
            "1234567890qwertyuiopasdfghjklzxcvbnm",
        ),
        (
            "~/`1234567890-=\nqwert\nyu  \n  iop[]\\asdfghjkl;'zxcvbnm,./",
            "1234567890qwertyuiopasdfghjklzxcvbnm",
        ),
        (
            "".join([chr(i) for i in range(0, 1000)]),
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        ),
    ],
)
def test_varying_inputs(in_str: str, expected: str) -> None:
    """Test that varying inputs are handled correctly."""

    assert cleanse_string(in_str) == expected


@mark.parametrize(
    "in_str,preserve_newlines,expected",
    [
        ("a\nb\nc\n", False, "abc"),
        ("a\nb\nc\n", True, "a\nb\nc\n"),
        ("a  \n  b  \n  c", False, "abc"),
        ("a  \n  b  \n  c", True, "a\nb\nc"),
        ("a\n\n\nb\n\n\nc", False, "abc"),
        ("a\n\n\nb\n\n\nc", True, "a\n\n\nb\n\n\nc"),
    ],
)
def test_newline_preservation(
    in_str: str, preserve_newlines: bool, expected: str
) -> None:
    """Test that newlines are preserved as expected."""

    assert cleanse_string(in_str, preserve_newlines=preserve_newlines) == expected


@mark.parametrize(
    # pylint: disable=unused-variable,undefined-variable
    "in_str,whitespace_amount,expected",
    [
        ("a b c", None, "abc"),
        ("a b c", 0, "a b c"),
        ("a b c", 1, "a b c"),
        ("a b c", 2, "a  b  c"),
        ("a  b  c", None, "abc"),
        ("a  b  c", 0, "a  b  c"),
        ("a  b  c", 1, "a b c"),
        ("a  b  c", 2, "a  b  c"),
        ("a  b  c", 3, "a   b   c"),
        ("a  b c", None, "abc"),
        ("a  b c", 0, "a  b c"),
        ("a  b c", 1, "a b c"),
        ("a  b c", 2, "a  b  c"),
        (
            (json_str := dumps(random_nested_json())),
            0,
            (
                alnum_json_whitespace := "".join(
                    c for c in json_str if c.isalnum() or c == " "
                )
            ),
        ),
        (
            json_str,
            1,
            sub(r"\s+", " ", alnum_json_whitespace),
        ),
        (
            json_str,
            None,
            alnum_json_whitespace.replace(" ", ""),
        ),
    ],
)
def test_whitespace_amounts(
    in_str: str, whitespace_amount: int | None, expected: str
) -> None:
    """Test preserving different amounts of spaces."""

    assert cleanse_string(in_str, whitespace_amount=whitespace_amount) == expected
