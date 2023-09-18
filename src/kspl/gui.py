import tkinter
from abc import abstractmethod
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from tkinter import simpledialog, ttk
from typing import Any, Dict, List

import customtkinter
from mashumaro import DataClassDictMixin
from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.logging import logger, time_it
from py_app_dev.mvp.event_manager import EventID, EventManager
from py_app_dev.mvp.presenter import Presenter
from py_app_dev.mvp.view import View

from kspl.kconfig import KConfig


class ConfigElementType(Enum):
    MENU = auto()
    CONFIG = auto()


@dataclass
class ConfigElementViewData:
    name: str
    level: int
    type: ConfigElementType


@dataclass
class VariantViewData:
    """A variant is a set of configuration values for a KConfig model."""

    name: str
    config_dict: Dict[str, int | str | bool]


class KSplEvents(EventID):
    EDIT = auto()


class CTkView(View):
    @abstractmethod
    def mainloop(self) -> None:
        pass


class MainView(CTkView):
    def __init__(
        self,
        event_manager: EventManager,
        elements: List[ConfigElementViewData],
        variants: List[VariantViewData],
    ) -> None:
        self.event_manager = event_manager
        self.elements = elements
        self.variants = variants
        self.root = customtkinter.CTk()

        # Configure the main window
        self.root.title("K-SPL")
        self.root.geometry(f"{1080}x{580}")

        # ========================================================
        # create tabview and populate with frames
        tabview = customtkinter.CTkTabview(self.root)
        self.tree = self.create_tree_view(tabview.add("Configuration"))
        self.tree["columns"] = tuple(variant.name for variant in self.variants)
        self.tree.heading("#0", text="Configuration")
        for variant in self.variants:
            self.tree.heading(variant.name, text=variant.name)
        # Keep track of the mapping between the tree view items and the config elements
        self.tree_view_items_mapping = self.populate_tree_view()
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.double_click_handler)

        # ========================================================
        # put all together
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        tabview.grid(row=0, column=0, sticky="nsew")

    def mainloop(self) -> None:
        self.root.mainloop()

    def create_tree_view(self, frame: customtkinter.CTkFrame) -> ttk.Treeview:
        frame.grid_rowconfigure(0, weight=10)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        columns = [var.name for var in self.variants]

        style = ttk.Style()
        style.configure(
            "mystyle.Treeview", highlightthickness=0, bd=0, font=("Calibri", 14)
        )  # Modify the font of the body
        style.configure(
            "mystyle.Treeview.Heading", font=("Calibri", 14, "bold")
        )  # Modify the font of the headings

        # create a Treeview widget
        config_treeview = ttk.Treeview(
            frame,
            columns=columns,
            show="tree headings",
            style="mystyle.Treeview",
        )
        config_treeview.grid(row=0, column=0, sticky="nsew")
        return config_treeview

    def populate_tree_view(self) -> Dict[str, str]:
        """
        Populates the tree view with the configuration elements.
        :return: a mapping between the tree view items and the configuration elements
        """
        stack = []  # To keep track of the parent items
        last_level = -1
        mapping: Dict[str, str] = {}

        for element in self.elements:
            values = self.collect_values_for_element(element)
            if element.level == 0:
                # Insert at the root level
                item_id = self.tree.insert("", "end", text=element.name, values=values)
                stack = [item_id]  # Reset the stack with the root item
            elif element.level > last_level:
                # Insert as a child of the last inserted item
                item_id = self.tree.insert(
                    stack[-1], "end", text=element.name, values=values
                )
                stack.append(item_id)
            elif element.level == last_level:
                # Insert at the same level as the last item
                item_id = self.tree.insert(
                    stack[-2], "end", text=element.name, values=values
                )
                stack[-1] = item_id  # Replace the top item in the stack
            else:
                # Go up in the hierarchy and insert at the appropriate level
                item_id = self.tree.insert(
                    stack[element.level - 1], "end", text=element.name, values=values
                )
                stack = stack[: element.level] + [item_id]

            last_level = element.level
            mapping[item_id] = element.name
        return mapping

    def collect_values_for_element(
        self, element: ConfigElementViewData
    ) -> List[int | str]:
        return (
            [
                self.prepare_value_to_be_displayed(
                    variant.config_dict.get(element.name, None)
                )
                for variant in self.variants
            ]
            if element.type == ConfigElementType.CONFIG
            else []
        )

    def prepare_value_to_be_displayed(self, value: Any) -> str:
        if value is None:
            return "N/A"
        elif isinstance(value, bool):
            return "✅" if value else "⛔"
        else:
            return str(value)

    def double_click_handler(self, event: tkinter.Event) -> None:  # type: ignore
        current_selection = self.tree.selection()
        if not current_selection:
            return

        selected_item = current_selection[0]
        elem_name = self.tree_view_items_mapping[selected_item]

        variant_idx_str = self.tree.identify_column(event.x)  # Get the clicked column
        variant_idx = (
            int(variant_idx_str.split("#")[-1]) - 1
        )  # Convert to 0-based index

        if variant_idx < 0 or variant_idx >= len(self.variants):
            return

        selected_variant = self.variants[variant_idx]
        selected_value = selected_variant.config_dict[elem_name]

        if selected_value is not None:
            new_value = selected_value
            if isinstance(selected_value, bool):
                # Toggle the boolean value
                new_value = not selected_value
            elif isinstance(selected_value, int):
                tmp_int_value = simpledialog.askinteger(
                    "Enter new value", "Enter new value", initialvalue=selected_value
                )
                if tmp_int_value is not None:
                    new_value = tmp_int_value
            elif isinstance(selected_value, str):
                # Prompt the user to enter a new string value using messagebox
                tmp_str_value = simpledialog.askstring(
                    "Enter new value", "Enter new value", initialvalue=selected_value
                )
                if tmp_str_value is not None:
                    new_value = tmp_str_value

            selected_variant.config_dict[elem_name] = new_value

            # Update the Treeview
            values = list(
                self.tree.item(selected_item, "values")
            )  # Get the current values of the selected item
            values[variant_idx] = self.prepare_value_to_be_displayed(new_value)
            self.tree.item(selected_item, values=values)


@dataclass
class VariantData:
    name: str
    config: KConfig


class SPLKConfigData:
    def __init__(self, project_root_dir: Path) -> None:
        self.project_root_dir = project_root_dir.absolute()
        variant_config_files = self._search_variant_config_file(self.project_root_dir)
        self.model = KConfig(self.kconfig_model_file)
        if variant_config_files:
            self.variant_configs: List[VariantData] = [
                VariantData(
                    self._get_variant_name(file), KConfig(self.kconfig_model_file, file)
                )
                for file in variant_config_files
            ]
        else:
            self.variant_configs = [VariantData("Default", self.model)]

    @property
    def kconfig_model_file(self) -> Path:
        return self.project_root_dir / "KConfig"

    def get_elements(self) -> List[ConfigElementViewData]:
        elements = []
        for elem in self.model.elements:
            elements.append(
                ConfigElementViewData(
                    elem.name,
                    elem.level,
                    ConfigElementType.MENU
                    if elem.is_menu
                    else ConfigElementType.CONFIG,
                )
            )
        return elements

    def get_variants(self) -> List[VariantViewData]:
        variants = []

        for variant in self.variant_configs:
            variants.append(
                VariantViewData(
                    variant.name,
                    {
                        config_elem.name: config_elem.raw_value
                        for config_elem in variant.config.elements
                        if not config_elem.is_menu
                    },
                )
            )
        return variants

    def _get_variant_name(self, file: Path) -> str:
        return file.relative_to(self.project_root_dir / "variants").parent.name

    def _search_variant_config_file(self, project_dir: Path) -> List[Path]:
        """
        Finds all files called 'config.txt' in the variants directory
        and returns a list with their paths.
        """
        return list((project_dir / "variants").glob("**/config.txt"))


class KSPL(Presenter):
    def __init__(self, event_manager: EventManager, project_dir: Path) -> None:
        self.event_manager = event_manager
        self.event_manager.subscribe(KSplEvents.EDIT, self.edit)
        self.counter = 0
        self.logger = logger.bind()
        self.kconfig_data = SPLKConfigData(project_dir)
        self.view = MainView(
            self.event_manager,
            self.kconfig_data.get_elements(),
            self.kconfig_data.get_variants(),
        )

    def edit(self) -> None:
        self.counter += 1
        self.logger.info(f"Counter: {self.counter}")

    def run(self) -> None:
        self.view.mainloop()


@dataclass
class GuiCommandConfig(DataClassDictMixin):
    project_dir: Path = field(
        default=Path(".").absolute(),
        metadata={
            "help": "Project root directory. "
            "Defaults to the current directory if not specified."
        },
    )

    @classmethod
    def from_namespace(cls, namespace: Namespace) -> "GuiCommandConfig":
        return cls.from_dict(vars(namespace))


class GuiCommand(Command):
    def __init__(self) -> None:
        super().__init__("gui", "Start the GUI for SPL configuration.")
        self.logger = logger.bind()

    @time_it("Build")
    def run(self, args: Namespace) -> int:
        self.logger.info(f"Running {self.name} with args {args}")
        config = GuiCommandConfig.from_namespace(args)
        event_manager = EventManager()
        KSPL(event_manager, config.project_dir.absolute()).run()
        return 0

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, GuiCommandConfig)