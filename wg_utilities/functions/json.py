"""Useful functions for working with JSON/dictionaries"""
from typing import Any, Dict, List, Optional


def set_nested_value(
    *,
    json_obj: Dict[Any, Any],
    keys: List[str],
    target_value: Any,
    final_key: Optional[str] = None
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
