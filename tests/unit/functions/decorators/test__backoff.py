"""Unit tests for wg_utilities.functions.decorators.backoff decorator."""

from __future__ import annotations

from unittest.mock import ANY, MagicMock, patch

import pytest
from pydantic import ValidationError

from tests.conftest import TestError
from wg_utilities.functions import backoff


def test_default_call_permanent_failure() -> None:
    """Test that the default call works as expected."""

    call_count = 0

    @backoff()
    def test_func() -> None:
        """Test function."""

        nonlocal call_count

        call_count += 1

        raise ValueError

    with pytest.raises(ValueError), patch(
        "wg_utilities.functions.decorators.sleep",
    ) as mock_sleep:
        test_func()

    assert mock_sleep.call_count == 9  # 10 tries total
    assert mock_sleep.call_args_list[0][0][0] == 0.1

    prev_value = 0
    for call in mock_sleep.call_args_list:
        assert call[0][0] > prev_value or call[0][0] == 60  # max delay
        prev_value = call[0][0]

    assert call_count == 10


def test_default_call_success() -> None:
    """Test that the default call works when the function succeeds immediately."""

    call_count = 0

    @backoff()
    def test_func() -> None:
        """Test function."""

        nonlocal call_count

        call_count += 1

    with patch("wg_utilities.functions.decorators.sleep") as mock_sleep:
        test_func()

    mock_sleep.assert_not_called()

    assert call_count == 1


def test_custom_call_correct_exception() -> None:
    """Test that custom parameters work as expected."""

    call_count = 0

    @backoff(ValueError, max_tries=5, max_delay=30)
    def test_func() -> None:
        """Test function."""

        nonlocal call_count

        call_count += 1

        raise ValueError

    with pytest.raises(ValueError), patch(
        "wg_utilities.functions.decorators.sleep",
    ) as mock_sleep:
        test_func()

    assert mock_sleep.call_count == 4  # 5 tries total
    assert mock_sleep.call_args_list[0][0][0] == 0.1

    prev_value = 0
    for call in mock_sleep.call_args_list:
        assert call[0][0] > prev_value or call[0][0] == 30  # max delay
        prev_value = call[0][0]

    assert call_count == 5


def test_custom_call_incorrect_exception() -> None:
    """Test that custom parameters work as expected."""

    call_count = 0

    @backoff((ValueError, TypeError, ValidationError), max_tries=5, max_delay=30)
    def test_func() -> None:
        """Test function."""

        nonlocal call_count

        call_count += 1

        raise RuntimeError

    with pytest.raises(RuntimeError), patch(
        "wg_utilities.functions.decorators.sleep",
    ) as mock_sleep:
        test_func()

    assert mock_sleep.call_count == 0

    assert call_count == 1


def test_transient_failure() -> None:
    """Test that transient failures are handled correctly."""

    call_count = 0
    function_succeeded = False

    @backoff(ValueError, max_tries=50, max_delay=30)
    def test_func() -> None:
        """Test function."""

        nonlocal call_count, function_succeeded

        call_count += 1

        if call_count < 3:
            raise ValueError

        function_succeeded = True

    with patch("wg_utilities.functions.decorators.sleep") as mock_sleep:
        test_func()

    assert mock_sleep.call_count == 2  # 3 tries total
    assert mock_sleep.call_args_list[0][0][0] == 0.1

    prev_value = 0
    for call in mock_sleep.call_args_list:
        assert call[0][0] > prev_value or call[0][0] == 30  # max delay
        prev_value = call[0][0]

    assert call_count == 3

    assert function_succeeded


def test_logger() -> None:
    """Test that the logger is called correctly."""

    call_count = 0

    logger = MagicMock()

    @backoff(TestError, max_tries=5, max_delay=30, logger=logger)
    def test_func() -> None:
        """Test function."""

        nonlocal call_count

        call_count += 1

        raise TestError

    with pytest.raises(TestError):
        test_func()

    assert call_count == 5

    assert logger.warning.call_count == 5
    for i, call in enumerate(logger.warning.call_args_list):
        *rest, exc = call[0]

        assert rest == [
            "Exception caught in backoff decorator (attempt %i/%i, waiting for %fs): %s %s",
            i,
            5,
            ANY,
            "TestError",
        ]

        assert isinstance(exc, TestError)
