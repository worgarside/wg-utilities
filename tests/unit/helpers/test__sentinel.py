"""Unit tests for the `Sentinel` class."""

from __future__ import annotations

import pytest

from wg_utilities.helpers import Sentinel

SENTINEL = Sentinel()


def test_falsy() -> None:
    """Test that the sentinel is always falsy."""
    assert not SENTINEL
    assert bool(SENTINEL) is False
    assert bool(SENTINEL) is not True

    if SENTINEL:
        pytest.fail("Sentinel should be falsy")


def test_iterable() -> None:
    """Test that the sentinel is an iterable that raises StopIteration."""
    iterator = iter(SENTINEL)

    assert isinstance(iterator, Sentinel.Iterator)
    assert iter(iterator) is iterator

    with pytest.raises(StopIteration):
        next(iterator)

    for _ in SENTINEL:
        pytest.fail("Sentinel should not iterate")

    assert list(SENTINEL) == []
    assert tuple(SENTINEL) == ()
    assert set(SENTINEL) == set()


def test_callable() -> None:
    """Test that the sentinel is callable."""
    SENTINEL()
