"""Script for creating (and deploying) a new version of WGUtils"""

from argparse import ArgumentParser
from enum import Enum
from logging import DEBUG, getLogger
from os import chdir
from pathlib import Path
from re import match

from packaging.version import parse as parse_version

from wg_utilities.functions import run_cmd
from wg_utilities.functions.processes import LOGGER as CMD_LOGGER
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)
add_stream_handler(CMD_LOGGER)

VERSION_REGEX = r"(\d+\.)?(\d+\.)?(\d+\.)?(\*|\d+)"

PROJECT_ROOT = Path(__file__).parents[2]
SETUP_PY_PATH = PROJECT_ROOT / "setup.py"
WG_UTILS_PACKAGE_INIT_PATH = PROJECT_ROOT / "wg_utilities" / "__init__.py"

chdir(PROJECT_ROOT)


class Bump(Enum):
    """Enum for different version bump types"""

    MAJOR = 0
    MINOR = 1
    PATCH = 2


def get_latest_version() -> str:
    """Gets the latest release number (x.y.z) from GitHub

    Returns:
        str: the latest release number (x.y.z)
    """

    output, _ = run_cmd("git ls-remote --tags")

    tags = [
        line.split("\t")[1].replace("refs/tags/", "")
        for line in output.split("\n")
        if "refs/tags" in line and not line.endswith("^{}")
    ]

    releases = sorted(
        filter(lambda tag: match(VERSION_REGEX, tag), tags), key=parse_version
    )

    return releases[-1]


def get_new_version(bump_type: Bump, latest_version: str) -> str:
    """Builds a new version number

    Args:
        bump_type (Bump): the type of bump we're executing
        latest_version (str): the latest version, found from GitHub

    Returns:
        str: the new version number (x.y.z)
    """

    version_digits = latest_version.split(".")

    version_digits[bump_type.value] = str(int(version_digits[bump_type.value]) + 1)

    for digit in range(bump_type.value + 1, len(version_digits)):
        version_digits[digit] = "0"

    return ".".join(version_digits)


def create_release_branch(old: str, new: str) -> None:
    """Creates (and completes!) a release branch with the new release number

    Args:
        old (str): the old release number (x.y.z)
        new (str): the new release number (x.y.z)

    Raises:
        RuntimeError: if a RuntimeError is raised, and it's not because Git flow isn't
            installed *and* the user chooses not to install it
    """

    LOGGER.info("Bumping version from %s to %s", old, new)

    run_cmd("git push --all origin")
    try:
        run_cmd(f"git flow release start {new}")
    except RuntimeError as exc:
        if (
            "git: 'flow' is not a git command" in str(exc)
            and input("git-flow is not installed. Install and initialise? [y/N] ")
            == "y"
        ):
            run_cmd("brew install git-flow")
            run_cmd("git flow init")
            run_cmd(f"git flow release start {new}")
        else:
            raise

    update_setup_py_file(old, new)
    update_wg_utils_package_init_file(old, new)

    run_cmd(f"git add {SETUP_PY_PATH}")
    run_cmd(f"git add {WG_UTILS_PACKAGE_INIT_PATH}")
    run_cmd(f'git commit -m "VB {new}"')
    run_cmd(f"git push --set-upstream origin release/{new}")
    run_cmd(f'git tag -a {new} -m ""')
    run_cmd(f"git flow release finish -n {new}")
    run_cmd("git push --all")


def _update_file(
    *, file_path: Path, version_line_prefix: str, old: str, new: str
) -> None:
    """Updates the given file with the new version number

    Args:
        file_path (Path): the path to the file to update
        version_line_prefix (str): the prefix of the line containing the version number
        old (str): the old release number (x.y.z)
        new (str): the new release number (x.y.z)
    """
    with open(file_path, encoding="UTF-8") as f:
        file_content = f.readlines()

    version_line_num, version_line_content = [
        (index, line)
        for index, line in enumerate(file_content)
        if line.strip().lower().startswith(version_line_prefix)
    ][0]

    file_content[version_line_num] = version_line_content.replace(old, new)

    with open(file_path, "w", encoding="UTF-8") as f:
        f.writelines(file_content)


def update_setup_py_file(old: str, new: str) -> None:
    """Updates the `setup.py` file with the new version number

    Args:
        old (str): the old release number (x.y.z)
        new (str): the new release number (x.y.z)
    """
    _update_file(
        file_path=SETUP_PY_PATH,
        version_line_prefix="version=",
        old=old,
        new=new,
    )


def update_wg_utils_package_init_file(old: str, new: str) -> None:
    """Updates the `wg_utilities/__init__.py` file with the new version number

    Args:
        old (str): the old release number (x.y.z)
        new (str): the new release number (x.y.z)
    """
    _update_file(
        file_path=WG_UTILS_PACKAGE_INIT_PATH,
        version_line_prefix="__version__",
        old=old,
        new=new,
    )


def main() -> None:
    """Main function for this script"""
    parser = ArgumentParser()
    parser.add_argument("--bump")
    args = parser.parse_args()

    try:
        args.bump = args.bump.upper()
        bump_type = Bump[args.bump]
    except AttributeError as exc:
        raise AttributeError("Argument 'bump' missing") from exc
    except KeyError as exc:
        raise KeyError(f"'{args.bump}' is not a valid bump type") from exc

    run_cmd("git push --tags")
    latest_version = get_latest_version()

    create_release_branch(latest_version, get_new_version(bump_type, latest_version))

    run_cmd("rm -r build dist wg_utilities.egg-info", exit_on_error=False)
    run_cmd(f"python {SETUP_PY_PATH} sdist bdist_wheel")
    run_cmd("twine upload dist/*")
    run_cmd("rm -r build dist wg_utilities.egg-info", exit_on_error=False)


if __name__ == "__main__":
    main()
