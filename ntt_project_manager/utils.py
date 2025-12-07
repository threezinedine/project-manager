import os
import subprocess
from .log import logger


def RunCommand(
    command: str,
    cwd: str | None = None,
) -> None:
    """
    Run a system command.
    Arguments
    ---------
    command : str
        The command to run.
    cwd : str | None
        The working directory to run the command in. If None, uses the current directory.
    """
    finalCWD = cwd if cwd is not None else os.getcwd()

    logger.debug(f'Run command: "{command}" at: "{finalCWD}"')

    finalCommand = command

    subprocess.run(
        finalCommand,
        cwd=finalCWD,
        shell=True,
        check=True,
    )


def ValidateCommandExist(
    command: str,
) -> None:
    """
    Used for checking the system health whereas a certain command exists or not.
    If the command does not exist, raise error
    """
    logger.debug(f"Checking command: {command}")

    try:
        if os.name == "nt":
            subprocess.run(
                ["where", command],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        else:
            subprocess.run(
                ["which", command],
                check=True,
                stdout=subprocess.DEVNULL,
            )
    except Exception as _:
        raise SystemError(f'The command "{command}" does not exist')
