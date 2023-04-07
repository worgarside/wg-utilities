"""Functions for the functions tests."""
from __future__ import annotations

from tests.conftest import read_json_file
from wg_utilities.functions.json import JSONObj


def random_nested_json() -> JSONObj:
    """Return a random nested JSON object."""
    return read_json_file("random_nested.json")


def random_nested_json_with_arrays() -> JSONObj:
    """Return a random nested JSON object with lists as values."""
    return read_json_file("random_nested_with_arrays.json")


def random_nested_json_with_arrays_and_stringified_json() -> JSONObj:
    """Return a random nested JSON object with lists and stringified JSON.

    I've manually stringified the JSON and put it back into itself a couple of times
    for more thorough testing.

    Returns:
        JSONObj: randomly generated JSON
    """
    return read_json_file("random_nested_with_arrays_and_stringified_json.json")
