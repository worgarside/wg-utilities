"""Script for creating (and deploying) a new version of WGUtils"""

from argparse import ArgumentParser
from enum import Enum
from logging import DEBUG, getLogger
from os import chdir
from os.path import abspath, sep
from re import match

from packaging.version import parse as parse_version

from wg_utilities.functions import run_cmd
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)

VERSION_REGEX = r"(\d+\.)?(\d+\.)?(\d+\.)?(\*|\d+)"

PROJECT_ROOT = sep.join(
    abspath(__file__).split(sep)[
        0 : abspath(__file__).split(sep).index("wg-utilities") + 1
    ],
)

SETUP_PY_PATH = sep.join(
    [
        PROJECT_ROOT,
        "setup.py",
    ]
)

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
    """

    LOGGER.info("Bumping version from %s to %s", old, new)

    run_cmd("git push --all origin")
    run_cmd(f"git flow release start {new}")

    with open(SETUP_PY_PATH, encoding="UTF-8") as f:
        setup_file = f.readlines()

    version_line_num, version_line_content = [
        (index, line)
        for index, line in enumerate(setup_file)
        if line.strip().lower().startswith("version=")
    ][0]

    setup_file[version_line_num] = version_line_content.replace(old, new)

    with open(SETUP_PY_PATH, "w", encoding="UTF-8") as f:
        f.writelines(setup_file)

    run_cmd(f"git add {SETUP_PY_PATH}")
    run_cmd(f'git commit -m "VB {new}"')
    run_cmd(f"git push --set-upstream origin release/{new}")
    run_cmd(f'git tag -a {new} -m ""')
    run_cmd(f"git flow release finish -n {new}")
    run_cmd("git push --all")


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
