"""Unit Tests for the `create_file_handler` function."""
from __future__ import annotations

from logging import CRITICAL, DEBUG, ERROR, FATAL, INFO, NOTSET, WARN, WARNING
from os.path import isdir, isfile
from pathlib import Path
from tempfile import TemporaryDirectory

from pytest import mark, raises

from wg_utilities.loggers import create_file_handler


def test_target_directory_is_created() -> None:
    """Test that the target directory is created when requested."""

    with TemporaryDirectory() as tmp_dir:
        assert not isdir(dir_path := f"{tmp_dir}/foo/bar")
        assert not isfile(file_path := Path(f"{dir_path}/baz.log"))

        f_handler = create_file_handler(file_path, create_directory=True)

        assert isdir(dir_path)
        assert isfile(file_path)

    assert f_handler.baseFilename == str(file_path)
    assert f_handler.level == DEBUG
    assert f_handler.mode == "a"


def test_target_directory_is_not_created() -> None:
    """Test that the target directory is not created when not requested."""
    dir_path = "/foo/bar"
    file_path = Path(f"{dir_path}/baz.log")

    assert not isdir(dir_path)
    assert not isfile(file_path)

    # The FileHandler instantiation will fail as the directory doesn't exist
    with raises(FileNotFoundError) as exc_info:
        create_file_handler(file_path, create_directory=False)

    assert not isdir(dir_path)
    assert not isfile(file_path)

    assert str(exc_info.value) == f"[Errno 2] No such file or directory: '{file_path}'"


@mark.parametrize(  # type: ignore[misc]
    "level",
    [
        CRITICAL,
        FATAL,
        ERROR,
        WARNING,
        WARN,
        INFO,
        DEBUG,
        NOTSET,
    ],
)
def test_log_level_is_set_correctly(level: int) -> None:
    """Test that the log level is set correctly."""

    log_path = Path(__file__).parent / "foo.log"

    f_handler = create_file_handler(log_path, level=level, create_directory=False)

    assert isfile(log_path)
    assert f_handler.baseFilename == str(log_path)
    assert f_handler.level == level
    assert f_handler.mode == "a"

    log_path.unlink()
