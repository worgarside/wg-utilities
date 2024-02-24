"""Useful functions for working with JSON/dictionaries."""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from logging import DEBUG, getLogger
from typing import Any, Protocol, TypeVar, Union, cast

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)

JSONVal = Union[
    None,
    object,
    bool,
    str,
    float,
    int,
    list["JSONVal"],
    "JSONObj",
    dict[str, object],
]
JSONObj = MutableMapping[str, JSONVal]
JSONArr = Sequence[JSONVal]


def set_nested_value(
    *,
    json_obj: dict[Any, Any],
    keys: list[str],
    target_value: Any,
    final_key: str | None = None,
) -> None:
    """Update a nested value in a dictionary.

    Args:
        json_obj (dict): the JSON object to update
        keys (list): a list of keys used to traverse the dictionary
        target_value (Any): the value to set at the given location/path
        final_key (str): the final key, the value of which we're actually setting
    """

    final_key = final_key or keys.pop()

    if len(keys) > 0:
        set_nested_value(
            json_obj=json_obj.get(keys.pop(0), {}),
            keys=keys,
            target_value=target_value,
            final_key=final_key,
        )
    else:
        json_obj[final_key] = target_value


V_contra = TypeVar("V_contra", contravariant=True, bound=JSONVal)
V = TypeVar("V", bound=JSONVal)


class TargetProcessorFunc(Protocol[V_contra]):
    """Typing protocol for the user-defined function passed into the below functions."""

    def __call__(
        self,
        value: V_contra,
        *,
        dict_key: str | None = None,
        list_index: int | None = None,
    ) -> JSONVal:
        """The function to be called on each value in the JSON object."""


def process_list(
    lst: list[JSONVal],
    /,
    *,
    target_type: type[V] | tuple[type[V], ...],
    target_processor_func: TargetProcessorFunc[V],
    pass_on_fail: bool = True,
    log_op_func_failures: bool = False,
    single_keys_to_remove: Sequence[str] | None = None,
) -> None:
    """Iterate through a list, applying `list_op_func` to any `target_type` instances.

    This is used in close conjunction with `process_dict` to recursively process
    a JSON object and apply a given function to any values of a given type across the
    whole object.

    Failures in the given function can be ignored by setting `pass_on_fail` to `True`,
    and/or logged by setting `log_op_func_failures` to `True`. If both are set to
    `True`, then the function will log the failure and then continue.

    Args:
        lst (list): the list to iterate through
        target_type (type): the target type to apply functions to
        target_processor_func (Callable): a function to apply to instances of `target_type`
        pass_on_fail (bool): ignore failure in either op function
        log_op_func_failures (bool): log any failures in either op function
        single_keys_to_remove (list): a list of keys that can be "expanded" up to the parent key

    Raises:
        Exception: if the `target_processor_func` fails and `pass_on_fail` is False
    """
    for i, elem in enumerate(lst):
        if isinstance(elem, target_type):
            try:
                lst[i] = target_processor_func(cast(V, elem), list_index=i)
            except Exception:
                if log_op_func_failures:
                    LOGGER.exception("Unable to process item at index %i", i)

                if not pass_on_fail:
                    raise

        # If the new(?) value is a dict/list, then it needs to be processed
        # before continuing to the next elem in this list
        if isinstance(lst[i], dict | list):
            process_json_object(
                lst[i],  # type: ignore[arg-type]
                target_type=target_type,
                target_processor_func=target_processor_func,
                pass_on_fail=pass_on_fail,
                log_op_func_failures=log_op_func_failures,
                single_keys_to_remove=single_keys_to_remove,
            )


def traverse_dict(  # noqa: PLR0912
    obj: JSONObj,
    /,
    *,
    target_type: type[V] | tuple[type[V], ...],
    target_processor_func: TargetProcessorFunc[V],
    pass_on_fail: bool = True,
    log_op_func_failures: bool = False,
    single_keys_to_remove: Sequence[str] | None = None,
) -> None:
    """Traverse dict, applying`target_processor_func` to any values of type `target_type`.

    Args:
        obj (dict): the JSON object to traverse
        target_type (type): the target type to apply functions to
        target_processor_func (Callable): a function to apply to instances of `target_type`
        pass_on_fail (bool): ignore failure in either op function
        log_op_func_failures (bool): log any failures in either op function
        single_keys_to_remove (list): a list of keys that can be "expanded" up to the parent key from a dict of
            length one, e.g.:
            ... {
            ...     "parent_1": "something",
            ...     "parent_2": {
            ...         "uselessKey": "actual value"
            ...     }
            ... }
            would go to
            ... {
            ...     "parent_1": "something",
            ...     "parent_2": "actual value"
            ... }

    Raises:
        Exception: if the `target_processor_func` fails and `pass_on_fail` is False
    """
    for k, v in obj.items():
        if isinstance(v, target_type):
            try:
                obj.update({k: target_processor_func(cast(V, v), dict_key=k)})
                if isinstance(obj[k], dict):
                    traverse_dict(
                        # If a dict has been created from a non-dict type (e.g. `loads("{...}")`,
                        # then we need to traverse the current object again, as the new dict may
                        # contain more instances of `target_type`. Otherwise, traverse
                        # the dict (that already existed).
                        obj if target_type is not dict else cast(JSONObj, obj[k]),
                        target_type=target_type,
                        target_processor_func=target_processor_func,
                        pass_on_fail=pass_on_fail,
                        log_op_func_failures=log_op_func_failures,
                        single_keys_to_remove=single_keys_to_remove,
                    )
            except Exception:
                if log_op_func_failures:
                    LOGGER.exception("Unable to process item with key %s", k)
                if not pass_on_fail:
                    raise

            continue

        if isinstance(v, dict):
            matched_single_key = False
            if (
                len(v) == 1
                and single_keys_to_remove is not None
                and (only_key := next(iter(v.keys()))) in single_keys_to_remove
            ):
                matched_single_key = True
                if isinstance(value := v.get(only_key), target_type):
                    try:
                        value = target_processor_func(cast(V, value), dict_key=only_key)
                    except Exception:
                        if log_op_func_failures:
                            LOGGER.exception(
                                "Unable to process item with key %s",
                                k,
                            )
                        if not pass_on_fail:
                            raise

                if isinstance(value, dict):
                    # Wrap the value, so that if the top level key is one
                    # of `single_keys_to_remove` then it's processed
                    # correctly
                    tmp_wrapper: JSONObj = {"-": value}
                    traverse_dict(
                        tmp_wrapper,
                        target_type=target_type,
                        target_processor_func=target_processor_func,
                        pass_on_fail=pass_on_fail,
                        log_op_func_failures=log_op_func_failures,
                        single_keys_to_remove=single_keys_to_remove,
                    )

                    value = tmp_wrapper["-"]

                obj[k] = value

            if not matched_single_key:
                traverse_dict(
                    v,
                    target_type=target_type,
                    target_processor_func=target_processor_func,
                    pass_on_fail=pass_on_fail,
                    log_op_func_failures=log_op_func_failures,
                    single_keys_to_remove=single_keys_to_remove,
                )

            continue

        if isinstance(v, list):
            process_list(
                v,
                target_type=target_type,
                target_processor_func=target_processor_func,
                pass_on_fail=pass_on_fail,
                log_op_func_failures=log_op_func_failures,
                single_keys_to_remove=single_keys_to_remove,
            )


class InvalidJsonObjectError(Exception):
    """Raised when an invalid JSON object/array is passed to `process_json_object`."""

    def __init__(self, obj: Any) -> None:
        """Initialize the exception."""
        super().__init__(
            f"Input object must be a dict or list, not {type(obj)!r}",
        )


def process_json_object(
    obj: JSONObj | JSONArr,
    /,
    *,
    target_type: type[V] | tuple[type[V], ...],
    target_processor_func: TargetProcessorFunc[V],
    pass_on_fail: bool = True,
    log_op_func_failures: bool = False,
    single_keys_to_remove: Sequence[str] | None = None,
) -> None:
    """Generic entry point to process dicts and/or lists.

    Raises:
        InvalidJsonObjectError: if an invalid JSON object/array is passed
    """

    if isinstance(obj, dict):
        traverse_dict(
            obj,
            target_type=target_type,
            target_processor_func=target_processor_func,
            pass_on_fail=pass_on_fail,
            log_op_func_failures=log_op_func_failures,
            single_keys_to_remove=single_keys_to_remove,
        )
    elif isinstance(obj, list):
        process_list(
            obj,
            target_type=target_type,
            target_processor_func=target_processor_func,
            pass_on_fail=pass_on_fail,
            log_op_func_failures=log_op_func_failures,
            single_keys_to_remove=single_keys_to_remove,
        )
    else:
        raise InvalidJsonObjectError(obj)
