"""Unit Tests for the `flatten_dict` function."""
from __future__ import annotations

from pytest import mark

from tests.unit.functions import INPUT_OUTPUT_COMBOS
from wg_utilities.functions import flatten_dict


@mark.parametrize(  # type: ignore[misc]
    "user_input,want",
    INPUT_OUTPUT_COMBOS,
)
def test_flatten_dict_with_varying_input_dicts(
    user_input: dict[str, object], want: dict[str, object]
) -> None:
    """Test that the `flatten_dict` function handles various dictionaries correctly."""

    assert flatten_dict(user_input) == want


@mark.parametrize(  # type: ignore[misc]
    "user_input,want",
    INPUT_OUTPUT_COMBOS,
)
def test_flatten_dict_uses_correct_join_char(
    user_input: dict[str, object], want: dict[str, object]
) -> None:
    """Test that the `flatten_dict` function joins all keys with the correct character.

    The same character should be used no matter how deeply nested the keys are.
    """

    want_with_join_char = {k.replace(".", "-"): v for k, v in want.items()}

    assert flatten_dict(user_input, join_char="-") == want_with_join_char


@mark.parametrize(  # type: ignore[misc]
    "user_input,want",
    [
        ({}, {}),
        (
            {
                "one": 1,
                "two": {
                    "three": 3,
                    "four": 4,
                },
                "five": {"six": 6},
            },
            {
                "one": 1,
                "two": {
                    "three": 3,
                    "four": 4,
                },
                "five.six": 6,
            },
        ),
        (
            {
                "one": 1,
                "two": {
                    3: 3,
                    "four": 4,
                },
                "five": {"two": {"six": 6}},
            },
            {
                "one": 1,
                "two": {
                    3: 3,
                    "four": 4,
                },
                "five.two": {"six": 6},
            },
        ),
        (
            {
                "one": {
                    "two": {
                        "three": {
                            "four": {
                                "five": {"six": {"seven": 7, "eight": 8, "nine": 9}}
                            }
                        }
                    }
                }
            },
            {
                "one.two": {
                    "three": {
                        "four": {"five": {"six": {"seven": 7, "eight": 8, "nine": 9}}}
                    }
                }
            },
        ),
    ],
)
def test_exclude_keys_with_exact_keys_false(
    user_input: dict[str, object], want: dict[str, object]
) -> None:
    """Test that when `exact_keys` is False, the keys chosen for exclusion are excluded.

    In this test, the only key to exclude is `"two"`, which means any descendent of a
    `"two"` key should not be flattened.
    """

    assert flatten_dict(user_input, exclude_keys=["two"], exact_keys=False) == want


@mark.parametrize(  # type: ignore[misc]
    "user_input,want",
    [
        ({}, {}),
        (
            {
                "one": 1,
                "two": {
                    "three": 3,
                    "four": 4,
                },
                "five": {"six": 6},
            },
            {
                "one": 1,
                "two": {
                    "three": 3,
                    "four": 4,
                },
                "five.six": 6,
            },
        ),
        (
            {
                "one": 1,
                "two": {
                    3: 3,
                    "four": 4,
                },
                "five": {"two": {"six": 6}},
            },
            {
                "one": 1,
                "two": {
                    3: 3,
                    "four": 4,
                },
                "five.two.six": 6,  # <-- This line has changed
            },
        ),
        (
            {
                "one": {
                    "two": {
                        "three": {
                            "four": {
                                "five": {"six": {"seven": 7, "eight": 8, "nine": 9}}
                            }
                        }
                    }
                }
            },
            {
                "one.two.three.four.five.six.seven": 7,
                "one.two.three.four.five.six.eight": 8,
                "one.two.three.four.five.six.nine": 9,
            },
        ),
    ],
)
def test_exclude_keys_with_exact_keys_true(
    user_input: dict[str, object], want: dict[str, object]
) -> None:
    """Test that when `exact_keys` is False, the keys chosen for exclusion are excluded.

    In this test, the only key to exclude is `"two"`, which means any descendent of a
    *flattened* key `"two"` should not be flattened. This means that if a value is
    nested under `"five.two"` for example, it will still be flattened as it isn't an
    exact match.
    """

    assert flatten_dict(user_input, exclude_keys=["two"], exact_keys=True) == want
