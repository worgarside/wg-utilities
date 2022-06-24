"""Useful functions for working with JSON/dictionaries"""
from logging import DEBUG, getLogger
from typing import Any, Callable, Dict, List, Optional, Type

from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


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
    dict_op_func: Callable[[Dict[Any, Any], Any, Any], None],
    list_op_func: Callable[[Any], None],
    pass_on_fail: bool = True,
    log_op_func_failures: bool = False,
) -> None:
    """Iterates through a list and applies `list_op_func` to any instances of
    `target_type`

    Args:
        lst (list): the list to iterate through
        target_type (type): the target type to apply functions to
        dict_op_func (Callable): a function to apply to instances of `target_type` in
         a dict
        list_op_func (Callable): a function to apply to instances of `target_type` in
         a list
        pass_on_fail (bool): ignore failure in either op function
        log_op_func_failures (bool): log any failures in either op function
    """
    for i, elem in enumerate(lst):
        if isinstance(elem, target_type):
            if pass_on_fail:
                try:
                    lst[i] = list_op_func(elem)
                except Exception as exc:  # pylint: disable=broad-except
                    if log_op_func_failures:
                        LOGGER.debug(str(exc))
            else:
                lst[i] = list_op_func(elem)
        elif isinstance(elem, dict):
            traverse_dict(
                elem,
                target_type=target_type,
                dict_op_func=dict_op_func,
                list_op_func=list_op_func,
                pass_on_fail=pass_on_fail,
                log_op_func_failures=log_op_func_failures,
            )
        elif isinstance(elem, list):
            process_list(
                elem,
                target_type=target_type,
                dict_op_func=dict_op_func,
                list_op_func=list_op_func,
                pass_on_fail=pass_on_fail,
                log_op_func_failures=log_op_func_failures,
            )


def traverse_dict(
    payload_json: Dict[Any, Any],
    *,
    target_type: Type[Any],
    dict_op_func: Callable[[Dict[Any, Any], Any, Any], None],
    list_op_func: Callable[[Any], Any],
    pass_on_fail: bool = True,
    log_op_func_failures: bool = False,
) -> None:
    """Recursively traverse a JSON object and apply `dict_op_func` to any values
    of type `target_type`

    Args:
        payload_json (dict): the JSON object to traverse
        target_type (type): the target type to apply functions to
        dict_op_func (Callable): a function to apply to instances of `target_type` in
         a dict
        list_op_func (Callable): a function to apply to instances of `target_type` in
         a list
        pass_on_fail (bool): ignore failure in either op function
        log_op_func_failures (bool): log any failures in either op function
    """
    for k, v in payload_json.items():
        if isinstance(v, target_type):
            if pass_on_fail:
                try:
                    dict_op_func(payload_json, k, v)
                except Exception as exc:  # pylint: disable=broad-except
                    if log_op_func_failures:
                        LOGGER.debug(str(exc))
            else:
                dict_op_func(payload_json, k, v)
        elif isinstance(v, dict):
            traverse_dict(
                v,
                target_type=target_type,
                dict_op_func=dict_op_func,
                list_op_func=list_op_func,
                pass_on_fail=pass_on_fail,
                log_op_func_failures=log_op_func_failures,
            )
        elif isinstance(v, list):
            process_list(
                v,
                target_type=target_type,
                dict_op_func=dict_op_func,
                list_op_func=list_op_func,
                pass_on_fail=pass_on_fail,
                log_op_func_failures=log_op_func_failures,
            )
