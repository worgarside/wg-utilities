"""Unit Tests for the `flatten_dict` function."""

from __future__ import annotations

from json import loads
from os import listdir
from pathlib import Path

import pytest

from wg_utilities.functions import flatten_dict

INPUT_OUTPUT_COMBOS = [
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
        {"one": 1, "two.three": 3, "two.four": 4, "five.six": 6},
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
        {"one": 1, "two.3": 3, "two.four": 4, "five.two.six": 6},
    ),
    (
        {
            "one": {
                "two": {
                    "three": {
                        "four": {"five": {"six": {"seven": 7, "eight": 8, "nine": 9}}}
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
]


# It's easier to store large objects in flat files, so...
_file: str
for _file in listdir(_json_dir := Path(__file__).parents[2] / "flat_files" / "json"):
    if _file.endswith("_flattened.json"):
        continue

    if (
        _file.endswith(".json")
        and (
            _flattened_path := _json_dir / _file.replace(".json", "_flattened.json")
        ).is_file()
    ):
        _original_payload = loads((_json_dir / _file).read_text(encoding="utf-8"))

        # I used this JSFiddle to create the flat JSON: https://jsfiddle.net/S2hsS
        _flattened_payload = loads(_flattened_path.read_text())

        INPUT_OUTPUT_COMBOS.append((_original_payload, _flattened_payload))


@pytest.mark.parametrize(
    ("user_input", "want"),
    INPUT_OUTPUT_COMBOS,
)
def test_flatten_dict_with_varying_input_dicts(
    user_input: dict[str, object], want: dict[str, object]
) -> None:
    """Test that the `flatten_dict` function handles various dictionaries correctly."""

    assert flatten_dict(user_input) == want


@pytest.mark.parametrize(
    ("user_input", "want"),
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


@pytest.mark.parametrize(
    ("user_input", "want"),
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


@pytest.mark.parametrize(
    ("user_input", "want"),
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
