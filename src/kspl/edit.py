from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mashumaro import DataClassDictMixin
from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.logging import logger, time_it

from .config_slurper import SPLKConfigData
from .kconfig import KConfig


@dataclass
class EditCommandConfig(DataClassDictMixin):
    project_dir: Path = field(
        default=Path(".").absolute(),
        metadata={"help": "Project root directory. Defaults to the current directory if not specified."},
    )
    kconfig_model_file: Optional[Path] = field(default=None, metadata={"help": "KConfig model file (KConfig)."})
    kconfig_config_file: Optional[Path] = field(default=None, metadata={"help": "KConfig user configuration file (config.txt)."})

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
        if cmd_config.kconfig_model_file is None:
            kconfig_data = SPLKConfigData(cmd_config.project_dir)
            variants = kconfig_data.get_variants()
            variant_names = [variant.name for variant in variants]
            selected_variant = self._select_variant(variant_names)
            if selected_variant is not None:
                variant_data = kconfig_data.find_variant_config(selected_variant)
                if variant_data is not None:
                    variant_data.config.menu_config()
                else:
                    self.logger.error(f"Variant {selected_variant} not found.")
        else:
            KConfig(cmd_config.kconfig_model_file, cmd_config.kconfig_config_file).menu_config()
        return 0

    def _select_variant(self, variant_names: list[str]) -> str | None:
        """Print the list of variants to choose from and let the user choose one."""
        selected_variant = None
        self.logger.info("Select a variant:")
        for index, variant_name in enumerate(variant_names):
            self.logger.info(f" [{index + 1}] {variant_name}")
        while True:
            try:
                selected_variant = variant_names[int(input(f"Select a variant (1-{len(variant_names)}): ")) - 1]
                break
            except (ValueError, IndexError):
                self.logger.error("Invalid input. Please try again or press CTRL+C to abort.")
            # In case of KeyboardInterrupt (CTRL+C) we want to abort
            except KeyboardInterrupt:
                self.logger.warning("Aborted by user.")
                break
        return selected_variant

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, EditCommandConfig)
