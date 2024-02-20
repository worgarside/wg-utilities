"""Unit tests for the `subclasses_recursive` function."""

from __future__ import annotations

from wg_utilities.functions import subclasses_recursive


class BaseClassA:
    """A base class for testing."""


class DirectSubclassA(BaseClassA):
    """A direct subclass of BaseClass."""


class BaseClassB:
    """A base class for testing."""


class DirectSubclassB(BaseClassB):
    """A direct subclass of BaseClass."""


class NestedSubclass(DirectSubclassA, DirectSubclassB):
    """A subclass of DirectSubclass; also a subclass of BaseClass."""


class LonelyClass:
    """A class with no subclasses."""


def test_no_subclasses() -> None:
    """Test that a class with no descendants yields no subclasses."""
    assert len(list(subclasses_recursive(LonelyClass))) == 0
    assert len(list(subclasses_recursive(NestedSubclass))) == 0


def test_subclasses() -> None:
    """Test that direct subclasses are correctly identified."""

    assert list(subclasses_recursive(BaseClassA)) == [DirectSubclassA, NestedSubclass]
    assert list(subclasses_recursive(BaseClassB)) == [DirectSubclassB, NestedSubclass]


def test_subclass_filter() -> None:
    """Test filtering subclasses."""

    assert list(
        subclasses_recursive(
            BaseClassA,
            class_filter=lambda cls: cls.__name__.startswith("Nested"),
        ),
    ) == [NestedSubclass]
    assert list(
        subclasses_recursive(
            BaseClassB,
            class_filter=lambda cls: cls.__name__.startswith("Nested"),
        ),
    ) == [NestedSubclass]


class BaseClassC:
    """A base class for testing."""


class DirectSubclassC1(BaseClassC):
    """A direct subclass of BaseClass."""


class DirectSubclassC2(BaseClassC):
    """A direct subclass of BaseClass."""


class NestedSubclassC101(DirectSubclassC1):
    """A subclass of DirectSubclass; also a subclass of BaseClass."""


class NestedSubclassC102(DirectSubclassC1):
    """A subclass of DirectSubclass; also a subclass of BaseClass."""


class NestedSubclassC201(DirectSubclassC2):
    """A subclass of DirectSubclass; also a subclass of BaseClass."""


class NestedSubclassC202(DirectSubclassC2):
    """A subclass of DirectSubclass; also a subclass of BaseClass."""


def test_nested_subclasses() -> None:
    """Test that nested subclasses are correctly identified."""
    assert list(subclasses_recursive(BaseClassC)) == [
        DirectSubclassC1,
        NestedSubclassC101,
        NestedSubclassC102,
        DirectSubclassC2,
        NestedSubclassC201,
        NestedSubclassC202,
    ]


def test_visit_tracking() -> None:
    """Test that visit tracking works as expected."""

    assert list(
        subclasses_recursive(
            BaseClassC,
            track_visited=False,
            __visited={DirectSubclassC2},  # type: ignore[call-arg]
        ),
    ) == [
        DirectSubclassC1,
        NestedSubclassC101,
        NestedSubclassC102,
        DirectSubclassC2,
        NestedSubclassC201,
        NestedSubclassC202,
    ]

    assert list(
        subclasses_recursive(
            BaseClassC,
            track_visited=True,
            __visited={DirectSubclassC2},  # type: ignore[call-arg]
        ),
    ) == [
        DirectSubclassC1,
        NestedSubclassC101,
        NestedSubclassC102,
    ]
