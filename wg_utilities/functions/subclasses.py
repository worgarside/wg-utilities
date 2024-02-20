"""Get all subclasses of a class recursively."""


from __future__ import annotations

from typing import Any, Callable, Generator


def subclasses_recursive(
    typ: type[Any],
    /,
    *,
    class_filter: None | Callable[[type[Any]], bool] = None,
) -> Generator[type[Any], None, None]:
    """Get all subclasses of a class recursively.

    Args:
        typ (type): the class to get the subclasses of
        class_filter (None, optional): a function to filter the subclasses

    Yields:
        type: a subclass of the given class
    """
    for subclass in typ.__subclasses__():
        if class_filter is None or class_filter(subclass) is True:
            yield subclass

        yield from subclasses_recursive(subclass, class_filter=class_filter)


__all__ = ["subclasses_recursive"]
