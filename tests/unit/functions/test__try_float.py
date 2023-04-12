"""Unit Tests for the `try_float` function."""

from __future__ import annotations

from typing import Any

from pytest import mark

from wg_utilities.functions import try_float


@mark.parametrize(
    "user_input,should_convert",
    [
        ("1", True),
        ("1.0", True),
        (1.1, True),
        (True, True),
        (False, True),
        (None, False),
        ("", False),
        ("a", False),
        ("1a", False),
        (1e1, True),
        ("1e1", True),
        ([1, 2, 3], False),
        ({"a": 1}, False),
        (try_float, False),
        (ValueError("test"), False),
    ],
)
def test_try_float_with_varying_input(user_input: Any, should_convert: bool) -> None:
    """Test a whole set of different inputs to the `try_float` function.

    The test is run twice, once with a default value and once without.
    """

    # With default
    assert try_float(user_input, user_input) == (
        float(user_input) if should_convert else user_input
    )

    # Without default
    assert try_float(user_input) == (float(user_input) if should_convert else 0.0)
