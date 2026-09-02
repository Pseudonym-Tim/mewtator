import tkinter as tk
from tkinter import Toplevel, END, StringVar, BooleanVar, filedialog
from tkinter import ttk
from app.ui.components.compat_label import Label
from typing import Callable, Optional
import os
import webbrowser
import sys

from app.ui.windows.notification_window import NotificationWindow

class SettingsWindow:
    def __init__(
        self,
        parent,
        config,
        translation_service,
        theme_service,
        on_save: Callable,
        on_cancel: Optional[Callable] = None,
    ):
        self.parent = parent
        self.config = config
        self.translation_service = translation_service
        self.theme_service = theme_service
        self.on_save = on_save
        self.on_cancel = on_cancel

        self.win = Toplevel(parent)
        self.win.withdraw()
        self.win.title(translation_service.get("settings.title", "Settings"))
        self.win.resizable(True, True)
        if parent.state() != "withdrawn":
            self.win.transient(parent)
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)

        self._apply_theme()
        self._build_scrollable_content()
        self._build_ui()
        self._position_dialog()

        self.win.deiconify()
        self.win.lift()
        self.win.grab_set()
        self.win.focus_set()


    def _build_scrollable_content(self):
        """Create a vertically scrollable settings body while keeping Save visible..."""
        colors = self.theme_service.get_color_scheme(
            self.theme_service.normalize_theme_name(self.config.theme)
        )

        self._scroll_host = ttk.Frame(self.win)
        self._scroll_host.pack(fill="both", expand=True)

        self._settings_canvas = tk.Canvas(
            self._scroll_host,
            background=colors["bg"],
            borderwidth=0,
            highlightthickness=0,
        )
        self._settings_scrollbar = ttk.Scrollbar(
            self._scroll_host, orient="vertical", command=self._settings_canvas.yview
        )
        self._settings_canvas.configure(yscrollcommand=self._settings_scrollbar.set)

        self._settings_scrollbar.pack(side="right", fill="y")
        self._settings_canvas.pack(side="left", fill="both", expand=True)

        self.content_frame = ttk.Frame(self._settings_canvas)
        self._content_window = self._settings_canvas.create_window(
            (0, 0), window=self.content_frame, anchor="nw"
        )

        self.content_frame.bind(
            "<Configure>",
            lambda _event: self._settings_canvas.configure(
                scrollregion=self._settings_canvas.bbox("all")
            ),
        )
        self._settings_canvas.bind(
            "<Configure>",
            lambda event: self._settings_canvas.itemconfigure(
                self._content_window, width=event.width
            ),
        )

        def _wheel(event):
            if getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            else:
                delta = -int(event.delta / 120) if event.delta else 0
            if delta:
                self._settings_canvas.yview_scroll(delta, "units")

        self.win.bind("<MouseWheel>", _wheel, add="+")
        self.win.bind("<Button-4>", _wheel, add="+")
        self.win.bind("<Button-5>", _wheel, add="+")

    def _position_dialog(self):
        """Center Settings over its parent without changing the parent geometry..."""

        screen_width = self.win.winfo_screenwidth()
        screen_height = self.win.winfo_screenheight()
        width = min(760, max(640, screen_width - 40), screen_width)
        height = min(790, max(520, screen_height - 80), screen_height)

        # Make sure parent geometry is current before reading it...
        try:
            self.parent.update_idletasks()
        except Exception:
            pass

        try:
            parent_visible = self.parent.state() != "withdrawn"
        except Exception:
            parent_visible = False

        if parent_visible:
            try:
                parent_x = self.parent.winfo_rootx()
                parent_y = self.parent.winfo_rooty()
                parent_width = self.parent.winfo_width()
                parent_height = self.parent.winfo_height()
                x = parent_x + max(0, (parent_width - width) // 2)
                y = parent_y + max(0, (parent_height - height) // 2)
            except Exception:
                parent_visible = False

        if not parent_visible:
            x = max(0, (screen_width - width) // 2)
            y = max(0, (screen_height - height) // 2)

        # Clamp to visible desktop so centering a large dialog over a
        # partially off-screen parent can't push it farther off-screen... - Tim
        x = max(0, min(x, max(0, screen_width - width)))
        y = max(0, min(y, max(0, screen_height - height)))

        self.win.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_theme(self):
        theme_name = self.theme_service.normalize_theme_name(self.config.theme)
        colors = self.theme_service.get_color_scheme(theme_name)
        self.win.configure(bg=colors["bg"])
        self.theme_service.apply_titlebar(self.win, theme_name)

        style = ttk.Style(self.win)
        hint_color = "#9a9a9a" if theme_name == "dark" else "#666666"
        style.configure("Settings.Hint.TLabel", foreground=hint_color, background=colors["bg"])
        
        # Configure link style
        link_color = "#5DADE2" if theme_name == "dark" else "#2E7DBE"
        style.configure("Settings.Link.TLabel", foreground=link_color, background=colors["bg"])
        

    def _build_ui(self):
        t = self.translation_service
        platform_is_linux = sys.platform.startswith("linux")
        
        # Auto-Detect Game Install
        auto_detect_btn = ttk.Button(
            self.content_frame,
            text=t.get("settings.auto_detect"),
            command=self._auto_detect,
            style="Primary.TButton",
            width=25,
            cursor="hand2",
        )
        auto_detect_btn.pack(pady=10)
        
        # Game Install Directory
        self.game_entry, game_btn = self._make_row(
            t.get("settings.game_install_dir"),
            has_button=True,
            initial_text=self.config.game_install_dir,
            button_cfg={'command': self._browse_game}
        )
        
        # Mods Folder
        self.mod_entry, mod_btn = self._make_row(
            t.get("settings.mods_folder"),
            has_button=True,
            initial_text=self.config.mod_folder,
            button_cfg={'command': self._browse_mod}
        )

        # (Linux) Steam Linux Runtime
        self.linux_steam_runtime_path_entry, linux_steam_runtime_path_btn = self._make_row(
            t.get("settings.linux_steam_runtime_path"),
            has_button=True,
            initial_text=self.config.linux_steam_runtime_path,
            button_cfg={'command': self._browse_linux_steam_runtime},
            show=platform_is_linux
        )

        # (Linux) Proton
        self.linux_proton_path_entry, linux_proton_path_btn = self._make_row(
            t.get("settings.linux_proton_path"),
            has_button=True,
            initial_text=self.config.linux_proton_path,
            button_cfg={'command': self._browse_linux_proton},
            show=platform_is_linux
        )

        # Language
        lang_row = ttk.Frame(self.content_frame)
        lang_row.pack(fill="x", padx=10, pady=5)
        
        Label(lang_row, text=t.get("settings.language"), width=20, anchor="w").pack(side="left")
        
        from app.infrastructure.translation_repository import TranslationRepository
        available_langs = TranslationRepository().get_available_languages()
        
        self.lang_var = StringVar(value=self.config.language)
        
        lang_menu = ttk.Combobox(
            lang_row,
            textvariable=self.lang_var,
            values=available_langs,
            state="readonly",
            width=25,
            height=15,
            cursor="hand2",
            style="Settings.Language.TCombobox",
        )
        lang_menu.pack(side="left", padx=5)

        def clear_language_text_selection(_event=None):
            self.win.after_idle(lang_menu.selection_clear)

        lang_menu.bind("<<ComboboxSelected>>", clear_language_text_selection, add="+")
        lang_menu.bind("<FocusIn>", clear_language_text_selection, add="+")
        
        # Launch Options
        self._add_separator(t.get("settings.launch_options", "Launch Options"))
        
        # Custom Launch Options
        self.custom_launch_entry, _ = self._make_row(
            t.get("settings.custom_launch_options", "Custom Launch Options"),
            has_button=False,
            initial_text=self.config.custom_launch_options
        )
        
        checkbox_frame = ttk.Frame(self.content_frame)
        checkbox_frame.pack(fill="x", padx=30, pady=5)
        
        # Enable Dev Mode
        self.dev_mode_var = BooleanVar(value=self.config.dev_mode_enabled)
        dev_mode_check = ttk.Checkbutton(
            checkbox_frame,
            text=t.get("settings.dev_mode", "Enable Dev Mode (-dev_mode true)"),
            variable=self.dev_mode_var,
            cursor="hand2"
        )
        dev_mode_check.pack(anchor="w")

        # Enable Debug Console
        self.debug_console_var = BooleanVar(value=self.config.debug_console_enabled)
        debug_console_check = ttk.Checkbutton(
            checkbox_frame,
            text=t.get("settings.debug_console", "Enable Debug Console (-enable_debugconsole true)"),
            variable=self.debug_console_var,
            cursor="hand2"
        )
        debug_console_check.pack(anchor="w")

        # Enable Mewtator custom game intro
        self.mewtator_intro_var = BooleanVar(
            value=getattr(self.config, "mewtator_intro_enabled", True)
        )
        mewtator_intro_check = ttk.Checkbutton(
            checkbox_frame,
            text=t.get(
                "settings.mewtator_intro",
                "Enable Mewtator custom game intro",
            ),
            variable=self.mewtator_intro_var,
            cursor="hand2"
        )
        mewtator_intro_check.pack(anchor="w")

        # Enable DLL Mod Support
        self.dll_injection_var = BooleanVar(value=self.config.dll_injection_enabled)
        dll_injection_check = ttk.Checkbutton(
            checkbox_frame,
            text=t.get("settings.dll_injection", "Enable DLL Mod Support"),
            variable=self.dll_injection_var,
            cursor="hand2"
        )
        dll_injection_check.pack(anchor="w")
        
        # Add hint label for DLL injection
        dll_hint_text = t.get("settings.dll_injection_hint", "Creates manifest for Mewjector chainloader (required for .dll mods)\nGet Mewjector: nexusmods.com/mewgenics/mods/218")
        lines = dll_hint_text.split('\n')
        
        dll_hint_label = Label(
            checkbox_frame,
            text=lines[0],
            font="MewtatorSmall",
            style="Settings.Hint.TLabel"
        )
        dll_hint_label.pack(anchor="w", padx=(20, 0))
        
        # Create a frame for the link line
        link_frame = ttk.Frame(checkbox_frame)
        link_frame.pack(anchor="w", padx=(20, 0))
        
        # Add the "Get Mewjector: " label
        get_text_label = Label(
            link_frame,
            text=t.get("settings.mewjector_link_text", "Get Mewjector: "),
            font="MewtatorSmall",
            style="Settings.Hint.TLabel"
        )
        get_text_label.pack(side="left")
        
        # Add the clickable link
        mewjector_url = "https://www.nexusmods.com/mewgenics/mods/218"
        link_label = Label(
            link_frame,
            text=t.get("settings.mewjector_url_display", "nexusmods.com/mewgenics/mods/218"),
            font="MewtatorSmallUnderline",
            style="Settings.Link.TLabel",
            cursor="hand2"
        )
        link_label.pack(side="left")
        link_label.bind("<Button-1>", lambda e: webbrowser.open(mewjector_url))
        
        # Add security warning for DLL injection
        dll_warning_label = Label(
            checkbox_frame,
            text=t.get("settings.dll_injection_warning", "\u26a0 Security: Only install DLL mods from trusted sources"),
            font="MewtatorSmallBold",
            foreground="#FF6B6B"
        )
        dll_warning_label.pack(anchor="w", padx=(20, 0))
        
        # TEMPORARILY DISABLED: These features are not yet functional in the game
        # # Mod Launch Settings Overrides Section
        # self._add_separator(t.get("settings.mod_overrides", "Mod Launch Settings Overrides"))
        # 
        # self.savefile_suffix_entry, _ = self._make_row(t.get("settings.savefile_suffix_override", "Savefile Suffix Override"), has_button=False)
        # if self.config.savefile_suffix_override:
        #     self.savefile_suffix_entry.insert(0, self.config.savefile_suffix_override)
        # 
        # self.inherit_save_entry, _ = self._make_row(t.get("settings.inherit_save_override", "Inherit Save Override"), has_button=False)
        # if self.config.inherit_save_override:
        #     self.inherit_save_entry.insert(0, self.config.inherit_save_override)
        
        # Appearance
        self._add_separator(t.get("settings.appearance", "Appearance"))

        appearance_frame = ttk.Frame(self.content_frame)
        appearance_frame.pack(fill="x", padx=30, pady=5)

        # Use standard system font
        self.use_generic_font_var = BooleanVar(value=self.config.use_generic_font)
        generic_font_check = ttk.Checkbutton(
            appearance_frame,
            text=t.get("settings.use_generic_font", "Use standard system font"),
            variable=self.use_generic_font_var,
            cursor="hand2"
        )
        generic_font_check.pack(anchor="w")
        Label(
            appearance_frame,
            text=t.get(
                "settings.use_generic_font_hint",
                "Improves readability",
            ),
            style="Settings.Hint.TLabel",
            wraplength=670,
        ).pack(anchor="w", padx=(20, 0), pady=(2, 0))

        # Advanced Section
        self._add_separator(t.get("settings.advanced", "Advanced"))
        
        advanced_frame = ttk.Frame(self.content_frame)
        advanced_frame.pack(fill="x", padx=30, pady=5)
        
        # Close Launcher When Game Launches
        self.close_on_launch_var = BooleanVar(value=self.config.close_on_launch)
        close_on_launch_check = ttk.Checkbutton(
            advanced_frame,
            text=t.get("settings.close_on_launch", "Close Launcher When Game Launches"),
            variable=self.close_on_launch_var,
            cursor="hand2"
        )
        close_on_launch_check.pack(anchor="w")

        # Linux launch options
        # (Linux) Allow launch without Steam Linux Runtime or Proton
        self.linux_allow_undefined_steam_runtime_or_proton_var = BooleanVar(value=self.config.linux_allow_undefined_steam_runtime_or_proton)
        linux_allow_undefined_steam_runtime_or_proton_check = ttk.Checkbutton(
            advanced_frame,
            text=t.get("settings.linux_allow_undefined_steam_runtime_or_proton", "Allow launch without Steam Linux Runtime or Proton"),
            variable=self.linux_allow_undefined_steam_runtime_or_proton_var,
            cursor="hand2"
        )
        if platform_is_linux:
            linux_allow_undefined_steam_runtime_or_proton_check.pack(anchor="w")

        # (Linux) Disable Steam game overlay
        self.linux_steam_gameoverlayrenderer_disabled_var = BooleanVar(value=self.config.linux_steam_gameoverlayrenderer_disabled)
        linux_steam_gameoverlayrenderer_disabled_check = ttk.Checkbutton(
            advanced_frame,
            text=t.get("settings.linux_steam_gameoverlayrenderer_disabled", "Disable Steam game overlay"),
            variable=self.linux_steam_gameoverlayrenderer_disabled_var,
            cursor="hand2"
        )
        # if platform_is_linux:
        #     linux_steam_gameoverlayrenderer_disabled_check.pack(anchor="w")

        # (Linux) compatdata override
        self.linux_compatdata_override_dir_entry, linux_compatdata_override_dir_btn = self._make_row(
            t.get("settings.linux_compatdata_override_dir", "compatdata override"),
            has_button=True,
            initial_text=self.config.linux_compatdata_override_dir,
            button_cfg={'command': self._browse_linux_compatdata_override_dir},
            show=False #platform_is_linux
        )
        # End Linux launch options

        # Save Settings
        save_btn = ttk.Button(
            self.win,
            text=t.get("settings.save", "Save Settings"),
            command=self._save_settings,
            style="Primary.TButton",
            width=25,
            cursor="hand2",
        )
        save_btn.pack(side="bottom", pady=(8, 12))
        
        self.win.bind("<Return>", lambda e: self._save_settings() if e.widget not in [self.game_entry, self.mod_entry] else None)
        self.win.bind("<KP_Enter>", lambda e: self._save_settings() if e.widget not in [self.game_entry, self.mod_entry] else None)
        self.win.bind("<Escape>", lambda e: self._cancel())
        
        self.game_entry.focus_set()

    def _cancel(self):
        self.win.destroy()
        if self.on_cancel is not None:
            self.on_cancel()
    
    def _add_separator(self, text: str):
        """Add a section separator with label."""
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill="x", padx=10, pady=(10, 5))
        
        Label(
            frame,
            text=text,
            font="MewtatorBodyBold"
        ).pack(anchor="w")
        
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(2, 0))
    
    def _make_row(self, label_text: str, has_button: bool = True, initial_text: str = None, button_cfg: {} = None, show = True):
        row = ttk.Frame(self.content_frame)
        if show:
            row.pack(fill="x", padx=10, pady=5)
        
        lbl = Label(row, text=label_text, width=20, anchor="w")
        lbl.pack(side="left")
        
        entry = ttk.Entry(row, width=50, font="MewtatorBody")
        entry.pack(side="left", fill="x", expand=True, padx=5)
        if initial_text is not None:
            entry.insert(0, initial_text)

        btn = None
        if has_button:
            btn = ttk.Button(
                row,
                text=self.translation_service.get("settings.browse"),
                style="Compact.TButton",
                width=11,
                cursor="hand2",
            )
            btn.pack(side="right", padx=2)
            if button_cfg is not None:
                btn.config(**button_cfg)

        return entry, btn
    
    def _auto_detect(self):
        from app.utils.game_detector import auto_detect_game_install
        from app.utils.platform_utils import get_executable_dir

        detected = auto_detect_game_install("Mewgenics")
        if detected:
            self.game_entry.delete(0, END)
            self.game_entry.insert(0, detected)
        else:
            self._show_notification(
                self.translation_service.get("messages.game_dir_not_found"),
                self.translation_service.get("messages.game_dir_not_detected"),
                kind="warning",
            )

        exe_dir = get_executable_dir()
        self.mod_entry.delete(0, END)
        self.mod_entry.insert(0, os.path.join(exe_dir, "mods"))

        if sys.platform.startswith("linux"):
            # Proton is paired with a Steam Linux Runtime version
            # https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/slr-for-game-developers.md#running-a-game-under-proton-in-the-steam-linux-runtime-environment

            proton_search_candidates = [
                # Proton 8.0 and below fail to launch Mewgenics
                # There is good coverage of Mewgenics running successfully with Proton 10.0 and 9.0 on ProtonDB
                ('Proton 10.0', 'SteamLinuxRuntime_sniper'),
                ('Proton 9.0 (Beta)', 'SteamLinuxRuntime_sniper'),
                ('Proton 11.0', 'SteamLinuxRuntime_4'),
                # Floating branches were tied to SteamLinuxRuntime_4 in 2026
                ('Proton - Experimental', 'SteamLinuxRuntime_4'),
                ('Proton Hotfix', 'SteamLinuxRuntime_4'),
            ]

            pair_found = False
            for proton_app_name, steam_linux_runtime_app_name in proton_search_candidates:
                linux_steam_runtime_detected = auto_detect_game_install(steam_linux_runtime_app_name)
                proton_detected = auto_detect_game_install(proton_app_name)
                if linux_steam_runtime_detected and proton_detected:
                    runtime_launcher = os.path.join(linux_steam_runtime_detected, "run")
                    proton_launcher = os.path.join(proton_detected, "proton")
                    if not (os.path.isfile(runtime_launcher) and os.path.isfile(proton_launcher)):
                        continue

                    self.linux_steam_runtime_path_entry.delete(0, END)
                    self.linux_steam_runtime_path_entry.insert(0, runtime_launcher)
                    self.linux_proton_path_entry.delete(0, END)
                    self.linux_proton_path_entry.insert(0, proton_launcher)
                    pair_found = True
                    break
            if not pair_found:
                self._show_notification(
                    self.translation_service.get("messages.game_dir_not_found"),
                    self.translation_service.get("messages.proton_or_steam_linux_runtime_not_detected"),
                    kind="warning",
                )

    def _browse_game(self):
        from app.utils.platform_utils import get_executable_dir
        
        with self.theme_service.file_dialog_safe_theme():
            path = filedialog.askdirectory(parent=self.win)
        
        if path:
            self.game_entry.delete(0, END)
            self.game_entry.insert(0, path)
            
            exe_dir = get_executable_dir()
            self.mod_entry.delete(0, END)
            self.mod_entry.insert(0, os.path.join(exe_dir, "mods"))
    
    def _browse_mod(self):
        with self.theme_service.file_dialog_safe_theme():
            path = filedialog.askdirectory(parent=self.win)
        
        if path:
            self.mod_entry.delete(0, END)
            self.mod_entry.insert(0, path)

    def _browse_linux_steam_runtime(self):
        with self.theme_service.file_dialog_safe_theme():
            path = filedialog.askopenfilename(
                parent=self.win,
                filetypes=[(self.translation_service.get("messages.steam_linux_runtime_launcher_file"), "run"), (self.translation_service.get("all_files"), "*")]
            )
        
        if path:
            self.linux_steam_runtime_path_entry.delete(0, END)
            self.linux_steam_runtime_path_entry.insert(0, path)

    def _browse_linux_proton(self):
        with self.theme_service.file_dialog_safe_theme():
            path = filedialog.askopenfilename(
                parent=self.win,
                filetypes=[(self.translation_service.get("messages.proton_launcher_file"), "proton"), (self.translation_service.get("all_files"), "*")]
            )
        
        if path:
            self.linux_proton_path_entry.delete(0, END)
            self.linux_proton_path_entry.insert(0, path)

    def _browse_linux_compatdata_override_dir(self):
        with self.theme_service.file_dialog_safe_theme():
            path = filedialog.askdirectory(parent=self.win)
        
        if path:
            self.linux_compatdata_override_dir_entry.delete(0, END)
            self.linux_compatdata_override_dir_entry.insert(0, path)

    def _show_notification(
        self,
        title: str,
        message: str,
        kind: str = "info",
    ):
        NotificationWindow(
            self.win,
            title,
            message,
            self.theme_service,
            button_text=self.translation_service.get("common.ok", "OK"),
            kind=kind,
        ).show()
    
    def _save_settings(self):
        from app.utils.platform_utils import get_executable_dir
        
        game = self.game_entry.get().strip()
        mod = self.mod_entry.get().strip()
        language = self.lang_var.get()
        
        # Validate game directory
        if not game:
            self._show_notification(
                self.translation_service.get("messages.error"),
                self.translation_service.get("messages.game_dir_required"),
                kind="error",
            )
            return
        
        game = os.path.normpath(game)
        
        if not os.path.isdir(game):
            self._show_notification(
                self.translation_service.get("messages.error"),
                self.translation_service.get("messages.game_dir_invalid"),
                kind="error",
            )
            return
        
        # Validate mod directory
        if not mod:
            exe_dir = get_executable_dir()
            mod = os.path.join(exe_dir, "mods")
        else:
            mod = os.path.normpath(mod)
        
        os.makedirs(mod, exist_ok=True)
        
        modlist_path = os.path.join(mod, "modlist.txt")
        if not os.path.exists(modlist_path):
            with open(modlist_path, "w", encoding="utf-8") as f:
                f.write("")

        # Validate Steam Linux Runtime/Proton files
        linux_steam_runtime_path = os.path.normpath(self.linux_steam_runtime_path_entry.get().strip()) if self.linux_steam_runtime_path_entry.get().strip() else ""
        linux_proton_path = os.path.normpath(self.linux_proton_path_entry.get().strip()) if self.linux_proton_path_entry.get().strip() else ""
        platform_is_linux = sys.platform.startswith("linux")
        if platform_is_linux:
            linux_allow_undefined_steam_runtime_or_proton = self.linux_allow_undefined_steam_runtime_or_proton_var.get()
            if linux_steam_runtime_path and not os.path.isfile(linux_steam_runtime_path):
                self._show_notification(
                    self.translation_service.get("messages.error"),
                    self.translation_service.get("messages.path_invalid").format(name='Steam Linux Runtime'),
                    kind="error",
                )
                return
            if linux_proton_path and not os.path.isfile(linux_proton_path):
                self._show_notification(
                    self.translation_service.get("messages.error"),
                    self.translation_service.get("messages.path_invalid").format(name='Proton'),
                    kind="error",
                )
                return

        # compatdata is checked at launch time
        linux_compatdata_override_dir = os.path.normpath(self.linux_compatdata_override_dir_entry.get().strip()) if self.linux_compatdata_override_dir_entry.get().strip() else ""

        self.config.game_install_dir = game
        self.config.mod_folder = mod
        self.config.language = language
        self.config.custom_launch_options = self.custom_launch_entry.get().strip()
        self.config.dev_mode_enabled = self.dev_mode_var.get()
        self.config.debug_console_enabled = self.debug_console_var.get()
        self.config.mewtator_intro_enabled = self.mewtator_intro_var.get()
        self.config.dll_injection_enabled = self.dll_injection_var.get()
        self.config.use_generic_font = self.use_generic_font_var.get()
        # TEMPORARILY DISABLED: These features are not yet functional in the game
        # self.config.savefile_suffix_override = self.savefile_suffix_entry.get().strip()
        # self.config.inherit_save_override = self.inherit_save_entry.get().strip()
        self.config.close_on_launch = self.close_on_launch_var.get()
        self.config.linux_allow_undefined_steam_runtime_or_proton = self.linux_allow_undefined_steam_runtime_or_proton_var.get()
        self.config.linux_steam_gameoverlayrenderer_disabled = self.linux_steam_gameoverlayrenderer_disabled_var.get()
        self.config.linux_steam_runtime_path = linux_steam_runtime_path
        self.config.linux_proton_path = linux_proton_path
        self.config.linux_compatdata_override_dir = linux_compatdata_override_dir
        
        self.win.destroy()
        self.on_save(self.config)
