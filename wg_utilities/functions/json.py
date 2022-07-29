"""Useful functions for working with JSON/dictionaries"""
from logging import DEBUG, getLogger
from typing import Any, Callable, Dict, List, Optional, Sequence, Type

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


def set_nested_value(
    *,
    json_obj: Dict[Any, Any],
    keys: List[str],
    target_value: Any,
    final_key: Optional[str] = None,
) -> None:
    """Update a nested value in a dictionary

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


def process_list(
    lst: List[Any],
    *,
    target_type: Type[Any],
    target_processor_func: Callable[[Any], Any],
    pass_on_fail: bool = True,
    log_op_func_failures: bool = False,
    single_keys_to_remove: Optional[Sequence[str]] = None,
) -> None:
    """Iterates through a list and applies `list_op_func` to any instances of
    `target_type`

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
                lst[i] = target_processor_func(elem)
            except Exception as exc:  # pylint: disable=broad-except
                if log_op_func_failures:
                    LOGGER.debug(str(exc))
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
    payload_json: Dict[Any, Any],
    *,
    target_type: Type[Any],
    target_processor_func: Callable[[Any], Any],
    pass_on_fail: bool = True,
    log_op_func_failures: bool = False,
    single_keys_to_remove: Optional[Sequence[str]] = None,
) -> None:
    # pylint: disable=too-many-branches,too-many-nested-blocks
    """Recursively traverse a JSON object and apply `dict_op_func` to any values
    of type `target_type`

    Args:
        payload_json (dict): the JSON object to traverse
        target_type (type): the target type to apply functions to
        target_processor_func (Callable): a function to apply to instances of
         `target_type`
        pass_on_fail (bool): ignore failure in either op function
        log_op_func_failures (bool): log any failures in either op function
        single_keys_to_remove (list): a list of keys that can be "expanded" up to the
         parent key, e.g.:
            ... {
            ...     "parent_1": "something",
            ...     "parent_2": {
            ...         "val": "actual value"
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
                payload_json.update({k: target_processor_func(v)})
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
                    LOGGER.error(str(exc))
                if not pass_on_fail:
                    raise
        elif isinstance(v, dict):
            matched_single_key = False
            if len(v) == 1 and single_keys_to_remove is not None:
                if (only_key := next(iter(v.keys()))) in single_keys_to_remove:
                    matched_single_key = True
                    if isinstance(value := v.get(only_key), target_type):
                        try:
                            value = target_processor_func(value)

                            if isinstance(value, dict):
                                # Wrap the value, so that if the top level key is one
                                # of `single_keys_to_remove` then it's processed
                                # correctly
                                tmp_wrapper = {"-": value}
                                traverse_dict(
                                    tmp_wrapper,
                                    target_type=target_type,
                                    target_processor_func=target_processor_func,
                                    pass_on_fail=pass_on_fail,
                                    log_op_func_failures=log_op_func_failures,
                                    single_keys_to_remove=single_keys_to_remove,
                                )

                                value = tmp_wrapper["-"]
                        except Exception as exc:  # pylint: disable=broad-except
                            if log_op_func_failures:
                                LOGGER.error(str(exc))
                            if not pass_on_fail:
                                raise
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
