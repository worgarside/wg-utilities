"""Functions for managing processes"""

from logging import getLogger, DEBUG
from re import compile as compile_regex
from subprocess import Popen, PIPE

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

    Raises:
        RuntimeError: if the command has a non-zero exit code
    """

    LOGGER.debug("Running command `%s`", cmd)

    with Popen(COMMAND_PATTERN.split(cmd)[1::2], stdout=PIPE, stderr=PIPE) as process:
        output, error = process.communicate()

        error = error.decode("utf-8").strip()

        if process.returncode != 0:
            if exit_on_error:
                raise RuntimeError(error)

            LOGGER.error(error)

    return output.decode("utf-8").strip(), error
