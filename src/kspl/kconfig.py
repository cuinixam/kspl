import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

import kconfiglib
from guiconfig import menuconfig
from kconfiglib import MenuNode


class TriState(Enum):
    Y = auto()
    M = auto()
    N = auto()


class ConfigElementType(Enum):
    UNKNOWN = auto()
    BOOL = auto()
    TRISTATE = auto()
    STRING = auto()
    INT = auto()
    HEX = auto()
    MENU = auto()


@dataclass
class ConfigElement:
    type: ConfigElementType
    name: str
    value: Any

    @property
    def is_menu(self) -> bool:
        return self.type == ConfigElementType.MENU


@dataclass
class EditableConfigElement(ConfigElement):
    original_value: Any

    #: The level of the menu this element is in. 0 is the top level.
    level: int = 0
    #: Is determined when the value is calculated. This is a hidden function call due to property magic.
    write_to_conf: bool = True

    @property
    def id(self) -> str:
        return self.name

    @property
    def has_been_changed(self) -> bool:
        return self.original_value != self.value


@dataclass
class ConfigurationData:
    """
    Holds the variant configuration data which is relevant for the code generation.

    Requires no variable substitution (this should have been already done)
    """

    elements: list[ConfigElement]


@contextmanager
def working_directory(some_directory: Path) -> Generator[None, Any, None]:
    current_directory = Path().absolute()
    try:
        os.chdir(some_directory)
        yield
    finally:
        os.chdir(current_directory)


class KConfig:
    def __init__(
        self,
        k_config_model_file: Path,
        k_config_file: Optional[Path] = None,
        k_config_root_directory: Optional[Path] = None,
    ):
        """
        Parameters.

        - k_config_model_file: Feature model definition (KConfig format)
        - k_config_file: User feature selection configuration file
        - k_config_root_directory: all paths for the included configuration paths shall be relative to this folder
        """
        if not k_config_model_file.is_file():
            raise FileNotFoundError(f"File {k_config_model_file} does not exist.")
        self.k_config_root_directory = k_config_root_directory or k_config_model_file.parent
        with working_directory(self.k_config_root_directory):
            self.config = kconfiglib.Kconfig(k_config_model_file.absolute().as_posix())
        self.parsed_files: list[Path] = self._collect_parsed_files()
        self.k_config_file: Optional[Path] = k_config_file
        if self.k_config_file:
            if not self.k_config_file.is_file():
                raise FileNotFoundError(f"File {self.k_config_file} does not exist.")
            self.config.load_config(self.k_config_file, replace=False)
            self.parsed_files.append(self.k_config_file)
        self.elements = self._collect_elements()
        self._elements_dict = {element.id: element for element in self.elements}

    def get_parsed_files(self) -> list[Path]:
        return self.parsed_files

    def collect_config_data(self) -> ConfigurationData:
        """- creates the ConfigurationData from the KConfig configuration."""
        elements = self.elements
        elements_dict = {element.id: element for element in elements}

        # replace text in KConfig with referenced variables (string type only)
        # KConfig variables get replaced like: ${VARIABLE_NAME}, e.g. ${CONFIG_FOO}
        for element in elements:
            if element.type == ConfigElementType.STRING:
                element.value = re.sub(
                    r"\$\{([A-Za-z0-9_]+)\}",
                    lambda m: str(elements_dict[str(m.group(1))].value),
                    element.value,
                )
                element.value = re.sub(
                    r"\$\{ENV:([A-Za-z0-9_]+)\}",
                    lambda m: str(os.environ.get(str(m.group(1)), "")),
                    element.value,
                )

        return ConfigurationData([ConfigElement(elem.type, elem.name, elem.value) for elem in elements if elem.type != ConfigElementType.MENU])

    def menu_config(self) -> None:
        if self.k_config_file:
            # The environment variable KCONFIG_CONFIG is used by kconfiglib to determine
            # the configuration file to load.
            os.environ["KCONFIG_CONFIG"] = self.k_config_file.absolute().as_posix()
        menuconfig(self.config)

    def _collect_elements(self) -> list[EditableConfigElement]:
        elements: list[EditableConfigElement] = []

        def convert_to_element(node: MenuNode, level: int) -> EditableConfigElement | None:
            # TODO: Symbols like 'choice' and 'comment' shall be ignored.
            element = None
            sym = node.item
            if isinstance(sym, kconfiglib.Symbol):
                if sym.config_string:
                    val = sym.str_value
                    type = ConfigElementType.STRING
                    if sym.type in [kconfiglib.BOOL, kconfiglib.TRISTATE]:
                        val = getattr(TriState, str(val).upper())
                        type = ConfigElementType.BOOL if sym.type == kconfiglib.BOOL else ConfigElementType.TRISTATE
                    elif sym.type == kconfiglib.HEX:
                        val = int(str(val), 16)
                        type = ConfigElementType.HEX
                    elif sym.type == kconfiglib.INT:
                        val = int(val)
                        type = ConfigElementType.INT
                    element = EditableConfigElement(
                        type=type,
                        name=sym.name,
                        value=val,
                        original_value=val,
                        level=level,
                        write_to_conf=sym._write_to_conf,
                    )
            else:
                if isinstance(node, kconfiglib.MenuNode):
                    element = EditableConfigElement(
                        type=ConfigElementType.MENU,
                        name=node.prompt[0],
                        value=None,
                        original_value=None,
                        level=level,
                        write_to_conf=False,
                    )
            return element

        def _shown_full_nodes(node: MenuNode) -> list[MenuNode]:
            # Returns the list of menu nodes shown in 'menu' (a menu node for a menu)
            # for full-tree mode. A tricky detail is that invisible items need to be
            # shown if they have visible children.

            def rec(node: MenuNode) -> list[MenuNode]:
                res = []

                while node:
                    res.append(node)
                    if node.list and isinstance(node.item, kconfiglib.Symbol):
                        # Nodes from menu created from dependencies
                        res += rec(node.list)
                    node = node.next

                return res

            return rec(node.list)

        def create_elements_tree(node: MenuNode, collected_nodes: list[EditableConfigElement], level: int = 0) -> None:
            # Updates the tree starting from menu.list, in full-tree mode. To speed
            # things up, only open menus are updated. The menu-at-a-time logic here is
            # to deal with invisible items that can show up outside show-all mode (see
            # _shown_full_nodes()).

            for menu_node in _shown_full_nodes(node):
                element = convert_to_element(menu_node, level)
                if element:
                    collected_nodes.append(element)
                # _shown_full_nodes() includes nodes from menus rooted at symbols, so
                # we only need to check "real" menus/choices here
                if menu_node.list and not isinstance(menu_node.item, kconfiglib.Symbol):
                    create_elements_tree(menu_node, collected_nodes, level + 1)

        create_elements_tree(self.config.top_node, elements)
        return elements

    def find_element(self, name: str) -> EditableConfigElement | None:
        return self._elements_dict.get(name, None)

    def _collect_parsed_files(self) -> list[Path]:
        """Collects all parsed files from the KConfig instance and returns them as a list of absolute paths."""
        parsed_files: list[Path] = []
        for file in self.config.kconfig_filenames:
            file_path = Path(file)
            parsed_files.append(file_path if file_path.is_absolute() else self.k_config_root_directory / file_path)
        return parsed_files
