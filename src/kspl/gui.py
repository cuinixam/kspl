import tkinter
from abc import abstractmethod
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from enum import auto
from pathlib import Path
from tkinter import simpledialog, ttk
from typing import Any, Dict, List, Optional

import customtkinter
from mashumaro import DataClassDictMixin
from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.logging import logger, time_it
from py_app_dev.mvp.event_manager import EventID, EventManager
from py_app_dev.mvp.presenter import Presenter
from py_app_dev.mvp.view import View

from kspl.config_slurper import SPLKConfigData, VariantViewData
from kspl.kconfig import ConfigElementType, EditableConfigElement, TriState


class KSplEvents(EventID):
    EDIT = auto()


class CTkView(View):
    @abstractmethod
    def mainloop(self) -> None:
        pass


@dataclass
class EditEventData:
    variant: VariantViewData
    config_element_name: str
    new_value: Any


class MainView(CTkView):
    def __init__(
        self,
        event_manager: EventManager,
        elements: List[EditableConfigElement],
        variants: List[VariantViewData],
    ) -> None:
        self.event_manager = event_manager
        self.elements = elements
        self.elements_dict = {elem.name: elem for elem in elements}
        self.variants = variants

        self.logger = logger.bind()
        self.edit_event_data: Optional[EditEventData] = None
        self.trigger_edit_event = self.event_manager.create_event_trigger(
            KSplEvents.EDIT
        )
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
        # TODO: make the tree view editable
        # self.tree.bind("<Double-1>", self.double_click_handler)

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
            "mystyle.Treeview",
            highlightthickness=0,
            bd=0,
            font=("Calibri", 14),
            rowheight=30,
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
        self, element: EditableConfigElement
    ) -> List[int | str]:
        return (
            [
                self.prepare_value_to_be_displayed(
                    element.type, variant.config_dict.get(element.name, None)
                )
                for variant in self.variants
            ]
            if not element.is_menu
            else []
        )

    def prepare_value_to_be_displayed(
        self, element_type: ConfigElementType, value: Any
    ) -> str:
        """
        UNKNOWN  - N/A
        BOOL     - ✅ ⛔
        TRISTATE - str
        STRING   - str
        INT      - str
        HEX      - str
        MENU     - N/A
        """
        if value is None:
            return "N/A"
        elif element_type == ConfigElementType.BOOL:
            return "✅" if value == TriState.Y else "⛔"
        else:
            return str(value)

    def double_click_handler(self, event: tkinter.Event) -> None:  # type: ignore
        current_selection = self.tree.selection()
        if not current_selection:
            return

        selected_item = current_selection[0]
        selected_element_name = self.tree_view_items_mapping[selected_item]

        variant_idx_str = self.tree.identify_column(event.x)  # Get the clicked column
        variant_idx = (
            int(variant_idx_str.split("#")[-1]) - 1
        )  # Convert to 0-based index

        if variant_idx < 0 or variant_idx >= len(self.variants):
            return

        selected_variant = self.variants[variant_idx]
        selected_element = self.elements_dict[selected_element_name]
        selected_element_value = selected_variant.config_dict.get(selected_element_name)

        # TODO: Consider the actual configuration type (ConfigElementType)
        if not selected_element.is_menu:
            new_value: Any = None
            if selected_element.type == ConfigElementType.BOOL:
                # Toggle the boolean value
                new_value = (
                    TriState.N if selected_element_value == TriState.Y else TriState.Y
                )
            elif selected_element.type == ConfigElementType.INT:
                tmp_int_value = simpledialog.askinteger(
                    "Enter new value",
                    "Enter new value",
                    initialvalue=selected_element_value,
                )
                if tmp_int_value is not None:
                    new_value = tmp_int_value
            else:
                # Prompt the user to enter a new string value using messagebox
                tmp_str_value = simpledialog.askstring(
                    "Enter new value",
                    "Enter new value",
                    initialvalue=str(selected_element_value),
                )
                if tmp_str_value is not None:
                    new_value = tmp_str_value

            # Check if the value has changed
            if new_value:
                # Trigger the EDIT event
                self.create_edit_event_trigger(
                    selected_variant, selected_element_name, new_value
                )

    def create_edit_event_trigger(
        self, variant: VariantViewData, element_name: str, new_value: Any
    ) -> None:
        self.edit_event_data = EditEventData(variant, element_name, new_value)
        self.trigger_edit_event()

    def pop_edit_event_data(self) -> Optional[EditEventData]:
        result = self.edit_event_data
        self.edit_event_data = None
        return result


class KSPL(Presenter):
    def __init__(self, event_manager: EventManager, project_dir: Path) -> None:
        self.event_manager = event_manager
        self.event_manager.subscribe(KSplEvents.EDIT, self.edit)
        self.logger = logger.bind()
        self.kconfig_data = SPLKConfigData(project_dir)
        self.view = MainView(
            self.event_manager,
            self.kconfig_data.get_elements(),
            self.kconfig_data.get_variants(),
        )

    def edit(self) -> None:
        edit_event_data = self.view.pop_edit_event_data()
        if edit_event_data is None:
            self.logger.error("Edit event received but event data is missing!")
        else:
            self.logger.debug(
                "Edit event received: "
                f"'{edit_event_data.variant.name}:{edit_event_data.config_element_name} = {edit_event_data.new_value}'"
            )
            # Update the variant configuration data with the new value
            variant = self.kconfig_data.find_variant_config(
                edit_event_data.variant.name
            )
            if variant is None:
                raise ValueError(
                    f"Could not find variant '{edit_event_data.variant.name}'"
                )
            config_element = variant.find_element(edit_event_data.config_element_name)
            if config_element is None:
                raise ValueError(
                    f"Could not find config element '{edit_event_data.config_element_name}'"
                )
            config_element.value = edit_event_data.new_value

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
        super().__init__("view", "View all SPL KConfig configurations.")
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
