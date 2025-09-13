import tkinter
from abc import abstractmethod
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from enum import auto
from pathlib import Path
from tkinter import font, simpledialog, ttk
from typing import Any, Callable, Optional

import customtkinter
from CTkToolTip import CTkToolTip
from mashumaro import DataClassDictMixin
from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.logging import logger, time_it
from py_app_dev.mvp.event_manager import EventID, EventManager
from py_app_dev.mvp.presenter import Presenter
from py_app_dev.mvp.view import View

from kspl.config_slurper import KConfigData, SPLKConfigData, VariantViewData
from kspl.kconfig import ConfigElementType, EditableConfigElement, TriState


@dataclass
class SegmentedButtonAction:
    """Dataclass for segmented button actions with optional tooltips."""

    label: str
    action: Callable[[], None]
    tooltip: Optional[str] = None


class KSplEvents(EventID):
    EDIT = auto()
    REFRESH = auto()


class CTkView(View):
    @abstractmethod
    def mainloop(self) -> None:
        pass


@dataclass
class EditEventData:
    variant: VariantViewData
    config_element_name: str
    new_value: Any


FONT_INCREASE_VALUE = 1
FONT_DECREASE_VALUE = -1


class MainView(CTkView):
    def __init__(
        self,
        event_manager: EventManager,
        elements: list[EditableConfigElement],
        variants: list[VariantViewData],
        icon_file: Optional[str] = None,
    ) -> None:
        self.event_manager = event_manager
        self.elements = elements
        self.elements_dict = {elem.name: elem for elem in elements}
        self.variants = variants

        self.logger = logger.bind()
        self.edit_event_data: EditEventData | None = None
        self.trigger_edit_event = self.event_manager.create_event_trigger(KSplEvents.EDIT)
        self.trigger_refresh_event = self.event_manager.create_event_trigger(KSplEvents.REFRESH)
        self.root = customtkinter.CTk()

        # Configure the main window
        self.root.title("K-SPL")
        self.root.geometry(f"{1080}x{580}")

        if icon_file:
            # update app icon
            self.root.iconbitmap(icon_file)

        # ----------------------------------------------------
        # Font / zoom management
        # ----------------------------------------------------
        self._font_family = "Calibri"
        self._base_font_size = 16
        self._font_size = self._base_font_size
        self._min_font_size = 8
        self._max_font_size = 40
        # Keep style reference so we can update dynamically
        self._style = ttk.Style()

        # Frame for controls
        control_frame = customtkinter.CTkFrame(self.root)
        control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # Define control actions using the new dataclass
        self.control_actions = [
            SegmentedButtonAction("🔽 Expand", self.expand_all_items),
            SegmentedButtonAction("🔼 Collapse", self.collapse_all_items),
            SegmentedButtonAction("🔍 Select", self.open_column_selection_dialog),
            SegmentedButtonAction("🔄 Refresh", self.trigger_refresh_event),
        ]

        # Define zoom actions using the new dataclass
        self.zoom_actions = [
            SegmentedButtonAction("🗚", lambda: self._change_font_size(FONT_INCREASE_VALUE), "Increase font size (Ctrl +)"),
            SegmentedButtonAction("⟳", self._reset_font_size, "Reset font size to default (Ctrl 0)"),
            SegmentedButtonAction("🗛", lambda: self._change_font_size(FONT_DECREASE_VALUE), "Decrease font size (Ctrl -)"),
        ]

        # Use grid in control_frame to keep zoom controls stable (no horizontal shift on font resize)
        control_frame.grid_columnconfigure(0, weight=0)  # actions
        control_frame.grid_columnconfigure(1, weight=1)  # elastic spacer
        control_frame.grid_columnconfigure(2, weight=0)  # zoom controls

        self.tree_control_segment = customtkinter.CTkSegmentedButton(
            master=control_frame,
            values=[action.label for action in self.control_actions],
            command=self.on_tree_control_segment_click,
            height=35,
            font=("Arial", 14),
        )
        self.tree_control_segment.grid(row=0, column=0, padx=(2, 6), pady=2, sticky="w")

        self.zoom_segment = customtkinter.CTkSegmentedButton(
            master=control_frame,
            values=[action.label for action in self.zoom_actions],
            command=self.on_zoom_segment_click,
            height=35,
            font=(self._font_family, self._font_size),
            corner_radius=6,
        )
        self.zoom_segment.grid(row=0, column=2, padx=(6, 2), pady=2, sticky="e")

        # Add tooltips for both control and zoom segments
        self._add_segmented_button_tooltips()

        # ========================================================
        # create main content frame
        main_frame = customtkinter.CTkFrame(self.root)
        self.tree = self.create_tree_view(main_frame)

        # Initialize column manager after tree is created
        self.column_manager = ColumnManager(self.tree)
        self.column_manager.update_columns(self.variants)

        # Keep track of the mapping between the tree view items and the config elements
        self.tree_view_items_mapping = self.populate_tree_view()
        self.adjust_column_width()
        self.tree.bind("<Button-1>", self.on_tree_click)
        # TODO: make the tree view editable
        # self.tree.bind("<Double-1>", self.double_click_handler)

        # ========================================================
        # put all together
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        # Register key bindings for zoom in/out like VS Code (Ctrl+ / Ctrl- / Ctrl0)
        self._register_zoom_key_bindings()

        # Initial font application (create_tree_view applied defaults already, but we want consistency)
        self._apply_font_update()

    def mainloop(self) -> None:
        self.root.mainloop()

    def create_tree_view(self, frame: customtkinter.CTkFrame) -> ttk.Treeview:
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        columns = [var.name for var in self.variants]
        style = self._style  # reuse stored style
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
            font=(self._font_family, self._font_size),
            rowheight=int(self._font_size * 2.1),
        )  # Body font & row height
        style.configure(
            "mystyle.Treeview.Heading",
            font=(self._font_family, self._font_size, "bold"),
        )  # Heading font

        # Add a separator to the right of the heading
        MainView.vline_img = tkinter.PhotoImage("vline", data="R0lGODlhAQABAIAAAAUEBAAAACwAAAAAAQABAAACAkQBADs=")
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
        scrollbar_x = ttk.Scrollbar(frame, command=config_treeview.xview, orient=tkinter.HORIZONTAL)
        config_treeview.config(xscrollcommand=scrollbar_x.set, yscrollcommand=scrollbar_y.set)
        scrollbar_y.pack(fill=tkinter.Y, side=tkinter.RIGHT)
        scrollbar_x.pack(fill=tkinter.X, side=tkinter.BOTTOM)
        config_treeview.pack(fill=tkinter.BOTH, expand=True)

        return config_treeview

    # ----------------------------------------------------
    # Font zoom helpers
    # ----------------------------------------------------
    def _register_zoom_key_bindings(self) -> None:
        # Windows / Linux typical bindings
        self.root.bind("<Control-plus>", lambda e: self._change_font_size(1))
        self.root.bind("<Control-equal>", lambda e: self._change_font_size(1))  # '=' without Shift
        self.root.bind("<Control-minus>", lambda e: self._change_font_size(-1))
        self.root.bind("<Control-underscore>", lambda e: self._change_font_size(-1))
        self.root.bind("<Control-0>", lambda e: self._reset_font_size())

    def _change_font_size(self, delta: int) -> None:
        new_size = max(self._min_font_size, min(self._max_font_size, self._font_size + delta))
        if new_size == self._font_size:
            return
        self._font_size = new_size
        self._apply_font_update()

    def _reset_font_size(self) -> None:
        if self._font_size == self._base_font_size:
            return
        self._font_size = self._base_font_size
        self._apply_font_update()

    def _apply_font_update(self) -> None:
        """Apply current font settings to style + key widgets."""
        try:
            self._style.configure(
                "mystyle.Treeview",
                font=(self._font_family, self._font_size),
                rowheight=int(self._font_size * 2.1),
            )
            self._style.configure(
                "mystyle.Treeview.Heading",
                font=(self._font_family, self._font_size, "bold"),
            )
            # Update segmented control font if it exists
            if hasattr(self, "tree_control_segment"):
                self.tree_control_segment.configure(font=(self._font_family, self._font_size))
            if hasattr(self, "zoom_segment"):
                self.zoom_segment.configure(font=(self._font_family, self._font_size))
            # Recalculate column widths (since text width changed)
            self.adjust_column_width()
        except tkinter.TclError:
            # Silently ignore if style not yet fully initialized
            pass

    def _add_segmented_button_tooltips(self) -> None:
        """Add tooltips to segmented button controls."""
        self._add_tooltips_to_segment(self.tree_control_segment, self.control_actions)
        self._add_tooltips_to_segment(self.zoom_segment, self.zoom_actions)

    def _add_tooltips_to_segment(self, segment: customtkinter.CTkSegmentedButton, actions: list[SegmentedButtonAction]) -> None:
        """Add tooltips to a specific segmented button."""
        if not hasattr(segment, "_buttons_dict"):
            return

        for action in actions:
            if action.tooltip and action.label in segment._buttons_dict:
                button = segment._buttons_dict[action.label]
                CTkToolTip(button, message=action.tooltip)

    def populate_tree_view(self) -> dict[str, str]:
        """
        Populates the tree view with the configuration elements.

        :return: a mapping between the tree view items and the configuration elements
        """
        stack = []  # To keep track of the parent items
        last_level = -1
        mapping: dict[str, str] = {}

        for element in self.elements:
            values = self.collect_values_for_element(element)
            if element.level == 0:
                # Insert at the root level
                item_id = self.tree.insert("", "end", text=element.name, values=values)
                stack = [item_id]  # Reset the stack with the root item
            elif element.level > last_level:
                # Insert as a child of the last inserted item
                item_id = self.tree.insert(stack[-1], "end", text=element.name, values=values)
                stack.append(item_id)
            elif element.level == last_level:
                # Insert at the same level as the last item
                item_id = self.tree.insert(stack[-2], "end", text=element.name, values=values)
                stack[-1] = item_id  # Replace the top item in the stack
            else:
                # Go up in the hierarchy and insert at the appropriate level
                item_id = self.tree.insert(stack[element.level - 1], "end", text=element.name, values=values)
                stack = [*stack[: element.level], item_id]

            last_level = element.level
            mapping[item_id] = element.name
        return mapping

    def collect_values_for_element(self, element: EditableConfigElement) -> list[int | str]:
        return [self.prepare_value_to_be_displayed(element.type, variant.config_dict.get(element.name, None)) for variant in self.variants] if not element.is_menu else []

    def prepare_value_to_be_displayed(self, element_type: ConfigElementType, value: Any) -> str:
        """
        Prepare the value to be displayed in the tree view based on the element type.

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
        """Adjust the column widths to fit the header text, preserving manual resizing."""
        heading_font = font.Font(font=(self._font_family, self._font_size, "bold"))
        padding = 60

        # Only adjust columns that actually exist in the current configuration
        current_columns = self.tree["columns"]
        for col in current_columns:
            try:
                text = self.tree.heading(col, "text")
                min_width = heading_font.measure(text) + padding
                # Get current width to preserve manual resizing
                current_width = self.tree.column(col, "width")
                # Use the larger of current width or minimum required width
                final_width = max(current_width, min_width)
                self.tree.column(col, minwidth=min_width, width=final_width, stretch=False)
            except tkinter.TclError:
                # Column might not exist anymore, skip it
                self.logger.warning(f"Skipping column '{col}' as it no longer exists")
                continue

        # First column (#0)
        try:
            text = self.tree.heading("#0", "text")
            min_width = heading_font.measure(text) + padding
            current_width = self.tree.column("#0", "width")
            final_width = max(current_width, min_width)
            self.tree.column("#0", minwidth=min_width, width=final_width, stretch=False)
        except tkinter.TclError:
            self.logger.warning("Skipping column '#0' as it no longer exists")

    def on_tree_click(self, event: Any) -> None:
        """Handle click events on the treeview to highlight the column header."""
        column_name = self.column_manager.get_column_from_click_position(event.x)

        if column_name is None:
            # Click was on the tree part or outside columns, clear selection
            self.column_manager.clear_selection()
            return

        if column_name == self.column_manager.selected_column_id:
            # Already selected, do nothing
            return

        # Set the new selected column
        self.column_manager.set_selected_column(column_name)

    def double_click_handler(self, event: Any) -> None:
        current_selection = self.tree.selection()
        if not current_selection:
            return

        selected_item = current_selection[0]
        selected_element_name = self.tree_view_items_mapping[selected_item]

        variant_idx_str = self.tree.identify_column(event.x)  # Get the clicked column
        variant_idx = int(variant_idx_str.split("#")[-1]) - 1  # Convert to 0-based index

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
                new_value = TriState.N if selected_element_value == TriState.Y else TriState.Y
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
                self.create_edit_event_trigger(selected_variant, selected_element_name, new_value)

    def create_edit_event_trigger(self, variant: VariantViewData, element_name: str, new_value: Any) -> None:
        self.edit_event_data = EditEventData(variant, element_name, new_value)
        self.trigger_edit_event()

    def pop_edit_event_data(self) -> EditEventData | None:
        result = self.edit_event_data
        self.edit_event_data = None
        return result

    def expand_all_items(self) -> None:
        """Expand all items in the tree view."""

        def expand_recursive(item: str) -> None:
            self.tree.item(item, open=True)
            children = self.tree.get_children(item)
            for child in children:
                expand_recursive(child)

        # Start with root items
        root_items = self.tree.get_children()
        for item in root_items:
            expand_recursive(item)

    def collapse_all_items(self) -> None:
        """Collapse all items in the tree view."""

        def collapse_recursive(item: str) -> None:
            children = self.tree.get_children(item)
            for child in children:
                collapse_recursive(child)
            self.tree.item(item, open=False)

        # Start with root items
        root_items = self.tree.get_children()
        for item in root_items:
            collapse_recursive(item)

    def on_tree_control_segment_click(self, value: str) -> None:
        """Handle clicks on the tree control segmented button."""
        self._dispatch_action(self.control_actions, value)
        # Reset selection to avoid button staying selected
        self.tree_control_segment.set("")

    def on_zoom_segment_click(self, value: str) -> None:
        """Handle clicks on zoom segmented control."""
        self._dispatch_action(self.zoom_actions, value)
        # Reset selection so it doesn't stay highlighted
        self.zoom_segment.set("")

    def _dispatch_action(self, actions: list[SegmentedButtonAction], value: str) -> None:
        """
        Generic helper to find and invoke an action by its label.

        Linear search is fine (tiny lists). Keeps API symmetrical for control and zoom
        segments without maintaining parallel dicts.
        """
        for action in actions:
            if action.label == value:
                action.action()
                return

    def open_column_selection_dialog(self) -> None:
        """Open a dialog to select which columns to display."""
        # Create a new top-level window
        dialog = customtkinter.CTkToplevel(self.root)
        dialog.title("Select variants")
        dialog.geometry("400x450")

        # Create a frame for select/deselect all buttons
        select_all_frame = customtkinter.CTkFrame(dialog)
        select_all_frame.pack(padx=10, pady=(10, 5), fill="x")

        def select_all_variants() -> None:
            """Select all variant checkboxes."""
            for var in self.column_manager.column_vars.values():
                var.set(True)
            self.update_visible_columns()

        def deselect_all_variants() -> None:
            """Deselect all variant checkboxes."""
            for var in self.column_manager.column_vars.values():
                var.set(False)
            self.update_visible_columns()

        select_all_button = customtkinter.CTkButton(
            master=select_all_frame,
            text="Select All",
            command=select_all_variants,
            width=100,
        )
        select_all_button.pack(side="left", padx=5)

        deselect_all_button = customtkinter.CTkButton(
            master=select_all_frame,
            text="Deselect All",
            command=deselect_all_variants,
            width=100,
        )
        deselect_all_button.pack(side="left", padx=5)

        # Create a scrollable frame for the checkboxes
        scrollable_frame = customtkinter.CTkScrollableFrame(dialog, height=250)
        scrollable_frame.pack(padx=10, pady=5, fill="both", expand=True)

        # Create a variable for each column using ColumnManager
        for column_name in self.column_manager.all_columns:
            # Set the initial value based on whether the column is currently visible
            is_visible = column_name in self.column_manager.visible_columns

            # Get or create variable
            if column_name not in self.column_manager.column_vars:
                self.column_manager.column_vars[column_name] = tkinter.BooleanVar(value=is_visible)
            else:
                self.column_manager.column_vars[column_name].set(is_visible)

            checkbox = customtkinter.CTkCheckBox(
                master=scrollable_frame,
                text=column_name,
                command=self.update_visible_columns,
                variable=self.column_manager.column_vars[column_name],
            )
            checkbox.pack(anchor="w", padx=5, pady=2)

        # Add OK and Cancel buttons in a fixed frame at the bottom
        button_frame = customtkinter.CTkFrame(dialog)
        button_frame.pack(padx=10, pady=10, fill="x")

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

    def update_visible_columns(self) -> None:
        """Wrapper method to update visible columns via ColumnManager."""
        self.column_manager.update_visible_columns()

    def update_data(self, elements: list[EditableConfigElement], variants: list[VariantViewData]) -> None:
        """Update the view with refreshed data."""
        self.elements = elements
        self.elements_dict = {elem.name: elem for elem in elements}
        self.variants = variants

        # Clear the tree first
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Use ColumnManager to handle all column-related updates
        self.column_manager.update_columns(variants)

        # Repopulate the tree view
        self.tree_view_items_mapping = self.populate_tree_view()
        self.adjust_column_width()

    # ...existing code...


class KSPL(Presenter):
    def __init__(self, event_manager: EventManager, kconfig_data: KConfigData, icon_file: Optional[str] = None) -> None:
        self.event_manager = event_manager
        self.event_manager.subscribe(KSplEvents.EDIT, self.edit)
        self.event_manager.subscribe(KSplEvents.REFRESH, self.refresh)
        self.logger = logger.bind()
        self.kconfig_data = kconfig_data
        self.view = MainView(
            self.event_manager,
            self.kconfig_data.get_elements(),
            self.kconfig_data.get_variants(),
            icon_file=icon_file,
        )

    def edit(self) -> None:
        edit_event_data = self.view.pop_edit_event_data()
        if edit_event_data is None:
            self.logger.error("Edit event received but event data is missing!")
        else:
            self.logger.debug(f"Edit event received: '{edit_event_data.variant.name}:{edit_event_data.config_element_name} = {edit_event_data.new_value}'")
            # Update the variant configuration data with the new value
            variant = self.kconfig_data.find_variant_config(edit_event_data.variant.name)
            if variant is None:
                raise ValueError(f"Could not find variant '{edit_event_data.variant.name}'")
            config_element = variant.find_element(edit_event_data.config_element_name)
            if config_element is None:
                raise ValueError(f"Could not find config element '{edit_event_data.config_element_name}'")
            config_element.value = edit_event_data.new_value

    def refresh(self) -> None:
        """Handle refresh event by reloading data and updating the view."""
        self.logger.info("Refreshing KConfig data...")
        try:
            # Store old state for debugging
            old_variants = [v.name for v in self.kconfig_data.get_variants()]
            self.logger.debug(f"Before refresh: {len(old_variants)} variants: {old_variants}")

            self.kconfig_data.refresh_data()

            # Log new state
            new_variants = [v.name for v in self.kconfig_data.get_variants()]
            self.logger.debug(f"After refresh: {len(new_variants)} variants: {new_variants}")

            # Update the view with new data
            self.view.update_data(
                self.kconfig_data.get_elements(),
                self.kconfig_data.get_variants(),
            )
            self.logger.info("Data refreshed successfully")
        except Exception as e:
            self.logger.error(f"Failed to refresh data: {e}")
            # Don't re-raise the exception to prevent the GUI from crashing
            # Instead, keep the current data state

    def run(self) -> None:
        self.view.mainloop()


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
        KSPL(event_manager, kconfig_data).run()
        return 0

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, GuiCommandConfig)


class ColumnManager:
    """Manages column state, visibility, selection, and headings for the treeview."""

    def __init__(self, tree: ttk.Treeview) -> None:
        self.tree = tree
        self.all_columns: list[str] = []
        self.visible_columns: list[str] = []
        self.header_texts: dict[str, str] = {}
        self.selected_column_id: str | None = None
        self.column_vars: dict[str, tkinter.BooleanVar] = {}

    def update_columns(self, variants: list[VariantViewData]) -> None:
        """Update column configuration with new variants."""
        # Clear any existing selection FIRST, before any tree operations
        self.selected_column_id = None

        # Update column lists
        new_all_columns = [v.name for v in variants]

        # Preserve visible columns that still exist, add new ones
        if self.visible_columns:
            existing_visible = [col for col in self.visible_columns if col in new_all_columns]
            new_columns = [col for col in new_all_columns if col not in existing_visible]
            self.visible_columns = existing_visible + new_columns
        else:
            self.visible_columns = list(new_all_columns)

        # Update all_columns after determining visible columns
        self.all_columns = new_all_columns

        # Update tree configuration with error handling
        try:
            # First completely clear the tree configuration
            self.tree.configure(columns=(), displaycolumns=())
            # Then set new configuration
            self.tree["columns"] = tuple(self.all_columns)
            self.tree["displaycolumns"] = self.visible_columns
        except tkinter.TclError:
            # If there's still an error, log it but continue
            pass

        # Update header texts and tree headings
        self.header_texts = {}
        for variant in variants:
            self.header_texts[variant.name] = variant.name
            try:
                self.tree.heading(variant.name, text=variant.name)
            except tkinter.TclError:
                # Column might not exist yet, will be handled in next update
                pass

        # Clean up column variables for dialog
        self.column_vars = {k: v for k, v in self.column_vars.items() if k in self.all_columns}

    def set_selected_column(self, column_name: str) -> bool:
        """Set the selected column and update its visual state. Returns True if successful."""
        if column_name not in self.all_columns:
            return False

        # Clear previous selection
        self._clear_selection()

        # Set new selection
        self.selected_column_id = column_name
        original_text = self.header_texts.get(column_name)
        if original_text:
            try:
                self.tree.heading(column_name, text=f"✅{original_text}")
                return True
            except tkinter.TclError:
                self.selected_column_id = None
                return False
        return False

    def clear_selection(self) -> None:
        """Clear the column selection."""
        self._clear_selection()

    def _clear_selection(self) -> None:
        """Internal method to clear selection without public access."""
        if self.selected_column_id and self.selected_column_id in self.header_texts:
            # Only try to clear if the column still exists in the tree
            if self.selected_column_id in self.all_columns:
                original_text = self.header_texts[self.selected_column_id]
                try:
                    self.tree.heading(self.selected_column_id, text=original_text)
                except tkinter.TclError:
                    # Column no longer exists in tree, that's fine
                    pass
        self.selected_column_id = None

    def get_column_from_click_position(self, x: int) -> str | None:
        """Get column name from click position, returns None if invalid."""
        column_id_str = self.tree.identify_column(x)
        if not column_id_str or column_id_str == "#0":
            return None

        col_idx = int(column_id_str.replace("#", "")) - 1
        if col_idx < 0 or col_idx >= len(self.visible_columns):
            return None

        return self.visible_columns[col_idx]

    def update_visible_columns(self) -> None:
        """Update visible columns based on column_vars state."""
        self.visible_columns = [col_name for col_name, var in self.column_vars.items() if var.get()]
        self.tree["displaycolumns"] = self.visible_columns
