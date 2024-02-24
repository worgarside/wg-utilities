"""Useful functions for working with JSON/dictionaries."""

from __future__ import annotations

import inspect
import re
from collections import defaultdict
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from functools import wraps
from itertools import chain
from typing import (
    Any,
    ClassVar,
    Collection,
    Final,
    Generator,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    NamedTuple,
    ParamSpec,
    Protocol,
    Sequence,
    TypeVar,
    overload,
)

try:
    from pydantic import BaseModel

    PYDANTIC_INSTALLED = True

except ImportError:  # pragma: no cover
    PYDANTIC_INSTALLED = False

    class BaseModel:  # type: ignore[no-redef]
        """Dummy class for when pydantic is not installed.

        As long as `isinstance` returns False, it's all good.
        """


import wg_utilities.exceptions as wg_exc
from wg_utilities.helpers import Sentinel, mixin

P = ParamSpec("P")
R = TypeVar("R")
Callback = Callable[P, R]

K = TypeVar("K")
V = TypeVar("V")

BASE_MODEL_PROPERTIES: Final[set[str]] = {
    name for name, _ in inspect.getmembers(BaseModel, lambda v: isinstance(v, property))
}


class LocNotFoundError(wg_exc.BadUsageError):
    """Raised when a location is not found in the object."""

    def __init__(
        self,
        loc: K | int | str,
        /,
        obj: Mapping[K, V] | Sequence[V] | BaseModel,
    ) -> None:
        super().__init__(f"Location {loc!r} not found in object {obj!r}.")


class InvalidCallbackError(wg_exc.BadDefinitionError):
    """Raised for invalid callback handling."""

    def __init__(self, *args: object, callback: Callback[..., Any]) -> None:
        super().__init__(*args)

        self.callback = callback


class InvalidCallbackArgumentsError(InvalidCallbackError):
    """Raised when a callback is called with extra and/or missing keyword or positional arguments."""

    ARG_TYPE: ClassVar[str]
    PATTERN: ClassVar[re.Pattern[str]]

    def __init__(self, *arg_names: str, callback: Callback[..., Any]) -> None:
        super().__init__(
            f"Missing required {self.ARG_TYPE} argument(s): `{'`, `'.join(arg_names)}`.",
            callback=callback,
        )


class MissingArgError(InvalidCallbackArgumentsError):
    """Raised when a required argument is missing."""

    ARG_TYPE = "positional"
    PATTERN = re.compile(rf"missing \d+ required {ARG_TYPE} argument: '(.+)'")


class MissingKwargError(InvalidCallbackArgumentsError):
    """Raised when a required keyword-only argument is missing."""

    ARG_TYPE = "keyword-only"
    PATTERN = re.compile(rf"missing \d+ required {ARG_TYPE} argument: '(.+)'")


class CallbackNotDecoratedError(InvalidCallbackError):
    """Raised when a callback is not decorated with `@JSONProcessor.callback`."""

    def __init__(self, callback: Callback[..., Any], /) -> None:
        super().__init__(
            f"Callback `{callback.__module__}.{callback.__name__}` must be decorated "
            "with `@JSONProcessor.callback`",
            callback=callback,
        )


class InvalidItemFilterError(InvalidCallbackError):
    """Raised when an item filter is not callable."""

    def __init__(self, item_filter: Any, /, *, callback: Callback[..., Any]) -> None:
        super().__init__(
            f"Item filter `{item_filter!r}` is not callable ({type(item_filter)}).",
            callback=callback,
        )
        self.item_filter = item_filter


class ItemFilter(Protocol):
    """Function to filter items before processing them."""

    def __call__(self, item: Any, /, *, loc: K | int | str) -> bool:
        """The function to be called on each value in the JSON object."""


@dataclass
class Config:
    """Configuration for the JSONProcessor."""

    process_subclasses: bool
    """Whether to (also) process subclasses of the target types."""

    process_type_changes: bool
    """Whether to re-process values if their type is updated.

    Can lead to recursion errors if not handled correctly.
    """

    process_pydantic_computed_fields: bool
    """Whether to process Pydantic model computed fields alongside the regular model fields."""

    process_pydantic_model_properties: bool
    """Whether to process Pydantic model properties alongside the model fields."""

    ignored_loc_lookup_errors: tuple[type[BaseException], ...]
    """Exception types to ignore when looking up locations in the JSON object."""


class JSONProcessor(mixin.InstanceCache, cache_id_attr="identifier"):
    """Recursively process JSON objects with user-defined callbacks.

    Attributes:
        _cbs (dict): A mapping of types to a list of callback functions to be executed on
            the values of the given type.
        identifier (str): A unique identifier for the JSONProcessor instance. Defaults to
            the hash of the instance.
        process_subclasses (bool): Whether to (also) process subclasses of the target types.
            Defaults to True.
        process_type_changes (bool): Whether to re-process values if their type is updated.
            Can lead to recursion errors if not handled correctly. Defaults to False.
    """

    _DECORATED_CALLBACKS: ClassVar[set[Callback[..., Any]]] = set()

    __SENTINEL: Final[Sentinel] = Sentinel()

    class CallbackDefinition(NamedTuple):
        """A named tuple to hold the callback function and its associated data.

        Attributes:
            callback (Callback): The callback function to execute on the target values.
            item_filter (ItemFilter | None): An optional function to use to filter target
                values before processing them. Defaults to None.
            allow_callback_failures (bool): Whether to allow callback failures. Defaults to False.
        """

        callback: Callback[..., Any]
        item_filter: ItemFilter | None = None
        allow_callback_failures: bool = False

    CallbackMappingInput = dict[
        type[Any] | None,
        Callback[..., Any]
        | CallbackDefinition
        | Collection[
            Callback[..., Any]
            | tuple[Callback[..., Any],]
            | tuple[Callback[..., Any], ItemFilter]
            | tuple[Callback[..., Any], ItemFilter, bool]
            | CallbackDefinition,
        ],
    ]

    CallbackMapping = dict[type[Any], list[CallbackDefinition]]

    class Break(wg_exc.WGUtilitiesError):
        """Escape hatch to allow breaking out of the processing loop from within a callback."""

    def __init__(
        self,
        _cbs: CallbackMappingInput | None = None,
        /,
        *,
        identifier: str = "",
        process_subclasses: bool = True,
        process_type_changes: bool = False,
        process_pydantic_computed_fields: bool = False,
        process_pydantic_model_properties: bool = False,
        ignored_loc_lookup_errors: tuple[type[Exception], ...] = (),
    ) -> None:
        """Initialize the JSONProcessor."""
        self.callback_mapping: JSONProcessor.CallbackMapping = defaultdict(list)

        self.config = Config(
            process_subclasses=process_subclasses,
            process_type_changes=process_type_changes,
            process_pydantic_computed_fields=process_pydantic_computed_fields,
            process_pydantic_model_properties=process_pydantic_model_properties,
            ignored_loc_lookup_errors=ignored_loc_lookup_errors,
        )

        self.identifier = identifier or hash(self)

        if _cbs:
            for target_type, cb_val in _cbs.items():
                cb_list: list[JSONProcessor.CallbackDefinition] = []
                if callable(cb_val):
                    # Single callback provided for type
                    cb_list.append(self.cb(cb_val))
                elif isinstance(cb_val, JSONProcessor.CallbackDefinition):
                    # Single CallbackDefinition named tuple provided for type
                    cb_list.append(cb_val)
                elif isinstance(cb_val, Collection):
                    for cb in cb_val:
                        if callable(cb):
                            # Single callbacks provided for type
                            cb_list.append(self.cb(cb))
                        elif isinstance(cb, tuple):
                            # Partial (or full) CallbackDefinition
                            cb_list.append(self.cb(*cb))
                        else:
                            raise InvalidCallbackError(cb, type(cb), callback=cb)
                else:
                    raise InvalidCallbackError(cb_val, type(cb_val), callback=cb_val)

                for cb_def in cb_list:
                    self.register_callback(target_type, cb_def)

    @staticmethod
    def cb(
        callback: Callback[..., Any],
        item_filter: ItemFilter | None = None,
        allow_callback_failures: bool = False,  # noqa: FBT001,FBT002
        *,
        allow_mutation: bool = True,
    ) -> CallbackDefinition:
        """Create a CallbackDefinition for the given callback."""

        if callback.__name__ == "<lambda>":
            callback = JSONProcessor.callback(allow_mutation=allow_mutation)(callback)

        if item_filter and not callable(item_filter):
            raise InvalidItemFilterError(item_filter, callback=callback)

        if not isinstance(allow_callback_failures, bool):
            raise InvalidCallbackError(
                allow_callback_failures,
                type(allow_callback_failures),
                callback=callback,
            )

        return JSONProcessor.CallbackDefinition(
            callback=callback,
            item_filter=item_filter,
            allow_callback_failures=allow_callback_failures,
        )

    def _get_callbacks(
        self,
        typ: type[Any],
    ) -> Generator[CallbackDefinition, None, None]:
        if self.config.process_subclasses:
            for cb_typ in self.callback_mapping:
                if issubclass(typ, cb_typ):
                    yield from self.callback_mapping[cb_typ]
        elif callback_list := self.callback_mapping.get(typ):
            yield from callback_list

    def _get_item(
        self,
        obj: Mapping[K, V] | Sequence[object] | BaseModel,
        loc: K | int | str,
    ) -> object | Sentinel:
        with suppress(*self.config.ignored_loc_lookup_errors):
            try:
                return obj[loc]  # type: ignore[index]
            except LookupError:
                raise LocNotFoundError(loc, obj) from None
            except TypeError as exc:
                if not isinstance(loc, str) or not (
                    str(exc).endswith("is not subscriptable")
                    or str(exc) == "list indices must be integers or slices, not str"
                ):
                    raise

            try:
                return getattr(obj, loc)  # type: ignore[no-any-return]
            except AttributeError:
                raise LocNotFoundError(loc, obj) from None

        return JSONProcessor.__SENTINEL

    @staticmethod
    def _set_item(
        obj: Mapping[K, V] | Sequence[object] | BaseModel,
        loc: K | int | str,
        val: V,
    ) -> None:
        with suppress(TypeError):
            obj[loc] = val  # type: ignore[index]
            return

        if not isinstance(loc, str):
            return

        with suppress(AttributeError):
            setattr(obj, loc, val)

        return

    @overload
    def _iterate(self, obj: Mapping[K, V]) -> Iterator[K]:
        ...

    @overload
    def _iterate(self, obj: Sequence[V]) -> Iterator[int]:
        ...

    @overload
    def _iterate(self, obj: BaseModel) -> Iterator[str]:
        ...

    def _iterate(
        self,
        obj: Mapping[K, V] | Sequence[V] | BaseModel,
    ) -> Iterator[K] | Iterator[int] | Iterator[str]:
        if isinstance(obj, Sequence):
            return iter(range(len(obj)))

        if isinstance(obj, BaseModel):
            iterables: list[Iterable[str]] = [obj.model_fields.keys()]

            if self.config.process_pydantic_model_properties:
                iterables.append(
                    sorted(
                        {
                            name
                            for name, prop in inspect.getmembers(obj.__class__)
                            if isinstance(prop, property)
                            and name not in BASE_MODEL_PROPERTIES
                        },
                    ),
                )

            if self.config.process_pydantic_computed_fields:
                iterables.append(obj.model_computed_fields.keys())

            return iter(chain(*iterables))

        return iter(obj)

    def _process_item(
        self,
        *,
        obj: Mapping[Any, Any] | Sequence[Any] | BaseModel,
        loc: Any | int,
        cb: Callback[..., Any],
        depth: int,
        orig_item_type: type[Any],
        kwargs: dict[str, Any],
    ) -> None:
        try:
            out = cb(
                _value_=self._get_item(obj, loc),
                _loc_=loc,
                _obj_type_=type(obj),
                _depth_=depth,
                **kwargs,
            )
        except TypeError as exc:
            arg_error: type[InvalidCallbackArgumentsError]
            for arg_error in InvalidCallbackArgumentsError.subclasses():  # type: ignore[assignment]
                if match := arg_error.PATTERN.search(str(exc)):
                    raise arg_error(*match.groups(), callback=cb) from None

            raise

        if out is not self.__SENTINEL:
            self._set_item(obj, loc, out)

            if self.config.process_type_changes and type(out) != orig_item_type:
                self._process_loc(
                    obj=obj,
                    loc=loc,
                    depth=depth,
                    kwargs=kwargs,
                )

    def _process_loc(
        self,
        *,
        obj: Mapping[Any, Any] | Sequence[Any] | BaseModel,
        loc: Any | int,
        depth: int,
        kwargs: dict[str, Any],
    ) -> None:
        try:
            item = self._get_item(obj, loc)
        except LocNotFoundError:
            return

        for cb, item_filter, allow_failures in self._get_callbacks(
            orig_item_type := type(item),
        ):
            if item_filter is None or bool(item_filter(item, loc=loc)):
                try:
                    self._process_item(
                        obj=obj,
                        loc=loc,
                        cb=cb,
                        depth=depth,
                        orig_item_type=orig_item_type,
                        kwargs=kwargs,
                    )
                except (self.Break, InvalidCallbackArgumentsError):
                    raise
                except Exception:
                    if not allow_failures:
                        raise

    def process(
        self,
        obj: Mapping[K, object] | Sequence[object],
        /,
        __depth: int = 0,
        __processed_models: set[BaseModel] | None = None,
        **kwargs: Any,
    ) -> None:
        """Recursively process a JSON object with the registered callbacks.

        Args:
            obj: The JSON object to process.
            kwargs: Any additional keyword arguments to pass to the callback(s).
        """

        for loc in self._iterate(obj):
            try:
                self._process_loc(
                    obj=obj,
                    loc=loc,
                    depth=__depth,
                    kwargs=kwargs,
                )
            except self.Break:
                break

            item = self._get_item(obj, loc)

            if isinstance(item, Mapping | Sequence) and not isinstance(
                item,
                (str, bytes),
            ):
                self.process(
                    item,
                    _JSONProcessor__depth=__depth + 1,
                    _JSONProcessor__processed_models=__processed_models,
                    **kwargs,
                )
            elif (
                PYDANTIC_INSTALLED
                and isinstance(item, BaseModel)
                and item not in (__processed_models or set())
            ):
                self.process_model(
                    item,
                    _JSONProcessor__depth=__depth + 1,
                    _JSONProcessor__processed_models=__processed_models,
                    **kwargs,
                )

    if PYDANTIC_INSTALLED:

        def process_model(
            self,
            model: BaseModel,
            /,
            __depth: int = 0,
            __processed_models: set[BaseModel] | None = None,
            **kwargs: Any,
        ) -> None:
            """Recursively process a Pydantic model with the registered callbacks.

            Args:
                model: The Pydantic model to process.
                kwargs: Any additional keyword arguments to pass to the callback(s).
            """
            if __processed_models is None:
                __processed_models = {model}
            else:
                __processed_models.add(model)

            for loc in self._iterate(model):
                try:
                    self._process_loc(obj=model, loc=loc, depth=__depth, kwargs=kwargs)
                except self.Break:
                    break

                try:
                    item = getattr(model, loc)
                except self.config.ignored_loc_lookup_errors:
                    continue

                if isinstance(item, BaseModel) and item not in __processed_models:
                    self.process_model(
                        item,
                        _JSONProcessor__depth=__depth + 1,
                        _JSONProcessor__processed_models=__processed_models,
                        **kwargs,
                    )
                elif isinstance(item, Mapping | Sequence) and not isinstance(
                    item,
                    (str, bytes),
                ):
                    self.process(
                        item,
                        _JSONProcessor__depth=__depth + 1,
                        _JSONProcessor__processed_models=__processed_models,
                        **kwargs,
                    )

    def register_callback(
        self,
        target_type: type[Any] | None,
        callback_def: CallbackDefinition,
    ) -> None:
        """Register a new callback for use when processing any JSON objects.

        Args:
            target_type (type): The type of the values to be processed.
            callback_def (CallbackDefinition): The callback definition to register.
        """
        decorated = (
            callback_def.callback.__func__
            if inspect.ismethod(callback_def.callback)
            else callback_def.callback
        )

        if decorated not in JSONProcessor._DECORATED_CALLBACKS:
            raise CallbackNotDecoratedError(decorated)  # type: ignore[arg-type]

        if target_type is None:
            target_type = type(None)

        self.callback_mapping[target_type].append(callback_def)

    @overload
    @classmethod
    def callback(
        cls,
        *,
        allow_mutation: Literal[True] = True,
    ) -> Callable[[Callable[P, R]], Callback[P, R]]:
        ...

    @overload
    @classmethod
    def callback(
        cls,
        *,
        allow_mutation: Literal[False],
    ) -> Callable[[Callable[P, R]], Callback[P, Sentinel]]:
        ...

    @overload
    @classmethod
    def callback(
        cls,
        *,
        allow_mutation: bool = ...,
    ) -> Callable[[Callable[P, R]], Callback[P, R | Sentinel]]:
        ...

    @classmethod
    def callback(
        cls,
        *,
        allow_mutation: bool = True,
    ) -> Callable[[Callable[P, R]], Callback[P, R | Sentinel]]:
        """Decorator to mark a function as a callback for use with the JSONProcessor.

        Warning:
            `allow_mutation` only blocks the return value from being used to update the input
            object. It does not prevent the callback from mutating the input object (or other
            objects passed in as arguments) in place.

        Args:
            allow_mutation (bool): Whether the callback is allowed to mutate the input object.
                Defaults to True.
        """

        def _decorator(func: Callable[P, R]) -> Callback[P, R | Sentinel]:
            """Decorator to mark a function as a callback for use with the JSONProcessor."""

            if isinstance(func, classmethod):
                raise InvalidCallbackError(
                    "@JSONProcessor.callback must be used _after_ @classmethod",
                    callback=func,
                )

            arg_names, kwarg_names = [], []

            for name, param in inspect.signature(func).parameters.items():
                if param.kind == param.POSITIONAL_ONLY:
                    arg_names.append(name)
                else:
                    kwarg_names.append(name)

            def filter_kwargs(
                kwargs: dict[str, Any],
                /,
            ) -> tuple[list[Any], dict[str, Any]]:
                a = []
                for an in arg_names:
                    with suppress(KeyError):
                        a.append(kwargs[an])

                kw = {}
                for kn in kwarg_names:
                    with suppress(KeyError):
                        kw[kn] = kwargs[kn]

                return a, kw

            # This is the same `cb` called in the `JSONProcessor._process_loc` method - no positional
            # arguments are explicitly passed in (and would be rehjected by `JSONProcessor.process` anyway),
            # unless the callback is a bound method. In this case, the `cls`/`self` argument is passed in
            # as the first positional argument, hence the need for `*bound_args` below

            if allow_mutation:

                @wraps(func)
                def cb(*bound_args: P.args, **process_kwargs: P.kwargs) -> R:
                    args, kwargs = filter_kwargs(process_kwargs)
                    return func(*bound_args, *args, **kwargs)

            else:

                @wraps(func)
                def cb(
                    *bound_args: P.args,
                    **process_kwargs: P.kwargs,
                ) -> Sentinel:
                    args, kwargs = filter_kwargs(process_kwargs)
                    func(*bound_args, *args, **kwargs)
                    return JSONProcessor.__SENTINEL

            cls._DECORATED_CALLBACKS.add(cb)

            return cb

        return _decorator


__all__ = ["JSONProcessor", "Callback", "ItemFilter"]
