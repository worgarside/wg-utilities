"""Set of functions for string manipulation."""

from __future__ import annotations

from re import sub


def cleanse_string(
    value: str,
    *,
    whitespace_amount: int | None = None,
    preserve_newlines: bool = False,
) -> str:
    """Remove all non-alphanumeric characters from a string.

    Args:
        value (str): the input string value
        whitespace_amount (int, optional): the number of spaces to replace whitespace
            for in a string. Setting to 0 preserves all whitespace, 1 is a single space,
            and so on. Defaults to None, which will remove all whitespace.
        preserve_newlines (bool, optional): whether to preserve newlines in the string.

    Returns:
        str: the cleansed string
    """
    inner_pattern = "a-zA-Z0-9"

    if preserve_newlines:
        inner_pattern += "\n"

    if whitespace_amount is None:
        return sub(rf"[^{inner_pattern}]", "", value)

    if whitespace_amount == 0:
        return sub(rf"[^{inner_pattern}\s]", "", value)

    return sub(r"\s+", " " * whitespace_amount, sub(rf"[^{inner_pattern}\s]", "", value))
