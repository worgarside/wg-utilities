"""Conftest for the processor tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generator

import pytest

from tests.unit.clients.spotify.conftest import (
    mock_requests_,
    spotify_client_,
    spotify_user_,
)
from wg_utilities.clients.oauth_client import BaseModelWithConfig
from wg_utilities.functions.subclasses import subclasses_recursive
from wg_utilities.helpers.processor import JProc

if TYPE_CHECKING:
    from wg_utilities.helpers.processor.json import Callback


@pytest.fixture(name="mock_cb")
def mock_cb_() -> Callback[..., Any]:
    """Create a callback that does nothing."""

    @JProc.callback()
    def _cb(_value_: Any) -> Any:  # pragma: no cover
        return _value_

    return _cb


@pytest.fixture(name="mock_cb_two")
def mock_cb_two_() -> Callback[..., Any]:
    """Create a second callback that does nothing."""

    @JProc.callback()
    def _cb2(_value_: Any) -> Any:  # pragma: no cover
        return _value_

    return _cb2


@pytest.fixture(name="mock_cb_three")
def mock_cb_three_() -> Callback[..., Any]:
    """Create a third callback that does nothing."""

    @JProc.callback()
    def _cb3(_value_: Any) -> Any:  # pragma: no cover
        return _value_

    return _cb3


@pytest.fixture(name="mock_cb_four")
def mock_cb_four_() -> Callback[..., Any]:
    """Create a fourth callback that does nothing."""

    @JProc.callback()
    def _cb4(_value_: Any) -> Any:  # pragma: no cover
        return _value_

    return _cb4


@pytest.fixture(autouse=True)
def _jproc_cleanup() -> Generator[None, None, None]:
    """Teardown for the JProc tests."""
    JProc._DECORATED_CALLBACKS = set()

    yield

    JProc._DECORATED_CALLBACKS = set()


@pytest.fixture(name="wrap")
def convert_lambda_to_callback_() -> Callable[[Callable[..., Any]], Callback[..., Any]]:
    """Fixture for converting Lambdas to proper functions for quicker testing."""

    def _cb_factory(_lambda: Callable[..., Any]) -> Callback[..., Any]:
        @JProc.callback()
        def _cb(_value_: Any) -> Any:
            return _lambda(_value_)

        return _cb

    return _cb_factory


@pytest.fixture(autouse=True)
def _modify_base_model() -> None:
    """Modify the base model for the Pydantic-based tests."""

    BaseModelWithConfig.__hash__ = lambda v: hash(str(v))  # type: ignore[assignment,method-assign]
    BaseModelWithConfig.model_config["validate_assignment"] = False

    for sc in subclasses_recursive(BaseModelWithConfig):
        sc.model_config["validate_assignment"] = False


# Keeps them imported for the Pydantic-based tests
__all__ = ["spotify_user_", "spotify_client_", "mock_requests_"]
