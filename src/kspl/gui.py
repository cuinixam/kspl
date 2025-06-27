import tkinter
from abc import abstractmethod
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from enum import auto
from pathlib import Path
from tkinter import font, simpledialog, ttk
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
        self.all_columns = [v.name for v in self.variants]
        self.visible_columns = list(self.all_columns)

        self.logger = logger.bind()
        self.edit_event_data: Optional[EditEventData] = None
        self.trigger_edit_event = self.event_manager.create_event_trigger(
            KSplEvents.EDIT
        )
        self.root = customtkinter.CTk()

        # Configure the main window
        self.root.title("K-SPL")
        self.root.geometry(f"{1080}x{580}")

        # Frame for controls
        control_frame = customtkinter.CTkFrame(self.root)
        control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        self.column_select_button = customtkinter.CTkButton(
            master=control_frame,
            text="Select variants",
            command=self.open_column_selection_dialog,
        )
        self.column_select_button.pack(side="left", padx=5)

        # ========================================================
        # create tabview and populate with frames
        tabview = customtkinter.CTkTabview(self.root)
        self.tree = self.create_tree_view(tabview.add("Configuration"))
        self.tree["columns"] = tuple(variant.name for variant in self.variants)
        self.tree["displaycolumns"] = self.visible_columns
        self.tree.heading("#0", text="Configuration")
        self.header_texts: Dict[str, str] = {}
        for variant in self.variants:
            self.tree.heading(variant.name, text=variant.name)
            self.header_texts[variant.name] = variant.name
        # Keep track of the mapping between the tree view items and the config elements
        self.tree_view_items_mapping = self.populate_tree_view()
        self.adjust_column_width()
        self.selected_column_id: Optional[str] = None
        self.tree.bind("<Button-1>", self.on_tree_click)
        # TODO: make the tree view editable
        # self.tree.bind("<Double-1>", self.double_click_handler)

        # ========================================================
        # put all together
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        tabview.grid(row=1, column=0, sticky="nsew")

    def mainloop(self) -> None:
        self.root.mainloop()

    def create_tree_view(self, frame: customtkinter.CTkFrame) -> ttk.Treeview:
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        columns = [var.name for var in self.variants]

        style = ttk.Style()
        # From: https://stackoverflow.com/a/56684731
        # This gives the selection a transparent look
        style.map(
            "mystyle.Treeview",
            background=[("selected", "#a6d5f7")],
            foreground=[("selected", "black")],
        )
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

        # Add a separator to the right of the heading
        MainView.vline_img = tkinter.PhotoImage(
            "vline", data="R0lGODlhAQABAIAAAAUEBAAAACwAAAAAAQABAAACAkQBADs="
        )
        style.element_create("vline", "image", "vline")
        style.layout(
            "mystyle.Treeview.Heading",
            [
                (
                    "mystyle.Treeview.heading.cell",
                    {
                        "sticky": "nswe",
                        "children": [
                            ("mystyle.Treeview.heading.text", {"sticky": "we"}),
                            ("vline", {"side": "right", "sticky": "ns"}),
                        ],
                    },
                )
            ],
        )

        # create a Treeview widget
        config_treeview = ttk.Treeview(
            frame,
            columns=columns,
            show="tree headings",
            style="mystyle.Treeview",
        )

        scrollbar_y = ttk.Scrollbar(frame, command=config_treeview.yview)
        scrollbar_x = ttk.Scrollbar(
            frame, command=config_treeview.xview, orient=tkinter.HORIZONTAL
        )
        config_treeview.config(
            xscrollcommand=scrollbar_x.set, yscrollcommand=scrollbar_y.set
        )
        scrollbar_y.pack(fill=tkinter.Y, side=tkinter.RIGHT)
        scrollbar_x.pack(fill=tkinter.X, side=tkinter.BOTTOM)
        config_treeview.pack(fill=tkinter.BOTH, expand=True)

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

    def adjust_column_width(self) -> None:
        """Adjust the column widths to fit the header text."""
        heading_font = font.Font(font=("Calibri", 14, "bold"))
        padding = 60
        for col in self.tree["columns"]:
            text = self.tree.heading(col, "text")
            width = heading_font.measure(text) + padding
            # Set the minimum width of the column to the width of the text.
            self.tree.column(col, minwidth=width, width=width, stretch=False)
        # First column (#0)
        text = self.tree.heading("#0", "text")
        width = heading_font.measure(text) + padding
        self.tree.column("#0", minwidth=width, width=width, stretch=False)

    def on_tree_click(self, event: tkinter.Event) -> None:
        """Handle click events on the treeview to highlight the column header."""
        column_id_str = self.tree.identify_column(event.x)
        if not column_id_str or column_id_str == "#0":
            # Click was on the tree part or outside columns, so reset if anything was selected
            if self.selected_column_id:
                original_text = self.header_texts.get(self.selected_column_id)
                if original_text:
                    self.tree.heading(self.selected_column_id, text=original_text)
                self.selected_column_id = None
            return

        col_idx = int(column_id_str.replace("#", "")) - 1
        if col_idx < 0:
            return
        column_name = self.tree["columns"][col_idx]

        if column_name == self.selected_column_id:
            return

        # Reset the previously selected column header
        if self.selected_column_id:
            original_text = self.header_texts.get(self.selected_column_id)
            if original_text:
                self.tree.heading(self.selected_column_id, text=original_text)

        # Highlight the new column header
        original_text = self.header_texts.get(column_name)
        if original_text:
            self.tree.heading(column_name, text=f"✅{original_text}")
        self.selected_column_id = column_name

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

    def update_visible_columns(self) -> None:
        """Update the visible columns based on the state of the checkboxes."""
        self.visible_columns = [
            col_name for col_name, var in self.column_vars.items() if var.get()
        ]
        self.tree["displaycolumns"] = self.visible_columns
        self.adjust_column_width()

    def open_column_selection_dialog(self) -> None:
        """Open a dialog to select which columns to display."""
        # Create a new top-level window
        dialog = customtkinter.CTkToplevel(self.root)
        dialog.title("Select variants")
        dialog.geometry("400x300")

        # Create a frame for the checkboxes
        checkbox_frame = customtkinter.CTkFrame(dialog)
        checkbox_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Create a variable for each column
        self.column_vars = {}
        for column_name in self.all_columns:
            # Set the initial value based on whether the column is currently visible
            is_visible = column_name in self.visible_columns
            var = tkinter.BooleanVar(value=is_visible)
            checkbox = customtkinter.CTkCheckBox(
                master=checkbox_frame,
                text=column_name,
                command=self.update_visible_columns,
                variable=var,
            )
            checkbox.pack(anchor="w", padx=5, pady=2)
            self.column_vars[column_name] = var

        # Add OK and Cancel buttons
        button_frame = customtkinter.CTkFrame(dialog)
        button_frame.pack(padx=10, pady=10)

        ok_button = customtkinter.CTkButton(
            master=button_frame,
            text="OK",
            command=dialog.destroy,
        )
        ok_button.pack(side="right", padx=5)

        cancel_button = customtkinter.CTkButton(
            master=button_frame,
            text="Cancel",
            command=dialog.destroy,
        )
        cancel_button.pack(side="right", padx=5)

        # Center the dialog on the screen
        dialog.update_idletasks()
        x = (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{self.root.winfo_x() + x}+{self.root.winfo_y() + y}")

        dialog.transient(self.root)  # Keep the dialog above the main window
        dialog.grab_set()  # Make the dialog modal


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
