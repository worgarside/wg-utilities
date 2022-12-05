"""Unit Tests for the `wg_utilities.functions.json.traverse_dict` function."""
from __future__ import annotations

from json import dumps, loads
from logging import ERROR
from re import sub
from unittest.mock import ANY

from pytest import LogCaptureFixture, mark, raises

from conftest import (
    random_nested_json,
    random_nested_json_with_arrays,
    random_nested_json_with_arrays_and_stringified_json,
)
from wg_utilities.functions import traverse_dict
from wg_utilities.functions.json import JSONObj, JSONVal, TargetProcessorFunc


def _generate_single_key_dict(_depth: int = 0, max_depth: int = 5) -> JSONObj:
    """Recursively generates a deep dictionary with single keys in places.

    Args:
        _depth (int): The current depth of the recursion. Defaults to 0.
        max_depth (int): The maximum depth of the recursion. Defaults to 5.

    Returns:
        JSONObj: The generated dictionary.
    """
    if _depth <= max_depth:
        return {
            "siblingKey": {
                # This niblingKey should be removed, as it has no siblings
                "niblingKey": _generate_single_key_dict(
                    _depth=_depth + 1, max_depth=max_depth
                ),
            },
            "adjacentKey": {
                # These keys should not be removed, as they have siblings
                "niblingKey": _generate_single_key_dict(
                    _depth=_depth + 1, max_depth=max_depth
                ),
                "innerKey": "adjacentInnerValue",
            },
            "outerKey": {
                # This innerKey should be removed, as it has no siblings
                "innerKey": "innerValue"
            },
        }

    return {
        "adjacentKey": {
            "niblingKey": None,
            # This innerKey should not be removed, as it has a sibling
            "innerKey": "adjacentInnerValue",
        },
        "outerKey": {
            # This innerKey should be removed, as it has no siblings
            "innerKey": "innerValue"
        },
    }


def test_empty_dict_doesnt_raise_exception() -> None:
    """Test that an empty dict doesn't raise an exception."""
    in_dict: JSONObj = {}
    traverse_dict(
        in_dict,
        target_type=str,
        target_processor_func=lambda value, dict_key=None, list_index=None: value,
    )

    # pylint: disable=use-implicit-booleaness-not-comparison
    assert in_dict == {}


@mark.parametrize(  # type: ignore[misc]
    "in_dict,target_type,target_processor_func,expected",
    [
        (
            {
                "key": "value",
                "key2": "value2",
                "key3": 3,
            },
            str,
            lambda value, dict_key=None, list_index=None: value.upper(),
            {
                "key": "VALUE",
                "key2": "VALUE2",
                "key3": 3,
            },
        ),
        (
            {
                "key": "value",
                "key2": b"value2",
                "key3": 3,
            },
            bytes,
            lambda value, dict_key=None, list_index=None: value.decode().upper(),
            {
                "key": "value",
                "key2": "VALUE2",
                "key3": 3,
            },
        ),
        (
            {
                "key": "value",
                "key2": b"value2",
                "key3": 3,
            },
            (str, bytes),
            lambda value, dict_key=None, list_index=None: (
                value.decode() if isinstance(value, bytes) else value
            ).upper(),
            {
                "key": "VALUE",
                "key2": "VALUE2",
                "key3": 3,
            },
        ),
        (
            {
                "key": "value",
                "key2": b"value2",
                "key3": {
                    "key": b"value",
                    "key2": b"value2",
                    "key3": 3,
                },
            },
            (str, bytes),
            lambda value, dict_key=None, list_index=None: (
                value.decode() if isinstance(value, bytes) else value
            ).upper(),
            {
                "key": "VALUE",
                "key2": "VALUE2",
                "key3": {
                    "key": "VALUE",
                    "key2": "VALUE2",
                    "key3": 3,
                },
            },
        ),
        (
            random_nested_json(),
            bool,
            lambda value, dict_key=None, list_index=None: str(value)[::-1].upper(),
            loads(
                dumps(random_nested_json())
                .replace("true", '"EURT"')
                .replace("false", '"ESLAF"')
            ),
        ),
    ],
)
def test_varying_inputs_processed_as_expected(
    in_dict: JSONObj,
    target_type: type[object] | tuple[type[object], ...],
    target_processor_func: TargetProcessorFunc,
    expected: JSONObj,
) -> None:
    """Test various lists with different types and processor functions."""

    traverse_dict(
        in_dict,
        target_type=target_type,
        target_processor_func=target_processor_func,
    )

    assert in_dict == expected


@mark.parametrize(  # type: ignore[misc]
    ",".join(
        [
            "in_dict",
            "target_type",
            "target_processor_func",
            "exception_type",
            "exception_message",
            "expected",
        ]
    ),
    [
        (
            {"a": "b", "c": 1, 2: 3, "d": "e", "f": "g"},
            (str, int),
            lambda value, dict_key=None, list_index=None: value.upper(),
            AttributeError,
            "'int' object has no attribute 'upper'",
            {"a": "B", "c": 1, 2: 3, "d": "e", "f": "g"},
        ),
        (
            {"a": 3, "b": 2, "c": 1, "d": 0, "e": 3, "f": 2, "g": 1, "h": 0},
            int,
            lambda value, dict_key=None, list_index=None: 1 / value,
            ZeroDivisionError,
            "division by zero",
            {"a": 1 / 3, "b": 1 / 2, "c": 1, "d": 0, "e": 3, "f": 2, "g": 1, "h": 0},
        ),
        (
            {
                "a": ("a", "b", "c"),
                "b": [1, 2, 3],
                "c": [4, 5],
                "d": [6, 7, 8],
                "e": [9, 10],
            },
            list,
            lambda value, dict_key=None, list_index=None: [
                value[0],
                value[1],
                value[2] + 1,
            ],
            IndexError,
            "list index out of range",
            {
                "a": ("a", "b", "c"),
                "b": [1, 2, 4],
                "c": [4, 5],
                "d": [6, 7, 8],
                "e": [9, 10],
            },
        ),
        (
            random_nested_json(),
            str,
            lambda value, dict_key=None, list_index=None: value[3],
            IndexError,
            "string index out of range",
            ANY,  # not worth calculating the expected value
        ),
    ],
)
def test_exceptions_are_raised_correctly(
    in_dict: JSONObj,
    target_type: type[JSONVal] | tuple[type[JSONVal], ...],
    target_processor_func: TargetProcessorFunc,
    exception_type: type[Exception],
    exception_message: str,
    expected: JSONObj,
) -> None:
    """Test that exceptions are raised correctly for varying inputs."""

    with raises(exception_type) as exc_info:
        traverse_dict(
            in_dict,
            target_type=target_type,
            target_processor_func=target_processor_func,
            pass_on_fail=False,
        )

    assert str(exc_info.value) == exception_message
    assert in_dict == expected


@mark.parametrize(  # type: ignore[misc]
    ",".join(
        [
            "in_dict",
            "target_type",
            "target_processor_func",
            "exception_type",
            "exception_message",
            "exception_keys",
            "expected",
        ]
    ),
    [
        (
            {"a": "b", "c": 1, 2: 3, "d": "e", "f": "g"},
            (str, int),
            lambda value, dict_key=None, list_index=None: value.upper(),
            AttributeError,
            "'int' object has no attribute 'upper'",
            ["c", 2],
            {"a": "B", "c": 1, 2: 3, "d": "E", "f": "G"},
        ),
        (
            {"a": 3, "b": 2, "c": 1, "d": 0, "e": 3, "f": 2, "g": 1, "h": 0},
            int,
            lambda value, dict_key=None, list_index=None: 1 / value,
            ZeroDivisionError,
            "division by zero",
            ["d", "h"],
            {
                "a": 1 / 3,
                "b": 1 / 2,
                "c": 1,
                "d": 0,
                "e": 1 / 3,
                "f": 1 / 2,
                "g": 1,
                "h": 0,
            },
        ),
        (
            {
                "a": ("a", "b", "c"),
                "b": [1, 2, 3],
                "c": [4, 5],
                "d": [6, 7, 8],
                "e": [9, 10],
            },
            list,
            lambda value, dict_key=None, list_index=None: [
                value[0],
                value[1],
                value[2] + 1,
            ],
            IndexError,
            "list index out of range",
            ["c", "e"],
            {
                "a": ("a", "b", "c"),
                "b": [1, 2, 4],
                "c": [4, 5],
                "d": [6, 7, 9],
                "e": [9, 10],
            },
        ),
        (
            random_nested_json(),
            str,
            lambda value, dict_key=None, list_index=None: value[3],
            IndexError,
            "string index out of range",
            [
                "cage",
                "pick",
                "opportunity",
                "curious",
                "travel",
                "closer",
                "sing",
                "arm",
                "wish",
                "split",
                "third",
            ],
            loads(
                sub(
                    r": \"[a-z]{3}([a-z])[a-z]*\"",
                    r': "\1"',
                    dumps(random_nested_json()),
                )
            ),
        ),
    ],
)
def test_exceptions_are_logged_correctly(
    in_dict: JSONObj,
    target_type: type[JSONVal] | tuple[type[JSONVal], ...],
    target_processor_func: TargetProcessorFunc,
    exception_type: type[Exception],
    exception_message: str,
    exception_keys: list[str],
    expected: JSONObj,
    caplog: LogCaptureFixture,
) -> None:
    """Test that exceptions are logged correctly for varying inputs."""

    traverse_dict(
        in_dict,
        target_type=target_type,
        target_processor_func=target_processor_func,
        log_op_func_failures=True,
    )

    assert in_dict == expected
    assert all(r.levelno == ERROR for r in caplog.records)

    log_records = [r.message for r in caplog.records]
    expected_exc_instance = exception_type(exception_message)
    for k in exception_keys:
        expected_message = (
            f"Unable to process item with key {k}: " f"{expected_exc_instance!r}"
        )
        assert expected_message in log_records
        log_records.remove(expected_message)

    # Check that no other log records were created
    assert len(log_records) == 0


def test_single_keys_are_removed_as_expected_one_key() -> None:
    """Test that any single keys are removed from the dict.

    This test removes a single key value from the dict.
    """

    in_dict = _generate_single_key_dict()

    traverse_dict(
        in_dict,
        target_type=str,
        target_processor_func=lambda v, dict_key=None, list_index=None: v.upper(),
        single_keys_to_remove=["innerKey"],
        log_op_func_failures=True,
    )

    def _traverse(test_dict: JSONObj, _parent_key: str | None = None) -> None:
        for k, v in test_dict.items():
            if isinstance(v, dict):
                _traverse(v, _parent_key=k)
            else:
                # Avoid the start/end cases for simplicity
                if _parent_key is not None and v is not None:
                    assert (
                        _parent_key == "niblingKey"
                        and k == "outerKey"
                        and v == "INNERVALUE"
                    ) or (
                        _parent_key == "adjacentKey"
                        and k == "innerKey"
                        and v == "ADJACENTINNERVALUE"
                    )

    _traverse(in_dict)


def test_single_keys_are_removed_as_expected_two_keys() -> None:
    """Test that any single keys are removed from the dict.

    This test removes two key values from the dict.
    """

    in_dict = _generate_single_key_dict()

    # This is to prove that the assertion at the bottom of the test is correct
    assert '{"siblingKey": {"niblingKey"' in dumps(in_dict)
    assert '"outerKey": {"innerKey":' in dumps(in_dict)

    traverse_dict(
        in_dict,
        target_type=str,
        target_processor_func=lambda v, dict_key=None, list_index=None: v.upper(),
        single_keys_to_remove=["innerKey", "niblingKey"],
        log_op_func_failures=True,
    )

    def _traverse(test_dict: JSONObj, _parent_key: str | None = None) -> None:
        for k, v in test_dict.items():
            if isinstance(v, dict):
                _traverse(v, _parent_key=k)
            else:

                # Avoid the start/end cases for simplicity
                if _parent_key is not None and v is not None:
                    assert (
                        (
                            _parent_key == "niblingKey"
                            and k == "outerKey"
                            and v == "INNERVALUE"
                        )
                        or (
                            # This has added from the previous test, as `niblingKey`
                            # has been removed
                            _parent_key == "siblingKey"
                            and k == "outerKey"
                            and v == "INNERVALUE"
                        )
                        or (
                            _parent_key == "adjacentKey"
                            and k == "innerKey"
                            and v == "ADJACENTINNERVALUE"
                        )
                    )

    _traverse(in_dict)

    assert '{"siblingKey": {"niblingKey"' not in dumps(in_dict)
    assert '"outerKey": {"innerKey":' not in dumps(in_dict)


def test_nested_lists_processed_correctly() -> None:
    """Test that nested lists are processed correctly."""

    in_dict: JSONObj = {
        "a": ["a", "b", "c"],
        "b": [1, 2, 3],
        "c": [4, 5],
        "d": [6, 7, 8],
        "e": [9, 10],
    }

    traverse_dict(
        in_dict,
        target_type=list,
        target_processor_func=lambda value, dict_key=None, list_index=None: value[::-1],
        log_op_func_failures=True,
    )

    assert in_dict == {
        "a": ["c", "b", "a"],
        "b": [3, 2, 1],
        "c": [5, 4],
        "d": [8, 7, 6],
        "e": [10, 9],
    }


def test_complex_object() -> None:
    """Test a complex object to ensure all values are found."""

    in_dict = random_nested_json_with_arrays()

    traverse_dict(
        in_dict,
        target_type=bool,
        target_processor_func=lambda value, dict_key=None, list_index=None: "YES"
        if value
        else "NO",
        log_op_func_failures=True,
    )

    assert dumps(in_dict) == dumps(random_nested_json_with_arrays()).replace(
        "true", '"YES"'
    ).replace("false", '"NO"')


def test_that_new_dicts_are_handled_correctly() -> None:
    """Test that any new dictionaries are also traversed.

    i.e. when the `target_processor_func` returns a dictionary, that new dict should
    be traversed and processed as normal.
    """

    in_dict = random_nested_json_with_arrays_and_stringified_json()

    assert "\\" in dumps(in_dict)

    traverse_dict(
        in_dict,
        target_type=str,
        target_processor_func=lambda value, dict_key=None, list_index=None: loads(
            value
        ),
        log_op_func_failures=True,
    )

    # Check the stringified JSON has been replaced with a dict
    assert "\\" not in dumps(in_dict)

    traverse_dict(
        in_dict,
        target_type=bool,
        target_processor_func=lambda value, dict_key=None, list_index=None: "YES"
        if value
        else "NO",
        log_op_func_failures=True,
    )

    assert dumps(in_dict) == dumps(
        random_nested_json_with_arrays_and_stringified_json()
    ).replace("true", '"YES"').replace("false", '"NO"').replace("\\", "").replace(
        '"{', "{"
    ).replace(
        '}"', "}"
    )


def test_single_keys_of_target_type_have_exceptions_logged(
    caplog: LogCaptureFixture,
) -> None:
    """Test that exceptions are logged for the target func.

    If the value is from a single key which has been removed, it should be processed as
    normal and any errors in the processing function should be logged.
    """

    in_dict: JSONObj = {
        "a": {
            "key": "good value",
        },
        "b": {
            "key": "bad value",
        },
        "c": {
            "key": "too short",
        },
        "d": {"key": "long enough"},
    }

    traverse_dict(
        in_dict,
        target_type=str,
        target_processor_func=lambda value, dict_key=None, list_index=None: value[9],
        log_op_func_failures=True,
        single_keys_to_remove=["key"],
    )

    assert in_dict == {"a": "e", "b": "bad value", "c": "too short", "d": "g"}

    log_records = [r.message for r in caplog.records]
    expected_exc_instance = IndexError("string index out of range")
    for k in ["b", "c"]:
        expected_message = (
            f"Unable to process item with key {k}: " f"{expected_exc_instance!r}"
        )
        assert expected_message in log_records
        log_records.remove(expected_message)

    # Check that no other log records were created
    assert len(log_records) == 0


def test_single_keys_of_target_type_have_exceptions_raised(
    caplog: LogCaptureFixture,
) -> None:
    """Test that exceptions are raised for the target func.

    If the value is from a single key which has been removed, it should be processed as
    normal and any errors in the processing function should be raised.
    """

    in_dict: JSONObj = {
        "a": {
            "key": "good value",
        },
        "b": {
            "key": "bad value",
        },
        "c": {
            "key": "too short",
        },
        "d": {"key": "long enough"},
    }

    with raises(IndexError) as exc_info:
        traverse_dict(
            in_dict,
            target_type=str,
            target_processor_func=lambda v, dict_key=None, list_index=None: v[9],
            log_op_func_failures=True,
            pass_on_fail=False,
            single_keys_to_remove=["key"],
        )

    assert isinstance(exc_info.value, IndexError)
    assert str(exc_info.value) == "string index out of range"

    assert in_dict == {
        "a": "e",
        "b": {"key": "bad value"},
        "c": {"key": "too short"},
        "d": {"key": "long enough"},
    }

    assert len(caplog.records) == 1
    assert caplog.records[0].message == (
        f"Unable to process item with key b: " f"{exc_info.value!r}"
    )


@mark.parametrize(  # type: ignore[misc]
    "in_dict,target_type,target_processor_func,expected",
    [
        (
            {
                "key": "value",
                "key2": "value2",
                "key3": 3,
            },
            str,
            lambda value, dict_key=None, list_index=None: value.upper()
            if dict_key == "key"
            else value,
            {
                "key": "VALUE",
                "key2": "value2",
                "key3": 3,
            },
        ),
        (
            {
                "key": "value",
                "key2": b"value2",
                "key3": 3,
                "key4": b"value4",
            },
            bytes,
            lambda value, dict_key=None, list_index=None: value.decode().upper()
            if dict_key == "key4"
            else value,
            {
                "key": "value",
                "key2": b"value2",
                "key3": 3,
                "key4": "VALUE4",
            },
        ),
        (
            random_nested_json(),
            bool,
            lambda value, dict_key=None, list_index=None: str(value)[::-1].upper()
            if dict_key in ("pretty", "effort")
            else value,
            loads(
                dumps(random_nested_json())
                .replace('"pretty": true', '"pretty": "EURT"')
                .replace('"effort": true', '"effort": "EURT"')
                # False isn't in the dict for these keys
            ),
        ),
    ],
)
def test_dict_key_parameter_for_target_processor_func(
    in_dict: JSONObj,
    target_type: type[object] | tuple[type[object], ...],
    target_processor_func: TargetProcessorFunc,
    expected: JSONObj,
) -> None:
    """Test that the dict key is passed to the target processor func.

    The dict key should be passed to the target processor func as the second parameter.
    """

    traverse_dict(
        in_dict,
        target_type=target_type,
        target_processor_func=target_processor_func,
        log_op_func_failures=True,
        pass_on_fail=False,
    )

    assert in_dict == expected
