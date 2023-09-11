"""Unit Tests for the `wg_utilities.functions.json.process_list` function."""

from __future__ import annotations

from logging import ERROR
from unittest.mock import ANY, MagicMock, _Call, call, patch

import pytest

from wg_utilities.functions import process_list
from wg_utilities.functions.json import JSONVal, TargetProcessorFunc


def test_empty_list_doesnt_raise_exception() -> None:
    """Test that an empty list doesn't raise an exception."""

    in_list: list[JSONVal] = []

    process_list(
        in_list,
        target_type=str,
        target_processor_func=lambda value, **_: value,
        pass_on_fail=False,
    )

    # pylint: disable=use-implicit-booleaness-not-comparison
    assert in_list == []


def test_single_item_list() -> None:
    """Test that a list with a single item is processed correctly."""

    in_list: list[JSONVal] = ["test"]

    process_list(
        in_list,
        target_type=str,
        target_processor_func=lambda value, **_: str(value).upper(),
        pass_on_fail=False,
    )

    assert in_list == ["TEST"]


@pytest.mark.parametrize(
    ("in_list", "target_type", "target_processor_func", "expected"),
    [
        (
            ["a", "b", "c", 1, 2, 3, "d", "e", "f"],
            str,
            lambda value, **_: value.upper(),
            ["A", "B", "C", 1, 2, 3, "D", "E", "F"],
        ),
        (
            ["a", "b", "c", 1, 2, 3, "d", "e", "f"],
            str,
            lambda value, **_: value.upper() if value in "abc" else value,
            ["A", "B", "C", 1, 2, 3, "d", "e", "f"],
        ),
        (
            ["a", "b", "c", 1, 2, 3, "4", "5", "6"],
            int,
            lambda value, **_: value + 1,
            ["a", "b", "c", 2, 3, 4, "4", "5", "6"],
        ),
        (
            ["a", "b", "c", 1, 2, 3, "4", "5", "6"],
            str,
            lambda value, **_: int(value) + 1,
            ["a", "b", "c", 1, 2, 3, 5, 6, 7],
        ),
        (
            ["ab", b"bc", "cd", b"de"],
            bytes,
            lambda value, **_: value.decode(),
            ["ab", "bc", "cd", "de"],
        ),
        (
            ["ab", b"bcd", "bcd", "cd", b"cd", "def"],
            str,
            lambda value, **_: value[::-1] if len(value) > 2 else value,
            ["ab", b"bcd", "dcb", "cd", b"cd", "fed"],
        ),
        (
            ["ab", b"bcd", "bcd", "cd", b"cd", "def"],
            (str, bytes),
            lambda value, **_: (value.decode() if isinstance(value, bytes) else value)[
                ::-1
            ]
            if len(value) > 2
            else value,
            ["ab", "dcb", "dcb", "cd", b"cd", "fed"],
        ),
    ],
)
def test_varying_inputs_processed_as_expected(
    in_list: list[JSONVal],
    target_type: type[JSONVal] | tuple[type[JSONVal], ...],
    target_processor_func: TargetProcessorFunc,
    expected: list[JSONVal],
) -> None:
    """Test various lists with different types and processor functions."""

    process_list(
        in_list,
        target_type=target_type,
        target_processor_func=target_processor_func,
    )

    assert in_list == expected


@pytest.mark.parametrize(
    ",".join(
        [
            "in_list",
            "target_type",
            "target_processor_func",
            "exception_type",
            "exception_message",
            "expected",
        ]
    ),
    [
        (
            ["a", "b", "c", 1, 2, 3, "d", "e", "f"],
            (str, int),
            lambda value, **_: value.upper(),
            AttributeError,
            "'int' object has no attribute 'upper'",
            ["A", "B", "C", 1, 2, 3, "d", "e", "f"],
        ),
        (
            ["a", 3, 2, 1, 0, 3, 2, 1, 0, "b"],
            int,
            lambda value, **_: 1 / value,
            ZeroDivisionError,
            "division by zero",
            ["a", 1 / 3, 0.5, 1, 0, 3, 2, 1, 0, "b"],
        ),
        (
            [("a", "b", "c"), [1, 2, 3], [4, 5], [6, 7, 8], [9, 10]],
            list,
            lambda value, **_: [value[0], value[1], value[2] + 1],
            IndexError,
            "list index out of range",
            [("a", "b", "c"), [1, 2, 4], [4, 5], [6, 7, 8], [9, 10]],
        ),
    ],
)
def test_exceptions_are_raised_correctly(
    in_list: list[JSONVal],
    target_type: type[JSONVal] | tuple[type[JSONVal], ...],
    target_processor_func: TargetProcessorFunc,
    exception_type: type[Exception],
    exception_message: str,
    expected: list[JSONVal],
) -> None:
    """Test that exceptions are raised correctly for varying inputs."""

    with pytest.raises(exception_type) as exc_info:
        process_list(
            in_list,
            target_type=target_type,
            target_processor_func=target_processor_func,
            pass_on_fail=False,
        )

    assert str(exc_info.value) == exception_message
    assert in_list == expected


@pytest.mark.parametrize(
    ",".join(
        [
            "in_list",
            "target_type",
            "target_processor_func",
            "exception_indexes",
            "expected",
        ]
    ),
    [
        (
            ["a", "b", "c", 1, 2, 3, "d", "e", "f"],
            (str, int),
            lambda value, **_: value.upper(),
            [3, 4, 5],
            ["A", "B", "C", 1, 2, 3, "D", "E", "F"],
        ),
        (
            ["a", 3, 2, 1, 0, 3, 2, 1, 0, "b"],
            int,
            lambda value, **_: 1 / value,
            [4, 8],
            ["a", 1 / 3, 0.5, 1, 0, 1 / 3, 0.5, 1, 0, "b"],
        ),
        (
            [("a", "b", "c"), [1, 2, 3], [4, 5], [6, 7, 8], [9, 10]],
            list,
            lambda value, **_: [value[0], value[1], value[2] + 1],
            [2, 4],
            [("a", "b", "c"), [1, 2, 4], [4, 5], [6, 7, 9], [9, 10]],
        ),
    ],
)
def test_exceptions_are_logged_correctly(
    in_list: list[JSONVal],
    target_type: type[JSONVal] | tuple[type[JSONVal], ...],
    target_processor_func: TargetProcessorFunc,
    exception_indexes: list[int],
    expected: list[JSONVal],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that exceptions are logged correctly for varying inputs."""

    process_list(
        in_list,
        target_type=target_type,
        target_processor_func=target_processor_func,
        log_op_func_failures=True,
    )

    assert in_list == expected

    log_records = caplog.records

    for i in exception_indexes:
        log_record = log_records.pop(0)
        assert log_record.message == f"Unable to process item at index {i}"
        assert log_record.levelno == ERROR

    # Check that no other log records were created
    assert len(log_records) == 0


@pytest.mark.parametrize(
    ("in_list", "expected"),
    [
        (
            [
                ["a", "b", "c"],
                ["d", "e", "f"],
                ["g", "h", "i"],
            ],
            [
                ["A", "B", "C"],
                ["D", "E", "F"],
                ["G", "H", "I"],
            ],
        ),
        (
            [
                ["a", "b", "c"],
                [
                    ["d", "e", "f"],
                    ["g", "h", "i"],
                ],
                [
                    "j",
                    [
                        ["k", "l", "m"],
                        "n",
                    ],
                ],
            ],
            [
                ["A", "B", "C"],
                [
                    ["D", "E", "F"],
                    ["G", "H", "I"],
                ],
                [
                    "J",
                    [
                        ["K", "L", "M"],
                        "N",
                    ],
                ],
            ],
        ),
    ],
)
def test_nested_lists_are_processed_correctly(
    in_list: list[JSONVal], expected: list[JSONVal]
) -> None:
    """Test that nested lists are processed correctly."""

    process_list(
        in_list,
        target_type=str,
        target_processor_func=lambda v, **_: v.upper(),  # type: ignore[arg-type]
    )

    assert in_list == expected


@pytest.mark.parametrize(
    ("in_list", "call_args_list"),
    [
        (
            [
                {"a": "b", "c": "d"},
                ["e", "f", "g", "h"],
                {"i": "j", "k": "l"},
            ],
            [
                call(
                    {"a": "b", "c": "d"},
                    target_type=str,
                    target_processor_func=ANY,
                    pass_on_fail=True,
                    log_op_func_failures=False,
                    single_keys_to_remove=None,
                ),
                call(
                    {"i": "j", "k": "l"},
                    target_type=str,
                    target_processor_func=ANY,
                    pass_on_fail=True,
                    log_op_func_failures=False,
                    single_keys_to_remove=None,
                ),
            ],
        ),
        (
            [
                {"a": "b", "c": "d"},
                [
                    {"e": "f", "g": "h"},
                    {"i": "j", "k": "l"},
                ],
                [
                    "m",
                    [
                        {"n": "o", "p": "q"},
                        "r",
                    ],
                ],
            ],
            [
                call(
                    {"a": "b", "c": "d"},
                    target_type=str,
                    target_processor_func=ANY,
                    pass_on_fail=True,
                    log_op_func_failures=False,
                    single_keys_to_remove=None,
                ),
                call(
                    {"e": "f", "g": "h"},
                    target_type=str,
                    target_processor_func=ANY,
                    pass_on_fail=True,
                    log_op_func_failures=False,
                    single_keys_to_remove=None,
                ),
                call(
                    {"i": "j", "k": "l"},
                    target_type=str,
                    target_processor_func=ANY,
                    pass_on_fail=True,
                    log_op_func_failures=False,
                    single_keys_to_remove=None,
                ),
                call(
                    {"n": "o", "p": "q"},
                    target_type=str,
                    target_processor_func=ANY,
                    pass_on_fail=True,
                    log_op_func_failures=False,
                    single_keys_to_remove=None,
                ),
            ],
        ),
    ],
)
@patch("wg_utilities.functions.json.traverse_dict")
def test_nested_dicts_are_passed_to_traverse_dict(
    mock_traverse_dict: MagicMock, in_list: list[JSONVal], call_args_list: list[_Call]
) -> None:
    """Test that nested dicts are passed to traverse_dict."""

    process_list(
        in_list,
        target_type=str,
        target_processor_func=lambda v, **_: v.upper(),  # type: ignore[arg-type]
    )

    assert mock_traverse_dict.call_args_list == call_args_list


@pytest.mark.parametrize(
    ("in_list", "target_type", "target_processor_func", "expected"),
    [
        (
            ["a", "b", "c", 1, 2, 3, "d", "e", "f"],
            str,
            lambda value, list_index=None, **_: value.upper()
            if list_index % 2 == 0
            else value,
            ["A", "b", "C", 1, 2, 3, "D", "e", "F"],
        ),
        (
            ["a", "b", "c", 1, 2, 3, "d", "e", "f"],
            str,
            lambda value, list_index=None, **_: value.upper()
            if (value in "abc" and list_index % 2 == 0)
            else value,
            ["A", "b", "C", 1, 2, 3, "d", "e", "f"],
        ),
        (
            ["ab", b"bcd", "bcd", "cd", b"cd", "def"],
            bytes,
            lambda value, list_index=None, **_: value.decode()[::-1]
            if list_index == 1
            else value,
            ["ab", "dcb", "bcd", "cd", b"cd", "def"],
        ),
    ],
)
def test_list_index_parameter_for_target_processor_func(
    in_list: list[JSONVal],
    target_type: type[JSONVal] | tuple[type[JSONVal], ...],
    target_processor_func: TargetProcessorFunc,
    expected: list[JSONVal],
) -> None:
    """Test that the list index is passed to the target processor function."""

    process_list(
        in_list,
        target_type=target_type,
        target_processor_func=target_processor_func,
    )

    assert in_list == expected
