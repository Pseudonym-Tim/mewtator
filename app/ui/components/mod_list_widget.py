import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageTk

from app.ui.components.wide_scrollbar import WideScrollbar
from app.ui.components.rounded_button import RoundedButton


class ModListWidget(ttk.Frame):
    """Unified mod table list with checkbox-style enable/disable toggles..."""

    TREE_ROW_HEIGHT = 32

    def __init__(self, parent, title: str):
        super().__init__(parent, padding=(16, 14))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._toggle_command: Optional[Callable[[str], None]] = None
        self._name_by_iid: Dict[str, str] = {}
        self._iid_by_name: Dict[str, str] = {}
        self._enabled_by_name: Dict[str, bool] = {}
        self._current_colors: Dict[str, str] = {}
        self._checkbox_images: Dict[bool, tk.PhotoImage] = {}
        self._row_fit_job = None
        self._horizontal_scroll_required = False

        self._order_icons = {
            "up_enabled": None,
            "up_disabled": None,
            "down_enabled": None,
            "down_disabled": None,
        }

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)

        self.title_label = ttk.Label(
            header,
            text=title,
            font="MewtatorHeadingUnderline",
        )

        self.title_label.grid(row=0, column=0, sticky="w")

        self.actions = ttk.Frame(self)
        self.actions.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.actions.columnconfigure(5, weight=1)

        self.enable_all_button = ttk.Button(
            self.actions,
            text="",
            style="ModAction.TButton",
            cursor="hand2",
        )

        self.enable_all_button.grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.disable_all_button = ttk.Button(
            self.actions,
            text="",
            style="ModAction.TButton",
            cursor="hand2",
        )

        self.disable_all_button.grid(row=0, column=1, sticky="w", padx=(0, 6))

        self.auto_sort_button = ttk.Button(
            self.actions,
            text="",
            style="ModAction.TButton",
            cursor="hand2",
        )

        self.auto_sort_button.grid(row=0, column=2, sticky="w", padx=(0, 6))

        self.import_mod_button = ttk.Button(
            self.actions,
            text="",
            style="ModAction.TButton",
            cursor="hand2",
        )

        self.import_mod_button.grid(row=0, column=3, sticky="w", padx=(0, 6))

        self.refresh_button = ttk.Button(
            self.actions,
            text="",
            style="ModAction.TButton",
            cursor="hand2",
            width=3,
        )
        
        self.refresh_button.grid(row=0, column=4, sticky="w")

        table_area = ttk.Frame(self)
        table_area.grid(row=2, column=0, sticky="nsew")
        table_area.rowconfigure(0, weight=1)
        table_area.columnconfigure(0, weight=1)

        tree_frame = ttk.Frame(table_area)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=0)
        tree_frame.rowconfigure(2, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self._tree_frame = tree_frame

        columns = ("author", "version")

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="tree headings",
            selectmode="browse",
            style="ModList.Treeview",
        )

        self.tree.grid(row=0, column=0, sticky="ew")

        self.v_scrollbar = WideScrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,
        )

        self.v_scrollbar.grid(row=0, column=1, sticky="ns")

        self.h_scrollbar = WideScrollbar(
            tree_frame,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.h_scrollbar.grid(row=1, column=0, sticky="ew")

        self.tree.configure(
            yscrollcommand=self.v_scrollbar.set,
            xscrollcommand=self._set_horizontal_scroll,
        )

        tree_frame.bind("<Configure>", self._schedule_tree_row_fit, add="+")

        self.tree.heading("#0", text="", anchor="center")
        self.tree.column("#0", width=320, minwidth=220, stretch=True, anchor="w")
        self.tree.heading("author", text="", anchor="center")
        self.tree.column("author", width=165, minwidth=120, stretch=False, anchor="w")
        self.tree.heading("version", text="", anchor="center")
        self.tree.column("version", width=110, minwidth=90, stretch=False, anchor="center")

        self.order_frame = ttk.Frame(table_area, padding=(8, 0, 0, 0))
        self.order_frame.grid(row=0, column=1, sticky="ns")
        self.order_frame.rowconfigure(0, weight=1)
        self.order_frame.rowconfigure(3, weight=1)

        self.move_up_button = RoundedButton(
            self.order_frame,
            text="",
            font="MewtatorBody",
            width=38,
            height=36,
            radius=7,
        )

        self.move_up_button.grid(row=1, column=0, pady=(0, 5))

        self.move_down_button = RoundedButton(
            self.order_frame,
            text="",
            font="MewtatorBody",
            width=38,
            height=36,
            radius=7,
        )

        self.move_down_button.grid(row=2, column=0)

        self.tree.bind("<Button-1>", self._on_left_click, add="+")
        self.tree.bind("<Motion>", self._on_pointer_motion, add="+")
        self.tree.bind("<Leave>", lambda _event: self.tree.configure(cursor=""), add="+")
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._update_order_button_state(), add="+")
        self._update_order_button_state()

    def set_headings(self, name: str, author: str, version: str):
        self.tree.heading("#0", text=name)
        self.tree.heading("author", text=author)
        self.tree.heading("version", text=version)
        self._fit_header_widths(name, author, version)

    def _fit_header_widths(self, name: str, author: str, version: str):
        """Keep translated headings comfortably inside column cells..."""
        try:
            from tkinter import font as tkfont

            heading_font = tkfont.nametofont("MewtatorBodyBold")
            measure = heading_font.measure
        except (tk.TclError, RuntimeError):
            measure = lambda text: len(text) * 8

        self.tree.column("#0", minwidth=max(220, measure(name) + 56))
        self.tree.column("author", width=max(165, measure(author) + 44), minwidth=max(120, measure(author) + 36))
        self.tree.column("version", width=max(110, measure(version) + 44), minwidth=max(90, measure(version) + 36))

    def set_action_labels(
        self,
        enable_all: str,
        disable_all: str,
        auto_sort: str,
        import_mod: str,
        refresh_mods: str,
    ):
        self.enable_all_button.config(text=enable_all)
        self.disable_all_button.config(text=disable_all)
        self.auto_sort_button.config(text=auto_sort)
        self.import_mod_button.config(text=import_mod)
        self.refresh_button.config(text=refresh_mods)

    def set_toggle_action(self, command: Callable[[str], None]):
        self._toggle_command = command

    def set_enable_all_action(self, command: Callable):
        self.enable_all_button.config(command=command)

    def set_disable_all_action(self, command: Callable):
        self.disable_all_button.config(command=command)

    def set_auto_sort_action(self, command: Callable):
        self.auto_sort_button.config(command=command)

    def set_import_mod_action(self, command: Callable):
        self.import_mod_button.config(command=command)

    def set_refresh_action(self, command: Callable):
        self.refresh_button.config(command=command)

    def set_order_actions(
        self,
        move_up: Callable,
        move_down: Callable,
    ):
        self.move_up_button.config(command=move_up)
        self.move_down_button.config(command=move_down)
        self._update_order_button_state()

    def set_order_icons(
        self,
        up_enabled,
        up_disabled,
        down_enabled,
        down_disabled,
    ):
        """Set normal/disabled arrow art and refresh the current button state..."""

        self._order_icons.update(
            {
                "up_enabled": up_enabled,
                "up_disabled": up_disabled,
                "down_enabled": down_enabled,
                "down_disabled": down_disabled,
            }
        )
        self._update_order_button_state()

    def _update_order_button_state(self):
        """Only enabled mods can use the load-order swap controls..."""

        selection = self.get_selection()
        can_reorder = bool(
            selection and self._enabled_by_name.get(selection[1], False)
        )

        if can_reorder:
            self.move_up_button.configure(state="normal")
            self.move_down_button.configure(state="normal")
            up_image = self._order_icons.get("up_enabled")
            down_image = self._order_icons.get("down_enabled")
        else:
            self.move_up_button.configure(state="disabled")
            self.move_down_button.configure(state="disabled")
            up_image = self._order_icons.get("up_disabled")
            down_image = self._order_icons.get("down_disabled")

        if up_image is not None:
            self.move_up_button.configure(image=up_image, compound="center")
        if down_image is not None:
            self.move_down_button.configure(image=down_image, compound="center")

    def _on_left_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        if self.is_checkbox_at(event.x, event.y):
            self.tree.selection_set(row_id)
            self.tree.focus(row_id)
            name = self._name_by_iid.get(row_id)
            if name and self._toggle_command:
                self._toggle_command(name)
            return "break"

    def _on_pointer_motion(self, event):
        desired = "hand2" if self.is_checkbox_at(event.x, event.y) else ""
        if self.tree.cget("cursor") != desired:
            self.tree.configure(cursor=desired)

    def is_checkbox_at(self, x: int, y: int) -> bool:
        """Return true only over the visible checkbox, not its text gap..."""

        row_id = self.tree.identify_row(y)

        if self.tree.identify_column(x) != "#0" or not row_id:
            return False
        try:
            cell_x, _cell_y, _cell_width, _cell_height = self.tree.bbox(row_id, "#0")
        except (tk.TclError, ValueError):
            return False
        
        # Magical! - Tim
        return cell_x + 4 <= x < cell_x + 28

    def _set_horizontal_scroll(self, first, last):
        """Forward xview updates and refit the vertical viewport if needed..."""

        first_value = float(first)
        last_value = float(last)
        self._horizontal_scroll_required = (
            first_value > 0.000001 or last_value < 0.999999
        )
        self.h_scrollbar.set(first, last)
        self._schedule_tree_row_fit()

    def _schedule_tree_row_fit(self, _event=None):
        if self._row_fit_job is None:
            self._row_fit_job = self.after_idle(self._fit_tree_height_to_rows)

    def _fit_tree_height_to_rows(self):
        """Size the viewport to whole rows so scrolling ends on the last mod..."""

        self._row_fit_job = None
        frame_height = self._tree_frame.winfo_height()

        if frame_height <= 1:
            return

        try:
            requested_rows = max(1, int(self.tree.cget("height")))
            requested_height = max(1, self.tree.winfo_reqheight())
            chrome_height = max(0, requested_height - requested_rows * self.TREE_ROW_HEIGHT)
            horizontal_height = (
                self.h_scrollbar.winfo_reqheight()
                if self._horizontal_scroll_required
                else 0
            )

            available_row_height = max(
                self.TREE_ROW_HEIGHT,
                frame_height - chrome_height - horizontal_height,
            )

            visible_rows = max(1, available_row_height // self.TREE_ROW_HEIGHT)
        except (tk.TclError, ValueError, TypeError):
            return

        if requested_rows != visible_rows:
            self.tree.configure(height=visible_rows)

    def apply_theme(self, theme_service, theme_name: str):
        colors = theme_service.get_color_scheme(theme_name)
        self._current_colors = colors
        self.v_scrollbar.apply_theme(colors)
        self.h_scrollbar.apply_theme(colors)

        order_button_colors = dict(colors)

        order_button_colors.update(
            {
                "nav_bg": colors["button_bg"],
                "nav_active_bg": colors["button_active_bg"],
                "nav_pressed_bg": colors["button_pressed_bg"],
                "nav_fg": colors["button_fg"],
            }
        )

        self.move_up_button.apply_theme(order_button_colors)
        self.move_down_button.apply_theme(order_button_colors)

        style = ttk.Style(self)

        style.configure(
            "ModList.Treeview",
            background=colors["text_bg"],
            fieldbackground=colors["text_bg"],
            foreground=colors["fg"],
            bordercolor=colors["menu_active_bg"],
            lightcolor=colors["menu_active_bg"],
            darkcolor=colors["menu_active_bg"],
            rowheight=self.TREE_ROW_HEIGHT,
        )
        
        style.layout(
            "ModList.Treeview.Item",
            [
                (
                    "Treeitem.padding",
                    {
                        "sticky": "nswe",
                        "children": [
                            ("Treeitem.image", {"side": "left", "sticky": ""}),
                            ("Treeitem.text", {"sticky": "nswe"}),
                        ],
                    },
                )
            ],
        )
        style.configure("ModList.Treeview.Item", padding=(0, 0, 0, 0))
        # Keep selection as a background-only highlight... - Tim
        style.map(
            "ModList.Treeview",
            background=[("selected", colors["select_bg"])],
            foreground=[],
        )
        style.configure(
            "ModList.Treeview.Heading",
            background=colors["menu_bg"],
            foreground=colors["fg"],
            relief="flat",
        )
        style.map(
            "ModList.Treeview.Heading",
            background=[("active", colors["menu_active_bg"])],
        )

        self.tree.tag_configure("disabled", foreground=colors["muted_fg"])
        self.tree.tag_configure("warning", foreground=colors["warning_fg"])
        self.tree.tag_configure("error", foreground=colors["error_fg"])

        self._checkbox_images = {
            False: self._make_checkbox_image(False, colors),
            True: self._make_checkbox_image(True, colors),
        }
        for name, iid in self._iid_by_name.items():
            enabled = self._enabled_by_name.get(name, False)
            self.tree.item(iid, image=self._checkbox_images[enabled])
        self._schedule_tree_row_fit()

    def _make_checkbox_image(self, enabled: bool, colors: Dict[str, str]) -> tk.PhotoImage:
        """Render an anti-aliased checkbox instead of a pixel-stepped Tk glyph..."""

        scale = 4
        width, height = 34, 24
        image = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        def box(coords, fill, radius=0):
            scaled = tuple(value * scale for value in coords)
            if radius:
                draw.rounded_rectangle(scaled, radius=radius * scale, fill=fill)
            else:
                draw.rectangle(scaled, fill=fill)

        border = colors["muted_fg"]
        fill = colors["select_bg"] if enabled else colors["text_bg"]
        box((4, 0, 28, 24), border, radius=4)
        box((6, 2, 26, 22), fill, radius=2)

        if enabled:
            check_color = colors["select_fg"]
            points = [(9 * scale, 12 * scale), (14 * scale, 17 * scale), (22 * scale, 7 * scale)]
            line_width = 3 * scale
            draw.line(points, fill=check_color, width=line_width, joint="curve")
            cap_radius = line_width // 2

            for x, y in (points[0], points[-1]):
                draw.ellipse(
                    (x - cap_radius, y - cap_radius, x + cap_radius, y + cap_radius),
                    fill=check_color,
                )

        image = image.resize((width, height), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image, master=self)

    def clear(self):
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        self._name_by_iid.clear()
        self._iid_by_name.clear()
        self._enabled_by_name.clear()
        self._update_order_button_state()
        self._schedule_tree_row_fit()

    def add_item(
        self,
        name: str,
        author: str,
        version: str,
        enabled: bool,
        status: Optional[str] = None,
    ):
        iid = f"mod_{len(self._name_by_iid)}"
        tags = []
        if status in ("warning", "error"):
            tags.append(status)
        elif not enabled:
            tags.append("disabled")

        self.tree.insert(
            "",
            "end",
            iid=iid,
            image=self._checkbox_images.get(enabled, ""),
            text=name,
            values=(author, version),
            tags=tuple(tags),
        )
        self._name_by_iid[iid] = name
        self._iid_by_name[name] = iid
        self._enabled_by_name[name] = enabled
        self._update_order_button_state()
        self._schedule_tree_row_fit()

    def get_items(self) -> List[str]:
        return [
            self._name_by_iid[iid]
            for iid in self.tree.get_children("")
            if iid in self._name_by_iid
        ]

    def get_enabled_items(self) -> List[str]:
        return [name for name in self.get_items() if self._enabled_by_name.get(name)]

    def get_selection(self) -> Optional[Tuple[int, str]]:
        selection = self.tree.selection()
        if not selection:
            return None
        iid = selection[0]
        name = self._name_by_iid.get(iid)
        if name is None:
            return None
        children = list(self.tree.get_children(""))
        return children.index(iid), name

    def select_item(self, index: int):
        children = self.tree.get_children("")
        if not children:
            return
        index = max(0, min(index, len(children) - 1))
        iid = children[index]
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.tree.see(iid)
        self._update_order_button_state()

    def select_name(self, name: str):
        iid = self._iid_by_name.get(name)
        if iid:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
            self._update_order_button_state()

    def get_name_at(self, y: int) -> Optional[str]:
        iid = self.tree.identify_row(y)
        return self._name_by_iid.get(iid) if iid else None

    def get_enabled_state(self, name: str) -> Optional[bool]:
        return self._enabled_by_name.get(name)

    def bind_event(self, event: str, handler: Callable):
        self.tree.bind(event, handler, add="+")

    def focus(self):
        self.tree.focus_set()
        if not self.tree.selection() and self.tree.get_children(""):
            self.select_item(0)
