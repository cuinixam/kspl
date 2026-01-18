from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path

from mashumaro import DataClassDictMixin
from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger, time_it
from py_app_dev.mvp.event_manager import EventManager

from kspl.config_slurper import KConfigData, SPLKConfigData


@dataclass
class GuiCommandConfig(DataClassDictMixin):
    project_dir: Path = field(
        default=Path(".").absolute(),
        metadata={"help": "Project root directory. Defaults to the current directory if not specified."},
    )

    @classmethod
    def from_namespace(cls, namespace: Namespace) -> "GuiCommandConfig":
        return cls.from_dict(vars(namespace))


class GuiCommand(Command):
    def __init__(self) -> None:
        super().__init__("view", "View all SPL KConfig configurations.")
        self.logger = logger.bind()

    @time_it("Build")
    def run(self, args: Namespace) -> int:
        self.logger.info(f"Running {self.name} with args {args}")
        config = GuiCommandConfig.from_namespace(args)
        event_manager = EventManager()
        kconfig_data: KConfigData = SPLKConfigData(config.project_dir.absolute())
        try:
            from kspl.gui import KSPL

            KSPL(event_manager, kconfig_data).run()
        except ImportError as e:
            raise UserNotificationException("GUI functionality not available. Please ensure that your environment supports GUI operations.") from e
        return 0

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, GuiCommandConfig)
