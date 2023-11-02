from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mashumaro import DataClassDictMixin
from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.logging import logger, time_it

from kspl.kconfig import KConfig


@dataclass
class EditCommandConfig(DataClassDictMixin):
    kconfig_model_file: Path = field(metadata={"help": "KConfig model file (KConfig)."})
    kconfig_config_file: Optional[Path] = field(
        default=None, metadata={"help": "KConfig user configuration file (config.txt)."}
    )

    @classmethod
    def from_namespace(cls, namespace: Namespace) -> "EditCommandConfig":
        return cls.from_dict(vars(namespace))


class EditCommand(Command):
    def __init__(self) -> None:
        super().__init__("edit", "Edit KConfig configuration.")
        self.logger = logger.bind()

    @time_it("Build")
    def run(self, args: Namespace) -> int:
        self.logger.info(f"Running {self.name} with args {args}")
        cmd_config = EditCommandConfig.from_namespace(args)
        KConfig(
            cmd_config.kconfig_model_file, cmd_config.kconfig_config_file
        ).menu_config()
        return 0

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, EditCommandConfig)
