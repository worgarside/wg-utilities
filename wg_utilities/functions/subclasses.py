"""Get all subclasses of a class recursively."""


from __future__ import annotations

from typing import Any, Callable, Generator


def subclasses_recursive(
    typ: type[Any],
    /,
    *,
    class_filter: None | Callable[[type[Any]], bool] = None,
    track_visited: bool = False,
    __visited: set[type[Any]] | None = None,
) -> Generator[type[Any], None, None]:
    """Get all subclasses of a class recursively.

    Args:
        typ (type): the class to get the subclasses of
        class_filter (None, optional): a function to filter the subclasses
        track_visited (bool, optional): whether to track visited subclasses. Useful for avoiding
            infinite loops. Defaults to False.

    Yields:
        type: a subclass of the given class
    """

    for subclass in typ.__subclasses__():
        if track_visited:
            __visited = __visited or set()
            if subclass in __visited:
                continue

            __visited.add(subclass)

        if class_filter is None or class_filter(subclass):
            yield subclass

        yield from subclasses_recursive(
            subclass,
            class_filter=class_filter,
            track_visited=track_visited,
            __visited=__visited,  # type: ignore[call-arg]
        )


__all__ = ["subclasses_recursive"]
