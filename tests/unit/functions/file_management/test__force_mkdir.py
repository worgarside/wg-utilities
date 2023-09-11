"""Unit Tests for the `wg_utilities.functions.file_management.force_mkdir` function."""

from __future__ import annotations

from pathlib import Path
from shutil import rmtree

from wg_utilities.functions.file_management import force_mkdir


def test_directories_created_correctly() -> None:
    """Test that the directories are created correctly."""

    target_path = (remove_me := Path(__file__).parent / "one") / "two" / "three"

    assert not remove_me.exists()
    assert not target_path.exists()

    return_value = force_mkdir(target_path)

    assert return_value == target_path
    assert target_path.is_dir()

    rmtree(remove_me)

    assert not remove_me.exists()
    assert not target_path.exists()


def test_directories_created_correctly_with_path_is_file() -> None:
    """Test that the directories are created correctly."""

    target_path = (
        (remove_me := Path(__file__).parent / "one") / "two" / "three" / "four.txt"
    )

    assert not remove_me.exists()
    assert not target_path.exists()

    return_value = force_mkdir(target_path, path_is_file=True)

    assert return_value == target_path
    assert not target_path.exists()
    assert target_path.parent.is_dir()

    rmtree(remove_me)

    assert not remove_me.exists()
    assert not target_path.exists()
