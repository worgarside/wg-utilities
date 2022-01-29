"""Functions for string manipulation"""


def cleanse_string(value):
    """Remove all non-alphanumeric characters from a string

    Args:
        value (str): the input string value

    Returns:
        str: the cleansed string
    """
    return "".join([char for char in value if char.isalnum()])
