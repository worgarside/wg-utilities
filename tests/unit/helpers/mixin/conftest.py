"""Conftest for the mixin tests."""

from __future__ import annotations

import pytest

from wg_utilities.helpers.mixin.instance_cache import InstanceCacheMixin


@pytest.fixture(name="TestCacheableClass")
def test_cacheable_class() -> type:
    """Fixture for creating a test class that uses the InstanceCacheMixin."""

    class TestCacheableClass(
        InstanceCacheMixin,
        cache_id_attr="name",
        cache_id_func=None,
    ):
        __test__ = False

        def __init__(self, name: str):
            self.name = name

    return TestCacheableClass
