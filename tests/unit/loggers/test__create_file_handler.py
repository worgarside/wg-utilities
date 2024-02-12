"""Unit Tests for the `create_file_handler` function."""

from __future__ import annotations

from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger, getLevelName
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from freezegun import freeze_time

from wg_utilities.functions.datetime_helpers import utcnow
from wg_utilities.loggers.file_handler import create_file_handler


def test_target_directory_is_created() -> None:
    """Test that the target directory is created when requested."""

    with TemporaryDirectory() as tmp_dir:
        assert not (dir_path := Path(tmp_dir, "foo", "bar")).is_dir()
        assert not (file_path := dir_path / "baz.log").is_file()

        f_handler = create_file_handler(file_path, create_directory=True)

        assert dir_path.is_dir()
        assert file_path.is_file()

    assert f_handler.baseFilename == str(file_path)
    assert f_handler.level == DEBUG
    assert f_handler.mode == "a"


def test_target_directory_is_not_created() -> None:
    """Test that the target directory is not created when not requested."""
    dir_path = Path("/foo/bar")
    file_path = Path(dir_path, "baz.log")

    assert not dir_path.is_dir()
    assert not file_path.is_file()

    # The FileHandler instantiation will fail as the directory doesn't exist
    with pytest.raises(FileNotFoundError) as exc_info:
        create_file_handler(file_path, create_directory=False)

    assert not dir_path.is_dir()
    assert not file_path.is_file()

    assert str(exc_info.value) == f"[Errno 2] No such file or directory: '{file_path}'"


@pytest.mark.parametrize(
    "level",
    [
        CRITICAL,
        ERROR,
        WARNING,
        INFO,
        DEBUG,
    ],
)
def test_log_level_is_set_correctly(level: int, logger: Logger) -> None:
    """Test that the log level is set correctly."""

    log_path = Path(__file__).parent / f"{uuid4()}.log"

    f_handler = create_file_handler(log_path, level=level, create_directory=False)

    logger.addHandler(f_handler)
    with freeze_time(frozen_time := utcnow()):
        logger.log(level, "Test")

    assert log_path.is_file()
    assert f_handler.baseFilename == str(log_path)
    assert f_handler.level == level
    assert f_handler.mode == "a"

    assert log_path.read_text().strip() == "\t".join(
        [
            frozen_time.strftime("%Y-%m-%d %H:%M:%S%z"),
            f"test_log_level_is_set_correctly[{level}]",
            f"[{getLevelName(level)}]",
            "Test",
        ]
    )

    log_path.unlink()
