"""One-off functions that are useful across many different projects/use-cases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator


def chunk_list(lst: list[Any], chunk_len: int) -> Generator[list[Any], None, None]:
    """Yield successive n-sized chunks from lst.

    Examples:
        >>> chunk_list([1, 2, 3, 4, 5, 6, 7], 2)
        [1, 2]
        [3, 4]
        [5, 6]
        [7]

    Args:
        lst (list): the list to split into chunks
        chunk_len (int): number of items per chunk

    Yields:
        list: an N-sized chunk of the main list

    Raises:
        ValueError: if n is < 1
    """

    if chunk_len < 1:
        raise ValueError("`chunk_len` must be a positive integer")

    for i in range(0, len(lst), chunk_len):
        yield lst[i : i + chunk_len]


def flatten_dict(
    nested_dict: dict[str, object],
    *,
    join_char: str = ".",
    exclude_keys: list[str] | None = None,
    exact_keys: bool = False,
    _parent_key: str = "",
) -> dict[str, Any]:
    """Flatten a nested dictionary into a single level dictionary.

    This function recursively traverses a dictionary and flattens any nested JSON
    so the resultant dict has no values of type dict. This allows for easier processing
    into Redshift

    Examples:
        >>> flatten_dict(
        ...     {
        ...         "one": 1,
        ...         "two": {
        ...             "three": 3,
        ...             "four": 4,
        ...         },
        ...         "five": {"six": 6},
        ...     },
        ...     join_char="-",
        ...     exclude_keys=["five"],
        ... )
        {
            "one": 1,
            "two-three": 3,
            "two-four": 4,
            "five": {"six": 6}
        }

        >>> flatten_dict(
        ...     {
        ...         "one": 1,
        ...         "two": {
        ...             "three": 3,
        ...             "four": 4,
        ...         },
        ...         "five": {"two": {"six": 6}},
        ...     },
        ...     join_char="-",
        ...     exclude_keys=["five-two"],
        ...     exact_keys=True,
        ... )

    Args:
        nested_dict (dict): the dict to be flattened
        join_char (str): the character(s) to use when joining nested keys to form a
            single key
        exclude_keys (list): list of keys to exclude when flatting the dict
        exact_keys (bool): whether the excluded list of keys contains the exact
            flattened key, e.g. for `{"one":{"two":{"three":3}}` the exact key would be
            `one.two` or if it should exclude all keys regardless of parent
        _parent_key (str): the string that keeps track of all the nested keys,
            for the initial use this should be an empty string, which is the
            default

    Returns:
        dict: a flattened dict
    """
    output = {}

    for k, v in nested_dict.items():
        new_parent_key = (
            k if not _parent_key or (not exact_keys) else join_char.join([_parent_key, k])
        )
        if (
            isinstance(v, dict)
            and len(v) > 0
            and new_parent_key not in (e_keys := exclude_keys or [])
        ):
            output.update(
                {
                    join_char.join([str(k), str(k2)]): v2
                    for k2, v2 in flatten_dict(
                        v,
                        join_char=join_char,
                        exclude_keys=e_keys,
                        exact_keys=exact_keys,
                        _parent_key=new_parent_key,
                    ).items()
                },
            )
        else:
            output[k] = v

    return output


def try_float(v: Any, default: Any = 0.0) -> object:
    """Try to cast a value to a float, and returns a default if it fails.

    Examples:
        >>> try_float("12.34")
        12.34

        >>> try_float("ABC", -1)
        -1

        >>> try_float(1.2, 10)
        1.2

    Args:
        v (Union[str, bytes, bytearray, SupportsFloat, _SupportsIndex]): The
            value to be cast to a float
        default (object): The value to be returned if the casting fails

    Returns:
        float: The value passed in, in float format, or the default
    """

    try:
        return float(v)
    except (ValueError, TypeError):
        return default
