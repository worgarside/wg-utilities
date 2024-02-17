"""Unit tests for the `PostInitMeta` metaclass."""

from __future__ import annotations

import pytest

from wg_utilities.helpers.meta.post_init import MissingPostInitMethodError, PostInitMeta


def test_post_init_call() -> None:
    """Test that the post-init method is called after the class is instantiated."""

    class TestClass(metaclass=PostInitMeta):
        """A test class to check that the post-init method is called."""

        def __init__(self) -> None:
            self.post_init_called = False

        def __post_init__(self) -> None:
            """The post-init method to be called after the class is instantiated."""
            self.post_init_called = True

    test_instance = TestClass()

    assert test_instance.post_init_called is True


def test_missing_method() -> None:
    """Test that a class without a post-init method raises an error."""

    class ShouldNotThrow(metaclass=PostInitMeta):
        """A test class to check that the post-init method is called."""

        def __init__(self) -> None:
            self.post_init_called = False

        def __post_init__(self) -> None:
            """The post-init method to be called after the class is instantiated."""
            self.post_init_called = True

            self.this_will_throw_attribute_error(outcome=True)  # type: ignore[attr-defined]

    class ShouldThrow(metaclass=PostInitMeta):
        """A test class to check that an error is raised when the post-init method is missing."""

        def __init__(self) -> None:
            self.post_init_called = False

    with pytest.raises(AttributeError) as exc_info:
        ShouldNotThrow()

    assert isinstance(exc_info.value, AttributeError)
    assert not isinstance(exc_info.value, MissingPostInitMethodError)

    with pytest.raises(
        MissingPostInitMethodError,
        match="Class 'ShouldThrow' is missing a `__post_init__` method.",
    ):
        ShouldThrow()
