"""Functions for managing processes"""

from logging import DEBUG, getLogger
from re import compile as compile_regex
from subprocess import PIPE, Popen
from typing import Tuple

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)

COMMAND_PATTERN = compile_regex(r"""((?:[^\s"']|"[^"]*"|'[^']*')+)""")


def run_cmd(
    cmd: str, exit_on_error: bool = True, shell: bool = False
) -> Tuple[str, str]:
    """Helper function for running commands on the command line

    Args:
        cmd (str): the command to run in the user's terminal
        exit_on_error (bool): flag for if the script should exit if the command errored
        shell (bool): flag for running command in shell

    Returns:
        str: the output of the command
        str: the error from the command, if it errored

    Raises:
        RuntimeError: if the command has a non-zero exit code
    """

    LOGGER.debug("Running command `%s`", cmd)

    popen_input = cmd if shell else COMMAND_PATTERN.split(cmd)[1::2]

    with Popen(popen_input, stdout=PIPE, stderr=PIPE, shell=shell) as process:
        output, error = process.communicate()

        error_str = error.decode("utf-8").strip()

        if process.returncode != 0:
            if exit_on_error:
                raise RuntimeError(error_str)

            LOGGER.error(error_str)

    return output.decode("utf-8").strip(), error_str
