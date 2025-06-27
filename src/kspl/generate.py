import json
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import kconfiglib
from mashumaro import DataClassDictMixin
from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.logging import logger, time_it

from kspl.kconfig import ConfigElementType, ConfigurationData, KConfig, TriState


class GeneratedFile:
    def __init__(self, path: Path, content: str = "", skip_writing_if_unchanged: bool = False) -> None:
        self.path = path

        self.content = content

        self.skip_writing_if_unchanged = skip_writing_if_unchanged

    def to_string(self) -> str:
        return self.content

    def to_file(self) -> None:
        """Only write to file if the content has changed. The directory of the file is created if it does not exist."""
        content = self.to_string()

        if not self.path.exists() or not self.skip_writing_if_unchanged or self.path.read_text() != content:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(content)


class FileWriter(ABC):
    """Writes the ConfigurationData to a file."""

    def __init__(self, output_file: Path):
        self.output_file = output_file

    def write(self, configuration_data: ConfigurationData) -> None:
        """Writes the ConfigurationData to a file. The file shall not be modified if the content is the same as the existing one."""
        content = self.generate_content(configuration_data)
        GeneratedFile(self.output_file, content, skip_writing_if_unchanged=True).to_file()

    @abstractmethod
    def generate_content(self, configuration_data: ConfigurationData) -> str:
        """- generates the content of the file from the ConfigurationData."""


class HeaderWriter(FileWriter):
    """Writes the ConfigurationData as pre-processor defines in a C Header file."""

    config_prefix = "CONFIG_"  # Prefix for all configuration defines

    def generate_content(self, configuration_data: ConfigurationData) -> str:
        """
        Does exactly what the kconfiglib.write_autoconf() method does.

        We had to implemented here because we refactor the file writers to use the ConfigurationData
        instead of the KConfig configuration. ConfigurationData has variable substitution already done.
        """
        result: list[str] = [
            "/** @file */",
            "#ifndef __autoconf_h__",
            "#define __autoconf_h__",
            "",
        ]

        def add_define(define_decl: str, description: str) -> None:
            result.append(f"/** {description} */")
            result.append(define_decl)

        for element in configuration_data.elements:
            val = element.value
            if element.type in [ConfigElementType.BOOL, ConfigElementType.TRISTATE]:
                if val == TriState.Y:
                    add_define(
                        f"#define {self.config_prefix}{element.name} 1",
                        element.name,
                    )
                elif val == TriState.M:
                    add_define(
                        f"#define {self.config_prefix}{element.name}_MODULE 1",
                        element.name,
                    )

            elif element.type is ConfigElementType.STRING:
                add_define(
                    f'#define {self.config_prefix}{element.name} "{kconfiglib.escape(val)}"',
                    element.name,
                )

            else:  # element.type in [INT, HEX]:
                if element.type is ConfigElementType.HEX:
                    val = hex(val)
                add_define(
                    f"#define {self.config_prefix}{element.name} {val}",
                    element.name,
                )
        result.extend(["", "#endif /* __autoconf_h__ */", ""])
        return "\n".join(result)


class JsonWriter(FileWriter):
    """Writes the ConfigurationData in json format."""

    def generate_content(self, configuration_data: ConfigurationData) -> str:
        result = {}
        for element in configuration_data.elements:
            if element.type is ConfigElementType.BOOL:
                result[element.name] = True if element.value == TriState.Y else False
            else:
                result[element.name] = element.value
        return json.dumps({"features": result}, indent=4)


class CMakeWriter(FileWriter):
    """Writes the ConfigurationData as CMake variables."""

    def generate_content(self, configuration_data: ConfigurationData) -> str:
        result: list[str] = []
        add = result.append
        for element in configuration_data.elements:
            val = element.value
            if element.type is ConfigElementType.BOOL:
                val = True if element.value == TriState.Y else False
            add(f'set({element.name} "{val}")')

        return "\n".join(result)


@dataclass
class GenerateCommandConfig(DataClassDictMixin):
    kconfig_model_file: Path = field(metadata={"help": "KConfig model file (KConfig)."})
    kconfig_config_file: Optional[Path] = field(default=None, metadata={"help": "KConfig user configuration file (config.txt)."})
    out_header_file: Optional[Path] = field(default=None, metadata={"help": "File to write the configuration as C header."})
    out_json_file: Optional[Path] = field(
        default=None,
        metadata={"help": "File to write the configuration in JSON format."},
    )
    out_cmake_file: Optional[Path] = field(
        default=None,
        metadata={"help": "File to write the configuration in CMake format."},
    )

    @classmethod
    def from_namespace(cls, namespace: Namespace) -> "GenerateCommandConfig":
        return cls.from_dict(vars(namespace))


class GenerateCommand(Command):
    def __init__(self) -> None:
        super().__init__("generate", "Generate the KConfig configuration in the specified formats.")
        self.logger = logger.bind()

    @time_it("Build")
    def run(self, args: Namespace) -> int:
        self.logger.info(f"Running {self.name} with args {args}")
        cmd_config = GenerateCommandConfig.from_namespace(args)
        config = KConfig(cmd_config.kconfig_model_file, cmd_config.kconfig_config_file).collect_config_data()

        if cmd_config.out_header_file:
            HeaderWriter(cmd_config.out_header_file).write(config)
        if cmd_config.out_json_file:
            JsonWriter(cmd_config.out_json_file).write(config)
        if cmd_config.out_cmake_file:
            CMakeWriter(cmd_config.out_cmake_file).write(config)
        return 0

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, GenerateCommandConfig)
