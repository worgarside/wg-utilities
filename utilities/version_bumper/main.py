from argparse import ArgumentParser
from enum import Enum
from os.path import abspath, sep
from re import match, compile
from subprocess import Popen, PIPE
from distutils.version import StrictVersion
from logging import getLogger, DEBUG

from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)

VERSION_REGEX = r"(\d+\.)?(\d+\.)?(\d+\.)?(\*|\d+)"
PATTERN = compile(r"""((?:[^\s"']|"[^"]*"|'[^']*')+)""")

SETUP_PY_PATH = sep.join(
    [
        x
        for x in abspath(__file__).split(sep)[
            0 : abspath(__file__).split(sep).index("wg-utilities") + 1
        ]
    ]
    + ["setup.py"]
)


class Bump(Enum):
    MAJOR = 0
    MINOR = 1
    PATCH = 2


def run_cmd(cmd, exit_on_error=True):
    LOGGER.debug("Running command `%s`", cmd)

    process = Popen(PATTERN.split(cmd)[1::2], stdout=PIPE, stderr=PIPE)

    output, error = process.communicate()

    if process.returncode != 0:
        LOGGER.error(error.decode("utf-8").strip())
        if exit_on_error:
            exit(process.returncode)

    return output.decode("utf-8").strip(), error.decode("utf-8").strip()


def get_latest_version():
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
        filter(lambda tag: match(VERSION_REGEX, tag), tags), key=StrictVersion
    )

    return releases[-1]


def new_version(latest_version):
    version_digits = latest_version.split(".")

    version_digits[Bump[args.bump].value] = str(
        int(version_digits[Bump[args.bump].value]) + 1
    )

    for digit in range(Bump[args.bump].value + 1, len(version_digits)):
        version_digits[digit] = "0"

    return ".".join(version_digits)


def create_release_branch(old, new):
    LOGGER.info(f"Bumping version from {old} to {new}")

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

    run_cmd("git add setup.py")
    run_cmd(f'git commit -m "VB {new}"')
    run_cmd(f'git tag -a {new} -m ""')
    run_cmd(f"git flow release finish -n {new}")
    run_cmd("git push --all")
    run_cmd("pipenv run clean")
    run_cmd("pipenv run build")
    run_cmd("pipenv run deploy")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--bump")
    args = parser.parse_args()

    try:
        args.bump = args.bump.upper()
        _ = Bump[args.bump]
    except AttributeError as exc:
        raise AttributeError("Argument 'bump' missing") from exc
    except KeyError as exc:
        raise KeyError(f"'{args.bump}' is not a valid bump type") from exc

    run_cmd("git push --tags")
    lv = get_latest_version()

    create_release_branch(lv, new_version(lv))
