"""Useful functions for working with JSON/dictionaries."""

from __future__ import annotations

import inspect
import re
from collections import defaultdict
from collections.abc import Callable
from contextlib import suppress
from functools import wraps
from typing import (
    Any,
    ClassVar,
    Collection,
    Generator,
    Iterator,
    NamedTuple,
    ParamSpec,
    Protocol,
    TypeVar,
    overload,
)

from wg_utilities.exceptions._exception import BadDefinitionError
from wg_utilities.helpers.mixin import InstanceCache

P = ParamSpec("P")
R = TypeVar("R")
Callback = Callable[P, R]


class InvalidCallbackError(BadDefinitionError):
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

    def __call__(self, item: Any, /, *, loc: str | int) -> bool:
        """The function to be called on each value in the JSON object."""


class JSONProcessor(InstanceCache, cache_id_attr="identifier"):
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

    _DECORATED_CALLBACKS: ClassVar[set[Callable[..., Any]]] = set()

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

    def __init__(
        self,
        _cbs: CallbackMappingInput | None = None,
        /,
        *,
        identifier: str = "",
        process_subclasses: bool = True,
        process_type_changes: bool = False,
    ) -> None:
        """Initialize the JSONProcessor."""
        self.callback_mapping: JSONProcessor.CallbackMapping = defaultdict(list)

        self.process_subclasses = process_subclasses
        self.process_type_changes = process_type_changes

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
    ) -> CallbackDefinition:
        """Create a CallbackDefinition for the given callback."""

        if callback.__name__ == "<lambda>":
            callback = JSONProcessor.callback(callback)

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

    @overload
    @staticmethod
    def _iterate(obj: dict[Any, Any]) -> Iterator[Any]:
        ...

    @overload
    @staticmethod
    def _iterate(obj: list[Any]) -> Iterator[int]:
        ...

    @staticmethod
    def _iterate(
        obj: dict[Any, Any] | list[Any],
    ) -> Iterator[Any] | Iterator[int]:
        if isinstance(obj, list):
            return iter(range(len(obj)))

        return iter(obj)

    def _get_callbacks(
        self,
        typ: type[Any],
    ) -> Generator[CallbackDefinition, None, None]:
        if self.process_subclasses:
            for cb_typ in self.callback_mapping:
                if issubclass(typ, cb_typ):
                    yield from self.callback_mapping[cb_typ]
        elif callback_list := self.callback_mapping.get(typ):
            yield from callback_list

    def _process_loc(
        self,
        *,
        obj: dict[Any, Any] | list[Any],
        loc: Any | int,
        kwargs: dict[str, Any],
    ) -> None:
        try:
            orig_item_type = type(obj[loc])
        except (LookupError, TypeError):
            return

        for cb, item_filter, allow_failures in self._get_callbacks(orig_item_type):
            if item_filter is None or bool(item_filter(obj[loc], loc=loc)):
                try:
                    obj[loc] = cb(
                        _value_=obj[loc],
                        _loc_=loc,
                        _obj_type_=type(obj),
                        **kwargs,
                    )
                except TypeError as exc:
                    arg_error: type[InvalidCallbackArgumentsError]
                    for arg_error in InvalidCallbackArgumentsError.subclasses():  # type: ignore[assignment]
                        if match := arg_error.PATTERN.search(str(exc)):
                            raise arg_error(*match.groups(), callback=cb) from None

                    if not allow_failures:
                        raise
                except Exception:
                    if not allow_failures:
                        raise

                if self.process_type_changes and type(obj[loc]) != orig_item_type:
                    self._process_loc(obj=obj, loc=loc, kwargs=kwargs)

    def process(self, obj: dict[Any, Any] | list[Any], /, **kwargs: Any) -> None:
        """Recursively process a JSON object with the registered callbacks.

        Args:
            obj (dict[Any, Any] | list[Any]): The JSON object to process.
            kwargs (Any): Any additional keyword arguments to pass to the callbacks.
        """
        for loc in self._iterate(obj):
            self._process_loc(obj=obj, loc=loc, kwargs=kwargs)

            if issubclass(type(obj[loc]), dict | list):
                self.process(obj[loc], **kwargs)

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

    @classmethod
    def callback(
        cls,
        func: Callable[P, R],
    ) -> Callback[P, R]:
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
        @wraps(func)
        def cb(*bound_args: P.args, **process_kwargs: P.kwargs) -> R:
            args, kwargs = filter_kwargs(process_kwargs)
            return func(*bound_args, *args, **kwargs)

        cls._DECORATED_CALLBACKS.add(cb)

        return cb


__all__ = ["JSONProcessor", "Callback", "ItemFilter"]
