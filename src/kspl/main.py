import sys
from argparse import ArgumentParser
from sys import argv

from py_app_dev.core.cmd_line import CommandLineHandlerBuilder
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger, setup_logger

from kspl import __version__
from kspl.edit import EditCommand
from kspl.generate import GenerateCommand
from kspl.gui import GuiCommand


def do_run() -> None:
    parser = ArgumentParser(prog="kspl", description="kconfig for SPL", exit_on_error=False)
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    builder = CommandLineHandlerBuilder(parser)
    builder.add_commands([GuiCommand(), GenerateCommand(), EditCommand()])
    handler = builder.create()
    handler.run(argv[1:])


def main() -> int:
    try:
        setup_logger()
        do_run()
    except UserNotificationException as e:
        logger.error(f"{e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
