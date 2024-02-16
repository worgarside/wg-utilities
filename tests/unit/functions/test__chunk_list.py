"""Unit Tests for the `chunk_list` function."""

from __future__ import annotations

import pytest

from wg_utilities.functions import chunk_list


@pytest.mark.parametrize(
    ("user_input", "chunk_len", "want"),
    [
        ([], 5, []),
        (list(range(9)), 2, [[0, 1], [2, 3], [4, 5], [6, 7], [8]]),
        (list(range(10)), 2, [[0, 1], [2, 3], [4, 5], [6, 7], [8, 9]]),
        (list(range(10)), 20, [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]),
    ],
)
def test_chunk_list_with_varying_input(
    user_input: list[int],
    chunk_len: int,
    want: list[list[int]],
) -> None:
    """Test `chunk_list` handles varying inputs correctly."""

    chunks = list(chunk_list(user_input, chunk_len))

    assert chunks == want

    all_items = []
    for chunk in chunks:
        all_items.extend(chunk)

    assert all_items == user_input


@pytest.mark.parametrize(
    ("chunk_len", "exception_expected"),
    [(i, i < 1) for i in range(-10, 10)],
)
def test_chunk_len_less_than_one_throws_value_error(
    chunk_len: int,
    exception_expected: bool,
) -> None:
    """Test that a `chunk_len` value <1 throws a ValueError."""

    if exception_expected:
        with pytest.raises(ValueError) as exc_info:
            list(chunk_list([], chunk_len))

        assert str(exc_info.value) == "`chunk_len` must be a positive integer"
    else:
        list(chunk_list([], chunk_len))
