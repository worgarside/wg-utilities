"""Unit Tests for the `wg_utilities.functions.json.process_list` function."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from wg_utilities.functions import process_json_object
from wg_utilities.functions.json import InvalidJsonObjectError, JSONVal


def target_proc_func(  # pragma: no cover
    value: JSONVal, dict_key: str | None = None, list_index: int | None = None
) -> JSONVal:
    """Dummy function for processing items."""
    _ = dict_key, list_index
    return value


def test_dict() -> None:
    """Test that a dictionary is processed correctly."""

    with patch(
        "wg_utilities.functions.json.traverse_dict"
    ) as mock_traverse_dict, patch(
        "wg_utilities.functions.json.process_list"
    ) as mock_process_list:
        process_json_object(
            {"key": "value"},
            target_type=str,
            target_processor_func=target_proc_func,
            pass_on_fail=False,
            log_op_func_failures=True,
            single_keys_to_remove=["one", "two"],
        )

    mock_traverse_dict.assert_called_once_with(
        {"key": "value"},
        target_type=str,
        target_processor_func=target_proc_func,
        pass_on_fail=False,
        log_op_func_failures=True,
        single_keys_to_remove=["one", "two"],
    )
    mock_process_list.assert_not_called()


def test_list() -> None:
    """Test that a list is processed correctly."""

    with patch(
        "wg_utilities.functions.json.traverse_dict"
    ) as mock_traverse_dict, patch(
        "wg_utilities.functions.json.process_list"
    ) as mock_process_list:
        process_json_object(
            ["value"],
            target_type=str,
            target_processor_func=target_proc_func,
            pass_on_fail=False,
            log_op_func_failures=True,
            single_keys_to_remove=["one", "two"],
        )

    mock_traverse_dict.assert_not_called()
    mock_process_list.assert_called_once_with(
        ["value"],
        target_type=str,
        target_processor_func=target_proc_func,
        pass_on_fail=False,
        log_op_func_failures=True,
        single_keys_to_remove=["one", "two"],
    )


def test_invalid_type() -> None:
    """Test that an invalid type raises an exception."""

    with pytest.raises(InvalidJsonObjectError) as exc_info:
        process_json_object(
            123,  # type: ignore[arg-type]
            target_type=str,
            target_processor_func=target_proc_func,
            pass_on_fail=False,
            log_op_func_failures=True,
            single_keys_to_remove=["one", "two"],
        )

    assert (
        exc_info.value.args[0]
        == "Input object must be a dict or list, not <class 'int'>"
    )
