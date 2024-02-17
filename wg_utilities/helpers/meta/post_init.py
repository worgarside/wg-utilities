"""Mixin to provide `__post_init__` functionality."""
from __future__ import annotations

from typing import Any

from wg_utilities.exceptions import BadDefinitionError


class MissingPostInitMethodError(BadDefinitionError):
    """Raised when a class using the `PostInitMeta` metaclass does not define a `__post_init__` method."""

    def __init__(self, cls: type) -> None:
        """Initialize the error with the class that is missing the `__post_init__` method."""
        super().__init__(f"Class {cls.__name__!r} is missing a `__post_init__` method.")


class PostInitMeta(type):
    """Metaclass to call a post-init method after the class is instantiated."""

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Call the class and then call the post-init method."""
        obj = type.__call__(cls, *args, **kwargs)

        try:
            obj.__post_init__()
        except AttributeError as exc:
            if exc.name == "__post_init__":
                raise MissingPostInitMethodError(cls) from None

            raise

        return obj


__all__ = ["PostInitMeta", "MissingPostInitMethodError"]
