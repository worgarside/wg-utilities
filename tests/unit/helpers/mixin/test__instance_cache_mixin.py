"""Test the `InstanceCacheMixin` class."""

from __future__ import annotations

from uuid import UUID

import pytest

from wg_utilities.helpers.mixin.instance_cache import (
    CacheIdGenerationError,
    CacheIdType,
    InstanceCacheDuplicateError,
    InstanceCacheIdError,
    InstanceCacheMixin,
    InstanceCacheSubclassError,
    cache_id,
)

UID = UUID("e9545fd5-efd0-4d0c-a55a-f04dd03fbe4b")


def test_one_id_value_required() -> None:
    """Test an error is thrown when a subclass has both cache ID fields as null."""

    with pytest.raises(InstanceCacheSubclassError):

        class NoIdValue(InstanceCacheMixin, cache_id_attr=None, cache_id_func=None):
            pass


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cache_id_attr": "my_attribute"},
        {"cache_id_attr": "my_attribute", "cache_id_func": None},
        {"cache_id_func": "my_function"},
        {"cache_id_attr": "my_attribute", "cache_id_func": "my_function"},
    ],
)
def test_class_attributes_are_set(kwargs: dict[str, str | None]) -> None:
    """Test that the class attributes are set correctly for a new subclass."""

    class MyClass(InstanceCacheMixin, **kwargs):
        __test__ = False

    assert isinstance(MyClass._INSTANCES, dict)
    assert {} == MyClass._INSTANCES

    assert kwargs.get("cache_id_attr") == getattr(MyClass, "_CACHE_ID_ATTR", None)

    assert kwargs.get("cache_id_func", "__hash__") == getattr(
        MyClass,
        "_CACHE_ID_FUNC",
        None,
    )


def test_invalid_cache_id_attr() -> None:
    """Test an error is thrown when an invalid cache ID attribute is provided."""

    with pytest.raises(InstanceCacheSubclassError, match="Invalid cache ID attribute: "):

        class InvalidCacheIdAttr(InstanceCacheMixin, cache_id_attr=123):  # type: ignore[arg-type]
            pass


def test_invalid_cache_id_func() -> None:
    """Test an error is thrown when an invalid cache ID function is provided."""

    with pytest.raises(InstanceCacheSubclassError, match="Invalid cache ID function: "):

        class InvalidCacheIdFunc(InstanceCacheMixin, cache_id_func=123):  # type: ignore[arg-type]
            pass


def test_caching(TestCacheableClass: type[InstanceCacheMixin]) -> None:
    """Test that instances are cached correctly."""
    instance_1 = TestCacheableClass("one")
    instance_2 = TestCacheableClass("two")

    assert {
        "one": instance_1,
        "two": instance_2,
    } == TestCacheableClass._INSTANCES


def test_cache_collision(TestCacheableClass: type[InstanceCacheMixin]) -> None:
    """Test an error is thrown when a cache ID collision occurs."""
    _ = TestCacheableClass("one")

    with pytest.raises(
        InstanceCacheDuplicateError,
        match="'TestCacheableClass' instance with cache ID 'one' already exists.",
    ):
        TestCacheableClass("one")


def test_cache_retrieval(TestCacheableClass: type[InstanceCacheMixin]) -> None:
    """Test that instances are retrieved from the cache correctly."""
    instance_1 = TestCacheableClass("one")
    instance_2 = TestCacheableClass("two")

    assert instance_1 is TestCacheableClass.from_cache("one")
    assert instance_2 is TestCacheableClass.from_cache("two")
    assert instance_1 is not TestCacheableClass.from_cache("two")
    assert instance_2 is not TestCacheableClass.from_cache("one")

    with pytest.raises(
        InstanceCacheIdError,
        match="No matching 'TestCacheableClass' instance for cache ID: `three`",
    ):
        TestCacheableClass.from_cache("three")


def test_cache_entry_check(TestCacheableClass: type[InstanceCacheMixin]) -> None:
    """Test that the cache entry check works correctly."""
    TestCacheableClass("one")

    assert TestCacheableClass.has_cache_entry("one")
    assert not TestCacheableClass.has_cache_entry("two")


def test_cache_id(TestCacheableClass: type[InstanceCacheMixin]) -> None:
    """Test that the cache ID function works correctly."""
    instance = TestCacheableClass("one")

    assert TestCacheableClass._INSTANCES[cache_id(instance)] is instance


@pytest.mark.parametrize(
    ("kwargs", "expected_id"),
    [
        ({"cache_id_attr": "uid"}, (UID, 1234)),
        ({"cache_id_attr": "uid", "cache_id_func": None}, UID),
        ({"cache_id_func": "func"}, f"one|{UID}"),
        ({"cache_id_attr": "name", "cache_id_func": "func"}, ("one", f"one|{UID}")),
    ],
)
def test_cache_id_generation(
    kwargs: dict[str, str | None],
    expected_id: CacheIdType,
) -> None:
    """Test that the cache ID generation works correctly."""

    class MyClass(InstanceCacheMixin, **kwargs):
        __test__ = False

        def __init__(self, name: str):
            self.name = name
            self.uid = UID

        def func(self) -> str:
            return self.name + "|" + str(self.uid)

        def __hash__(self) -> int:
            """Dummy function to make testing easier."""
            return 1234

    instance = MyClass(name="one")

    assert expected_id == cache_id(instance)


def test_invalid_cache_id_generation() -> None:
    """Test an error is thrown when an invalid cache ID is generated."""

    class MyClass(InstanceCacheMixin, cache_id_attr="uid", cache_id_func="func"):
        __test__ = False

        def __init__(self, name: str):
            self.name = name

        def func(self) -> None:
            return None

    with pytest.raises(
        CacheIdGenerationError,
        match="Error generating cache ID for class 'MyClass': `None|None`",
    ):
        MyClass(name="one")
