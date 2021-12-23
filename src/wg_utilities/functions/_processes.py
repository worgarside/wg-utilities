"""Functions for managing processes"""

from logging import getLogger, DEBUG
from re import compile as compile_regex
from subprocess import Popen, PIPE
from sys import exit as sys_exit

from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)

COMMAND_PATTERN = compile_regex(r"""((?:[^\s"']|"[^"]*"|'[^']*')+)""")


def run_cmd(cmd, exit_on_error=True):
    """Helper function for running commands on the command line

    Args:
        cmd (str): the command to run in the user's terminal
        exit_on_error (bool): flag for if the script should exit if the command errored

    Returns:
        str: the output of the command
        str: the error from the command, if it errored
    """

    LOGGER.debug("Running command `%s`", cmd)

    with Popen(COMMAND_PATTERN.split(cmd)[1::2], stdout=PIPE, stderr=PIPE) as process:
        output, error = process.communicate()

        if process.returncode != 0:
            LOGGER.error(error.decode("utf-8").strip())
            if exit_on_error:
                sys_exit(process.returncode)

    return output.decode("utf-8").strip(), error.decode("utf-8").strip()
