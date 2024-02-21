"""Unit Tests for the `add_file_handler` function."""

from __future__ import annotations

from logging import CRITICAL, getLogger
from typing import TYPE_CHECKING
from unittest.mock import patch

from wg_utilities.loggers.file_handler import add_file_handler, create_file_handler

if TYPE_CHECKING:
    from pathlib import Path


def test_file_handler_is_added_to_logger(temp_dir: Path) -> None:
    """Test that the create_file_handler function is called."""

    file_handler = create_file_handler(log_path := temp_dir / "foo.log")

    logger = getLogger("test_file_handler_is_added_to_logger")

    with patch(
        "wg_utilities.loggers.file_handler.create_file_handler",
    ) as mock_create_file_handler:
        mock_create_file_handler.return_value = file_handler

        add_file_handler(logger, logfile_path=log_path, level=CRITICAL)

    assert logger.handlers[0] == file_handler
    assert len(logger.handlers) == 1


def test_create_file_handler_is_called(temp_dir: Path) -> None:
    """Test that the create_file_handler function is called."""

    file_handler = create_file_handler(log_path := temp_dir / "bar.log")

    logger = getLogger("test_create_file_handler_is_called")

    with patch(
        "wg_utilities.loggers.file_handler.create_file_handler",
    ) as mock_create_file_handler:
        mock_create_file_handler.return_value = file_handler

        add_file_handler(logger, logfile_path=log_path, level=CRITICAL)

    mock_create_file_handler.assert_called_once_with(
        logfile_path=log_path,
        level=CRITICAL,
        create_directory=True,
    )
