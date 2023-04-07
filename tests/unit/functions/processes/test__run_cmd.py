"""Unit Tests for the `wg_utilities.functions.processes.run_cmd` function."""

from __future__ import annotations

from pytest import raises

from wg_utilities.functions import run_cmd


def test__run_cmd_no_error() -> None:
    """Test that the run_cmd function runs a command without error."""
    output, error = run_cmd("echo 'hello world'")
    assert output == "'hello world'"
    assert error == ""


def test_command_throws_exception_on_error() -> None:
    """Test that the run_cmd function throws an exception if the command errors."""

    with raises(RuntimeError) as exc_info:
        run_cmd("qwertyuiop", shell=True)

    assert "not found" in str(exc_info.value)
    assert "qwertyuiop" in str(exc_info.value)
