"""Conftest for the processor tests."""

from __future__ import annotations

from typing import Any, Generator

import pytest

from wg_utilities.helpers.processor import JProc
from wg_utilities.helpers.processor.json import Callback


@pytest.fixture(name="mock_cb")
def mock_cb_() -> Callback[..., Any]:
    """Create a callback that does nothing."""

    @JProc.callback()
    def _cb(_value_: Any) -> Any:
        return _value_

    return _cb


@pytest.fixture(name="mock_cb_two")
def mock_cb_two_() -> Callback[..., Any]:
    """Create a second callback that does nothing."""

    @JProc.callback()
    def _cb2(_value_: Any) -> Any:
        return _value_

    return _cb2


@pytest.fixture(name="mock_cb_three")
def mock_cb_three_() -> Callback[..., Any]:
    """Create a third callback that does nothing."""

    @JProc.callback()
    def _cb3(_value_: Any) -> Any:
        return _value_

    return _cb3


@pytest.fixture(name="mock_cb_four")
def mock_cb_four_() -> Callback[..., Any]:
    """Create a fourth callback that does nothing."""

    @JProc.callback()
    def _cb4(_value_: Any) -> Any:
        return _value_

    return _cb4


@pytest.fixture(autouse=True)
def _jproc_cleanup() -> Generator[None, None, None]:
    """Teardown for the JProc tests."""
    JProc._DECORATED_CALLBACKS = set()

    yield

    JProc._DECORATED_CALLBACKS = set()
