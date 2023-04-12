"""Useful functions for working with JSON/dictionaries."""
from __future__ import annotations

from collections.abc import Callable, MutableMapping, Sequence
from logging import DEBUG, getLogger
from typing import Any, Protocol, Union

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


JSONVal = Union[
    None, object, bool, str, float, int, list["JSONVal"], "JSONObj", dict[str, object]
]
JSONObj = MutableMapping[str, JSONVal]


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


class TargetProcessorFunc(Protocol):
    """Typing protocol for the user-defined function passed into the below functions."""

    def __call__(
        self,
        value: JSONVal,
        *,
        dict_key: str | None = None,
        list_index: int | None = None,
    ) -> JSONVal:
        """The function to be called on each value in the JSON object."""  # noqa: D401


def process_list(
    lst: list[JSONVal],
    *,
    target_type: type[object] | tuple[type[object], ...],
    target_processor_func: TargetProcessorFunc,
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
        target_processor_func (Callable): a function to apply to instances of
         `target_type`
        pass_on_fail (bool): ignore failure in either op function
        log_op_func_failures (bool): log any failures in either op function
        single_keys_to_remove (list): a list of keys that can be "expanded" up to the
         parent key

    Raises:
        Exception: if the `target_processor_func` fails and `pass_on_fail` is False
    """
    for i, elem in enumerate(lst):
        if isinstance(elem, target_type):
            try:
                lst[i] = target_processor_func(elem, list_index=i)
            except Exception as exc:  # pylint: disable=broad-except
                if log_op_func_failures:
                    LOGGER.error("Unable to process item at index %i: %s", i, repr(exc))
                if not pass_on_fail:
                    raise
        elif isinstance(elem, dict):
            traverse_dict(
                elem,
                target_type=target_type,
                target_processor_func=target_processor_func,
                pass_on_fail=pass_on_fail,
                log_op_func_failures=log_op_func_failures,
                single_keys_to_remove=single_keys_to_remove,
            )
        elif isinstance(elem, list):
            process_list(
                elem,
                target_type=target_type,
                target_processor_func=target_processor_func,
                pass_on_fail=pass_on_fail,
                log_op_func_failures=log_op_func_failures,
            )


def traverse_dict(
    payload_json: JSONObj,
    *,
    target_type: type[object] | tuple[type[object], ...] | type[Callable[..., Any]],
    target_processor_func: TargetProcessorFunc,
    pass_on_fail: bool = True,
    log_op_func_failures: bool = False,
    single_keys_to_remove: Sequence[str] | None = None,
) -> None:
    # pylint: disable=too-many-branches
    """Traverse dict, applying`dict_op_func` to any values of type `target_type`.

    Args:
        payload_json (dict): the JSON object to traverse
        target_type (type): the target type to apply functions to
        target_processor_func (Callable): a function to apply to instances of
         `target_type`
        pass_on_fail (bool): ignore failure in either op function
        log_op_func_failures (bool): log any failures in either op function
        single_keys_to_remove (list): a list of keys that can be "expanded" up to the
         parent key from a dict of length one, e.g.:
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
    for k, v in payload_json.items():
        if isinstance(v, target_type):
            try:
                payload_json.update({k: target_processor_func(v, dict_key=k)})
                if isinstance(payload_json.get(k), dict):
                    traverse_dict(
                        payload_json,
                        target_type=target_type,
                        target_processor_func=target_processor_func,
                        pass_on_fail=pass_on_fail,
                        log_op_func_failures=log_op_func_failures,
                        single_keys_to_remove=single_keys_to_remove,
                    )
            except Exception as exc:  # pylint: disable=broad-except
                if log_op_func_failures:
                    LOGGER.error("Unable to process item with key %s: %s", k, repr(exc))
                if not pass_on_fail:
                    raise
        elif isinstance(v, dict):
            matched_single_key = False
            if len(v) == 1 and single_keys_to_remove is not None:
                if (only_key := next(iter(v.keys()))) in single_keys_to_remove:
                    matched_single_key = True
                    if isinstance(value := v.get(only_key), target_type):
                        try:
                            value = target_processor_func(value, dict_key=only_key)
                        except Exception as exc:  # pylint: disable=broad-except
                            if log_op_func_failures:
                                LOGGER.error(
                                    "Unable to process item with key %s: %s",
                                    k,
                                    repr(exc),
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

                    payload_json[k] = value

            if not matched_single_key:
                traverse_dict(
                    v,
                    target_type=target_type,
                    target_processor_func=target_processor_func,
                    pass_on_fail=pass_on_fail,
                    log_op_func_failures=log_op_func_failures,
                    single_keys_to_remove=single_keys_to_remove,
                )
        elif isinstance(v, list):
            process_list(
                v,
                target_type=target_type,
                target_processor_func=target_processor_func,
                pass_on_fail=pass_on_fail,
                log_op_func_failures=log_op_func_failures,
                single_keys_to_remove=single_keys_to_remove,
            )
