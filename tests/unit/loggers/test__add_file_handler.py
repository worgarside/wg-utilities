"""Unit Tests for the `add_file_handler` function."""

from __future__ import annotations

from logging import CRITICAL, getLogger
from pathlib import Path
from unittest.mock import patch

from wg_utilities.loggers import add_file_handler, create_file_handler


def test_file_handler_is_added_to_logger() -> None:
    """Test that the create_file_handler function is called."""

    file_handler = create_file_handler(log_path := Path(__file__).parent / "foo.log")

    logger = getLogger(__name__)

    with patch("wg_utilities.loggers.create_file_handler") as mock_create_file_handler:
        mock_create_file_handler.return_value = file_handler
        add_file_handler(logger, logfile_path=log_path, level=CRITICAL)

    assert logger.handlers[0] == file_handler
    assert len(logger.handlers) == 1

    log_path.unlink()


def test_create_file_handler_is_called() -> None:
    """Test that the create_file_handler function is called."""

    file_handler = create_file_handler(log_path := Path(__file__).parent / "foo.log")

    logger = getLogger(__name__)

    with patch("wg_utilities.loggers.create_file_handler") as mock_create_file_handler:
        mock_create_file_handler.return_value = file_handler
        add_file_handler(logger, logfile_path=log_path, level=CRITICAL)
        mock_create_file_handler.assert_called_once_with(
            logfile_path=log_path,
            level=CRITICAL,
            create_directory=True,
        )

    log_path.unlink()
