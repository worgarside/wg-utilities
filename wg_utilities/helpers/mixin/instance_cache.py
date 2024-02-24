"""Mixin class to provide instance caching functionality."""

from __future__ import annotations

from typing import Any, ClassVar, Self, final

from wg_utilities.exceptions._exception import WGUtilitiesError
from wg_utilities.helpers.meta.post_init import PostInitMeta

CacheIdType = object | tuple[object, object]


class InstanceCacheError(WGUtilitiesError):
    """Base class for all instance cache exceptions."""


class InstanceCacheSubclassError(InstanceCacheError):
    """Raised when a subclass is declared incorrectly."""


class InstanceCacheDuplicateError(InstanceCacheSubclassError):
    """Raised when a key is already in the cache."""

    def __init__(self, cls: type, key: CacheIdType, /) -> None:
        self.cls = cls
        self.key = key

        super().__init__(
            f"{cls.__name__!r} instance with cache ID {key!r} already exists.",
        )


class InstanceCacheIdError(InstanceCacheError):
    """Raised when there is an error handling a cache ID."""

    def __init__(
        self,
        cls: type,
        cache_id_: CacheIdType,
        /,
        msg: str = "Unable to process cache ID: `{cache_id}`",
    ) -> None:
        self.cls = cls
        self.cache_id = cache_id_

        cache_id_str = (
            "|".join(map(str, cache_id_))
            if isinstance(cache_id_, tuple)
            else str(cache_id_)
        )

        super().__init__(msg.format(cache_id=cache_id_str))


class CacheIdNotFoundError(InstanceCacheIdError):
    """Raised when an ID is not found in the cache."""

    def __init__(self, cls: type, cache_id_: CacheIdType, /) -> None:
        super().__init__(
            cls,
            cache_id_,
            msg=f"No matching {cls.__name__!r} instance for cache ID: `{{cache_id}}`",
        )


class CacheIdGenerationError(InstanceCacheIdError):
    """Raised when there is an error generating a cache ID."""

    def __init__(self, cls: type, cache_id_: CacheIdType, /) -> None:
        super().__init__(
            cls,
            cache_id_,
            msg=f"Error generating cache ID for class {cls.__name__!r}: `{{cache_id}}`",
        )


class InstanceCacheMixin(metaclass=PostInitMeta):
    """Mixin class to provide instance caching functionality.

    Attributes:
        cache_id_attr (str | None): The name of the attribute to use in the cache ID. Defaults to None.
            Must be provided if `cache_id_func` is None.
        cache_id_func (str | None): The name of the function whose return value to use in the cache ID.
            Defaults to "__hash__". Must not be `None` if `cache_id_attr` is None.
        kwargs (Any): Additional keyword arguments to pass to the superclass.
    """

    _INSTANCES: dict[CacheIdType, Self]

    _CACHE_ID_ATTR: ClassVar[str]
    _CACHE_ID_FUNC: ClassVar[str]

    def __init_subclass__(
        cls,
        *,
        cache_id_attr: str | None = None,
        cache_id_func: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialise subclasses with instance cache and cache ID attributes.

        Args:
            cache_id_attr (str | None, optional): The name of the attribute to use in the cache ID. Defaults to
                None. Must be provided if `cache_id_func` is None.
            cache_id_func (str | None, optional): The name of the function whose return value to use in the cache
                ID. Defaults to "__hash__" (and must be provided) if `cache_id_attr` is None.
            kwargs (Any): Additional keyword arguments to pass to the superclass.

        Raises:
            InstanceCacheSubclassError: If neither `cache_id_attr` nor `cache_id_func` are provided.
        """
        if not (cache_id_attr or cache_id_func):
            cache_id_func = "__hash__"

        if not (isinstance(cache_id_attr, str) or cache_id_attr is None):
            raise InstanceCacheSubclassError(
                f"Invalid cache ID attribute: {cache_id_attr!r}",
            )

        if not (isinstance(cache_id_func, str) or cache_id_func is None):
            raise InstanceCacheSubclassError(
                f"Invalid cache ID function: {cache_id_func!r}",
            )

        super().__init_subclass__(**kwargs)
        cls._INSTANCES = {}

        if cache_id_attr:
            cls._CACHE_ID_ATTR = cache_id_attr

        if cache_id_func:
            cls._CACHE_ID_FUNC = cache_id_func

    def __post_init__(self) -> None:
        """Add the instance to the cache.

        Raises:
            InstanceCacheDuplicateError: If the instance already exists in the cache.
        """
        if (instance_id := cache_id(self)) in self._INSTANCES:
            raise InstanceCacheDuplicateError(self.__class__, instance_id)

        self._INSTANCES[instance_id] = self  # type: ignore[assignment]

    @final
    @classmethod
    def from_cache(cls, cache_id_: CacheIdType, /) -> Self:
        """Get an instance from the cache by its cache ID."""
        try:
            return cls._INSTANCES[cache_id_]  # type: ignore[return-value]
        except KeyError:
            raise CacheIdNotFoundError(cls, cache_id_) from None

    @final
    @classmethod
    def has_cache_entry(cls, cache_id_: CacheIdType, /) -> bool:
        """Check if the cache has an entry for the given cache ID."""
        return cache_id_ in cls._INSTANCES


def cache_id(obj: InstanceCacheMixin, /) -> CacheIdType:
    """Get the cache ID for the given object."""
    attr_id = getattr(obj, getattr(obj, "_CACHE_ID_ATTR", "_"), None)
    func_id = getattr(obj, getattr(obj, "_CACHE_ID_FUNC", "_"), lambda: None)()

    match (attr_id, func_id):
        case (a_id, None) if a_id is not None:
            return a_id  # type: ignore[no-any-return]
        case (None, f_id) if f_id is not None:
            return f_id  # type: ignore[no-any-return]
        case (a_id, f_id) if a_id is not None and f_id is not None:
            return (a_id, f_id)
        case _:
            raise CacheIdGenerationError(obj.__class__, (attr_id, func_id))


__all__ = [
    "InstanceCacheIdError",
    "InstanceCacheDuplicateError",
    "InstanceCacheMixin",
    "cache_id",
]
