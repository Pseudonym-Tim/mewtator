import os
import tkinter as tk
from tkinter import messagebox, Toplevel, Label, Text, Button, WORD, BOTH, filedialog, simpledialog
from tkinter import ttk
import webbrowser
from app.core.models.mod_list import ModList
from app.core.services.mod_service import ModService
from app.core.services.config_service import ConfigService
from app.core.services.game_launcher_service import GameLauncherService
from app.core.services.dll_injection_service import DllInjectionService
from app.core.services.translation_service import TranslationService
from app.core.services.pack_service import PackService
from app.core.services.modlist_io_service import ModListIOService
from app.core.services.theme_service import ThemeService
from app.ui.windows.main_window import MainWindow
from app.ui.windows.settings_window import SettingsWindow
from app.ui.windows.progress_window import ProgressWindow
from app.utils.logging_utils import get_logger
from app.utils.platform_utils import open_file_or_folder


class MainController:
    def __init__(
        self,
        root: tk.Tk,
        config_service: ConfigService,
        mod_service: ModService,
        launcher_service: GameLauncherService,
        translation_service: TranslationService,
        pack_service: PackService,
        modlist_io_service: ModListIOService,
        theme_service: ThemeService,
        dll_injection_service: DllInjectionService = None
    ):
        self.root = root
        self.config_service = config_service
        self.mod_service = mod_service
        self.launcher_service = launcher_service
        self.dll_injection_service = dll_injection_service or DllInjectionService()
        self.translation_service = translation_service
        self.pack_service = pack_service
        self.modlist_io_service = modlist_io_service
        self.theme_service = theme_service
        
        self.config = config_service.load_config()
        self.mod_list: ModList = None
        self.window: MainWindow = None
        
        self.last_mtime = 0
        self.last_mod_folders = set()
        
        self.drag_data = {"source": None, "index": None, "changed": False}
        self.drag_indicator = None
    
    def start(self):
        if not self.config_service.validate_config(self.config):
            self.theme_service.set_theme(self.config.theme)
            self._show_info_dialog(
                self.translation_service.get("messages.setup_required_title"),
                self.translation_service.get("messages.setup_required_text")
            )
            self._show_settings()
            self.root.mainloop()
            return
        
        self._build_main_window()
        self._setup_auto_refresh()
        self.root.mainloop()
    
    def _build_main_window(self):
        self.theme_service.set_theme(self.config.theme)
        self.window = MainWindow(self.root, self.translation_service)
        
        self.mod_list = self.mod_service.load_mods()
        self.mod_list.add_observer(self._on_mod_list_changed)
        
        self.window.set_disabled_list_action(self._disable_all)
        self.window.set_enabled_list_action(self._enable_all)
        self.window.set_swap_action(self._swap_selected)
        self.window.set_auto_sort_action(self._auto_sort)
        self.window.set_launch_action(self._launch_game)
        
        self._setup_menu_bar()
        self._setup_list_bindings()
        self._setup_keyboard_shortcuts()

        # Validate requirements before first refresh
        self.mod_service.validate_requirements(self.mod_list)
        self._refresh_lists()
        self.window.apply_theme(self.theme_service, self.config.theme)
        self._auto_configure_chainloader()
    
    def _setup_menu_bar(self):
        self.window.menu_bar.create_file_menu(
            on_settings=self._show_settings,
            on_import=self._import_modlist,
            on_export=self._export_modlist,
            on_unpack=self._unpack,
            on_repack=self._repack,
            on_open_mods=lambda: open_file_or_folder(self.config.mod_folder),
            on_open_game=lambda: open_file_or_folder(self.config.game_install_dir),
            on_launch=self._launch_game,
            on_copy_launch=self._copy_launch_options,
            on_cleanup_dlls=self._cleanup_dll_injection,
            on_exit=self.root.quit
        )
        
        available_langs = self.translation_service.get_available_languages()
        self.window.menu_bar.create_language_menu(
            available_langs,
            self.config.language,
            self._change_language
        )
        
        available_themes = self.theme_service.get_available_themes()
        self.window.menu_bar.create_theme_menu(
            available_themes,
            self.config.theme,
            self._change_theme
        )
    
    def _setup_list_bindings(self):
        disabled_widget = self.window.disabled_list_widget
        enabled_widget = self.window.enabled_list_widget
        
        disabled_widget.bind_event("<<ListboxSelect>>", lambda e: self._update_preview_from_disabled())
        enabled_widget.bind_event("<<ListboxSelect>>", lambda e: self._update_preview_from_enabled())
        
        disabled_widget.bind_event("<Double-Button-1>", lambda e: self._enable_selected_disabled(e))
        enabled_widget.bind_event("<Double-Button-1>", lambda e: self._disable_selected_enabled(e))
        
        disabled_widget.bind_event("<Button-3>", lambda e: self._show_context_menu_disabled(e))
        enabled_widget.bind_event("<Button-3>", lambda e: self._show_context_menu_enabled(e))
        
        disabled_widget.bind_event("<Return>", lambda e: self._toggle_disabled())
        disabled_widget.bind_event("<space>", lambda e: self._toggle_disabled())
        enabled_widget.bind_event("<Return>", lambda e: self._toggle_enabled())
        enabled_widget.bind_event("<space>", lambda e: self._toggle_enabled())
        
        enabled_widget.bind_event("<w>", lambda e: self._move_up())
        enabled_widget.bind_event("<s>", lambda e: self._move_down())
        enabled_widget.bind_event("<W>", lambda e: self._move_to_top())
        enabled_widget.bind_event("<S>", lambda e: self._move_to_bottom())
        
        disabled_widget.bind_event("<bracketleft>", lambda e: self._switch_to_enabled())
        disabled_widget.bind_event("<bracketright>", lambda e: self._switch_to_enabled())
        enabled_widget.bind_event("<bracketleft>", lambda e: self._switch_to_disabled())
        enabled_widget.bind_event("<bracketright>", lambda e: self._switch_to_disabled())
        
        disabled_widget.bind_event("<Button-1>", lambda e: self._start_drag(e, disabled_widget.listbox))
        disabled_widget.bind_event("<B1-Motion>", lambda e: self._do_drag(e, disabled_widget.listbox))
        disabled_widget.bind_event("<ButtonRelease-1>", lambda e: self._end_drag(e, disabled_widget.listbox, enabled_widget.listbox))
        
        enabled_widget.bind_event("<Button-1>", lambda e: self._start_drag(e, enabled_widget.listbox))
        enabled_widget.bind_event("<B1-Motion>", lambda e: self._do_drag(e, enabled_widget.listbox))
        enabled_widget.bind_event("<ButtonRelease-1>", lambda e: self._end_drag(e, enabled_widget.listbox, disabled_widget.listbox))
    
    def _setup_keyboard_shortcuts(self):
        shortcuts = {
            "<F2>": lambda e: self._show_settings(),
            "<F3>": lambda e: self._copy_launch_options(),
            "<F5>": lambda e: self._launch_game(),
            "<Control-q>": lambda e: self.root.quit()
        }
        self.window.bind_keyboard_shortcuts(shortcuts)
    
    def _refresh_lists(self, preserve_selection=None):
        disabled_widget = self.window.disabled_list_widget
        enabled_widget = self.window.enabled_list_widget
        
        if preserve_selection is None:
            enabled_sel = enabled_widget.get_selection()
            disabled_sel = disabled_widget.get_selection()
            if enabled_sel:
                preserve_selection = ('enabled', enabled_sel[1])
            elif disabled_sel:
                preserve_selection = ('disabled', disabled_sel[1])
        
        disabled_widget.clear()
        enabled_widget.clear()
        
        for mod in self.mod_list.all_mods:
            if mod.enabled:
                if mod.missing:
                    color = "red"
                elif mod.has_unmet_requirements:
                    color = "orange"
                elif self.dll_injection_service.mod_has_dlls(mod) and not self.config.dll_injection_enabled:
                    color = "red"
                else:
                    color = None
                enabled_widget.add_item(mod.name, color)
            else:
                disabled_widget.add_item(mod.name)
        
        if preserve_selection:
            list_type, item_name = preserve_selection
            target_widget = enabled_widget if list_type == 'enabled' else disabled_widget
            items = target_widget.get_items()
            if item_name in items:
                target_widget.select_item(items.index(item_name))
    
    def _on_mod_list_changed(self):
        self.mod_service.validate_requirements(self.mod_list)
        self.mod_service.save_mod_order(self.mod_list)
        self._refresh_lists()
        self._update_dll_manifest()
    
    def _update_preview_from_disabled(self):
        selection = self.window.disabled_list_widget.get_selection()
        if selection:
            _, name = selection
            mod = self.mod_list.get_mod_by_name(name)
            if mod:
                has_dlls = self.dll_injection_service.mod_has_dlls(mod)
                self.window.preview_panel.update_preview(
                    mod.title, mod.author, mod.version, mod.description, mod.preview_path, mod.url, has_dlls
                )
    
    def _update_preview_from_enabled(self):
        selection = self.window.enabled_list_widget.get_selection()
        if selection:
            _, name = selection
            mod = self.mod_list.get_mod_by_name(name)
            if mod:
                has_dlls = self.dll_injection_service.mod_has_dlls(mod)
                self.window.preview_panel.update_preview(
                    mod.title, mod.author, mod.version, mod.description, mod.preview_path, mod.url, has_dlls
                )
    
    def _enable_all(self):
        # Check for DLL mods before enabling all
        if self.dll_injection_service.has_dll_mods(self.mod_list):
            if not self._check_dll_injection_prompt():
                return  # User declined or DLL support is disabled
        self.mod_list.enable_all()
    
    def _disable_all(self):
        self.mod_list.disable_all()
    
    def _enable_mod_with_dll_check(self, mod_name: str):
        """Enable a mod and check if DLL injection prompt should be shown."""
        mod = self.mod_list.get_mod_by_name(mod_name)
        if mod:
            # Check if this mod has DLLs
            if self.dll_injection_service.mod_has_dlls(mod):
                if not self._check_dll_injection_prompt():
                    return  # User declined or DLL support is disabled
        
        # Enable the mod
        self.mod_list.enable_mod(mod_name)
    
    def _auto_configure_chainloader(self):
        """Auto-detect chainloader.ini and configure it if found."""
        if not self.config.game_install_dir:
            return
        
        # Check if chainloader exists and DLL support is enabled
        if self.dll_injection_service.chainloader_exists(self.config.game_install_dir):
            if self.config.dll_injection_enabled:
                # Update manifest immediately
                self._update_dll_manifest()
    
    def _update_dll_manifest(self):
        """Update the DLL manifest file if DLL support is enabled."""
        if not self.config.game_install_dir or not self.config.mod_folder:
            return
        
        # Only update if DLL support is enabled and chainloader exists
        if self.config.dll_injection_enabled and self.dll_injection_service.chainloader_exists(self.config.game_install_dir):
            dll_mods = self.dll_injection_service.scan_for_dll_mods(self.mod_list)
            if dll_mods:
                self.dll_injection_service.update_chainloader_manifest(self.config.game_install_dir, self.config.mod_folder, dll_mods)
            else:
                # No DLL mods enabled, clear the manifest
                self.dll_injection_service.clear_chainloader_manifest(self.config.game_install_dir, self.config.mod_folder)
    
    def _check_dll_injection_prompt(self):
        """Check if DLL injection prompt should be shown and show it. Returns True if DLL support is enabled."""
        if not self.config.dll_injection_enabled:
            # Check if chainloader.ini exists in game directory
            chainloader_exists = False
            show_link = False
            warning_message = (
                "⚠ SECURITY WARNING: DLL files can execute arbitrary code with full system privileges. "
                "Only enable DLL mods from trusted sources!\n\n"
                "This mod contains DLL files. Would you like to enable DLL mod support?\n\n"
                "Mewtator will create a manifest file that Mewjector (external DLL chainloader) can read. "
                "You can change this setting later in Settings > Launch Options."
            )
            
            if self.config.game_install_dir:
                chainloader_exists = self.dll_injection_service.chainloader_exists(self.config.game_install_dir)
                if not chainloader_exists:
                    chainloader_warning = self.translation_service.get(
                        "messages.dll_injection_chainloader_warning",
                        "\n\n⚠ WARNING: chainloader.ini was not found in your game directory. You need to install Mewjector (DLL chainloader) for DLL mods to work."
                    )
                    warning_message += chainloader_warning
                    show_link = True
            
            result = self._show_dll_prompt_dialog(
                self.translation_service.get("messages.dll_injection_title", "Enable DLL Mod Support?"),
                self.translation_service.get("messages.dll_injection_prompt", warning_message),
                show_link=show_link
            )
            
            self.config.dll_injection_enabled = result
            self.config_service.save_config(self.config)
            
            # Update manifest immediately if enabled
            if result:
                self._update_dll_manifest()
            
            return result
        
        return True
    
    def _swap_selected(self):
        disabled_selection = self.window.disabled_list_widget.get_selection()
        enabled_selection = self.window.enabled_list_widget.get_selection()
        
        if disabled_selection:
            _, name = disabled_selection
            self._enable_mod_with_dll_check(name)
        elif enabled_selection:
            _, name = enabled_selection
            self.mod_list.disable_mod(name)
    
    def _toggle_disabled(self):
        selection = self.window.disabled_list_widget.get_selection()
        if selection:
            _, name = selection
            self._enable_mod_with_dll_check(name)
    
    def _toggle_enabled(self):
        selection = self.window.enabled_list_widget.get_selection()
        if selection:
            _, name = selection
            self.mod_list.disable_mod(name)
    
    def _enable_selected_disabled(self, event):
        widget = event.widget
        index = widget.nearest(event.y)
        if index >= 0:
            name = widget.get(index)
            self._enable_mod_with_dll_check(name)
    
    def _disable_selected_enabled(self, event):
        widget = event.widget
        index = widget.nearest(event.y)
        if index >= 0:
            name = widget.get(index)
            self.mod_list.disable_mod(name)
    
    def _move_up(self):
        selection = self.window.enabled_list_widget.get_selection()
        if selection:
            _, name = selection
            self.mod_list.move_up(name)
    
    def _move_down(self):
        selection = self.window.enabled_list_widget.get_selection()
        if selection:
            _, name = selection
            self.mod_list.move_down(name)
    
    def _move_to_top(self):
        selection = self.window.enabled_list_widget.get_selection()
        if selection:
            _, name = selection
            self.mod_list.move_to_top(name)
    
    def _move_to_bottom(self):
        selection = self.window.enabled_list_widget.get_selection()
        if selection:
            _, name = selection
            self.mod_list.move_to_bottom(name)
    
    def _switch_to_enabled(self):
        self.window.enabled_list_widget.focus()
    
    def _switch_to_disabled(self):
        self.window.disabled_list_widget.focus()
    
    def _start_drag(self, event, source_list):
        self.drag_data["source"] = source_list
        self.drag_data["index"] = source_list.nearest(event.y)
        self.drag_data["changed"] = False
        
        if self.drag_data["index"] >= 0 and self.drag_data["index"] < source_list.size():
            item_text = source_list.get(self.drag_data["index"])
            
            self.drag_indicator = tk.Toplevel(self.root)
            self.drag_indicator.wm_overrideredirect(True)
            self.drag_indicator.wm_attributes("-alpha", 0.8)
            self.drag_indicator.wm_attributes("-topmost", True)
            
            label = tk.Label(
                self.drag_indicator,
                text=f"📦 {item_text}",
                bg="#4a90e2",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=10,
                pady=5,
                relief="raised",
                borderwidth=2
            )
            label.pack()
            
            self.drag_indicator.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
    
    def _do_drag(self, event, source_list):
        if self.drag_indicator:
            self.drag_indicator.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
        
        if self.drag_data["source"] != source_list:
            return
        
        old_index = self.drag_data["index"]
        if old_index < 0 or old_index >= source_list.size():
            return
        
        new_index = source_list.nearest(event.y)
        
        if new_index != old_index and new_index >= 0 and new_index < source_list.size():
            item = source_list.get(old_index)
            source_list.delete(old_index)
            source_list.insert(new_index, item)
            source_list.selection_clear(0, tk.END)
            source_list.selection_set(new_index)
            self.drag_data["index"] = new_index
            self.drag_data["changed"] = True
    
    def _end_drag(self, event, source_list, target_list):
        if self.drag_indicator:
            self.drag_indicator.destroy()
            self.drag_indicator = None
        
        if self.drag_data["source"] != source_list:
            self.drag_data["changed"] = False
            return
        
        old_index = self.drag_data["index"]
        if old_index < 0 or old_index >= source_list.size():
            self.drag_data["changed"] = False
            return
        
        item = source_list.get(old_index)
        
        x, y = event.x_root, event.y_root
        widget = self.root.winfo_containing(x, y)
        
        moved_between_lists = False
        if widget == target_list:
            if source_list == self.window.enabled_list_widget.listbox:
                self.mod_list.disable_mod(item)
            else:
                self._enable_mod_with_dll_check(item)
            moved_between_lists = True
        
        if not moved_between_lists and self.drag_data["changed"]:
            enabled_names = list(self.window.enabled_list_widget.get_items())
            self.mod_list.set_order(enabled_names)
        
        self.drag_data["source"] = None
        self.drag_data["index"] = None
        self.drag_data["changed"] = False
    
    def _show_context_menu_disabled(self, event):
        widget = event.widget
        index = widget.nearest(event.y)
        if index < 0:
            return
        
        widget.selection_clear(0, tk.END)
        widget.selection_set(index)
        
        name = widget.get(index)
        
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label=self.translation_service.get("context_menu.enable"),
            command=lambda: self._enable_mod_with_dll_check(name)
        )
        menu.post(event.x_root, event.y_root)
    
    def _show_context_menu_enabled(self, event):
        widget = event.widget
        index = widget.nearest(event.y)
        if index < 0:
            return
        
        widget.selection_clear(0, tk.END)
        widget.selection_set(index)
        
        name = widget.get(index)
        
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label=self.translation_service.get("context_menu.move_top"),
            command=lambda: self.mod_list.move_to_top(name)
        )
        menu.add_command(
            label=self.translation_service.get("context_menu.move_bottom"),
            command=lambda: self.mod_list.move_to_bottom(name)
        )
        menu.add_command(
            label=self.translation_service.get("context_menu.disable"),
            command=lambda: self.mod_list.disable_mod(name)
        )
        menu.post(event.x_root, event.y_root)
    
    def _launch_game(self):
        missing = self.mod_service.get_missing_mod_names(self.mod_list)
        if missing:
            messagebox.showerror(
                self.translation_service.get("messages.missing_mods_title"),
                self.translation_service.get("messages.missing_mods_text", "").replace("{missing}", "\n".join(missing))
            )
            return
        
        req_errors = self.mod_service.validate_requirements(self.mod_list)
        if req_errors:
            error_msg = "\n".join(req_errors)
            result = messagebox.askyesno(
                self.translation_service.get("alerts.requirement_conflict", "Requirement Conflicts"),
                self.translation_service.get("alerts.requirement_conflict_text", "The following requirement conflicts were found:\n\n{errors}\n\nLaunch anyway?").format(errors=error_msg)
            )
            if not result:
                return
        
        # Check for conflicts in savefile_suffix and inherit_save
        conflicts = self.mod_service.detect_conflicts(self.mod_list, self.config)
        if conflicts:
            conflict_msg = "\n".join(conflicts)
            messagebox.showinfo(
                self.translation_service.get("alerts.savefile_conflict", "Launch Settings Info"),
                conflict_msg
            )
        
        enabled_paths = self.mod_service.get_enabled_mod_paths(self.mod_list)
        logger = get_logger()
        enabled_mods = [(mod.name, mod.path) for mod in self.mod_list.enabled_mods]
        logger.info("Launching game with %d enabled mods", len(enabled_mods))
        for name, path in enabled_mods:
            logger.info("Enabled mod: %s | %s", name, path)
        
        if self.launcher_service.should_warn_external_mods(self.config.game_install_dir, enabled_paths):
            result = messagebox.askyesno(
                self.translation_service.get("messages.proton_warning_title", "Proton/Steam Deck Warning"),
                self.translation_service.get("messages.proton_warning_text", "")
            )
            if not result:
                return
        
        try:
            self.launcher_service.launch_game(
                self.config.game_install_dir,
                enabled_paths,
                self.config,
                self.mod_list
            )
            
            # Close launcher if option is enabled
            if self.config.close_on_launch:
                self.root.destroy()
                
        except FileNotFoundError as e:
            messagebox.showerror(
                self.translation_service.get("messages.launch_error"),
                self.translation_service.get("messages.exe_not_found")
            )
        except Exception as e:
            messagebox.showerror(
                self.translation_service.get("messages.launch_error"),
                str(e)
            )
    
    def _copy_launch_options(self):
        missing = self.mod_service.get_missing_mod_names(self.mod_list)
        if missing:
            messagebox.showerror(
                self.translation_service.get("messages.missing_mods_title"),
                self.translation_service.get("messages.missing_mods_text", "").replace("{missing}", "\n".join(missing))
            )
            return
        
        enabled_paths = self.mod_service.get_enabled_mod_paths(self.mod_list)
        
        launch_opts = self.launcher_service.get_launch_options(
            self.config.game_install_dir,
            enabled_paths,
            self.config,
            self.mod_list
        )
        
        self.root.clipboard_clear()
        self.root.clipboard_append(launch_opts)
        self.root.update()
        
        dialog = Toplevel(self.root)
        dialog.title(self.translation_service.get("messages.launch_options_title", "Steam Launch Options"))
        dialog.geometry("700x550")
        dialog.transient(self.root)
        
        Label(
            dialog,
            text=self.translation_service.get("messages.launch_options_instructions", ""),
            wraplength=650,
            justify="left",
            pady=10
        ).pack()
        
        text_widget = Text(dialog, wrap=WORD, height=12, font=("Consolas", 9))
        text_widget.pack(fill=BOTH, expand=True, padx=10, pady=5)
        text_widget.insert("1.0", launch_opts)
        text_widget.config(state="normal")
        
        Button(
            dialog,
            text=self.translation_service.get("messages.copy_to_clipboard", "Copy to Clipboard"),
            command=lambda: [self.root.clipboard_clear(), self.root.clipboard_append(launch_opts), self.root.update()],
            width=30,
            height=2
        ).pack(pady=5)

        Button(
            dialog,
            text=self.translation_service.get("messages.export_bat", "Export to .BAT File"),
            command=lambda: self._export_bat_file(enabled_paths, dialog),
            width=30,
            height=2
        ).pack(pady=5)
        
        Button(
            dialog,
            text=self.translation_service.get("messages.close", "Close"),
            command=dialog.destroy,
            width=30,
            height=2
        ).pack(pady=5)
    
    def _export_bat_file(self, enabled_paths, parent_dialog=None):
        """Export launch configuration to a .bat file."""
        from app.utils.platform_utils import get_executable_dir
        
        default_name = "launch_mewgenics_mods.bat"
        default_path = os.path.join(self.config.game_install_dir, default_name)
        
        with self.theme_service.file_dialog_safe_theme():
            filepath = filedialog.asksaveasfilename(
                parent=parent_dialog or self.root,
                title=self.translation_service.get("messages.export_bat_title", "Export Launch Script"),
                initialfile=default_name,
                initialdir=self.config.game_install_dir,
                defaultextension=".bat",
                filetypes=[("Batch files", "*.bat"), ("All files", "*.*")]
            )
        
        if not filepath:
            return
        
        try:
            steam_launch_option = self.launcher_service.export_bat_file(
                self.config.game_install_dir,
                enabled_paths,
                filepath,
                self.config,
                self.mod_list
            )
            
            info_dialog = Toplevel(parent_dialog or self.root)
            info_dialog.title(self.translation_service.get("messages.export_bat_success_title", "Export Successful"))
            info_dialog.geometry("650x400")
            info_dialog.transient(parent_dialog or self.root)
            
            Label(
                info_dialog,
                text=self.translation_service.get("messages.export_bat_success", "Export Successful!"),
                font=("Arial", 12, "bold"),
                pady=10
            ).pack()
            
            Label(
                info_dialog,
                text=self.translation_service.get(
                    "messages.export_bat_instructions",
                    "The launch script has been saved. To use it with Steam:\n\n"
                    "1. Right-click Mewgenics in your Steam library\n"
                    "2. Select Properties → Launch Options\n"
                    "3. Paste the following line:\n"
                ),
                wraplength=600,
                justify="left",
                pady=5
            ).pack()
            
            steam_text = Text(info_dialog, wrap=WORD, height=3, font=("Consolas", 9))
            steam_text.pack(fill="x", padx=20, pady=10)
            steam_text.insert("1.0", steam_launch_option)
            steam_text.config(state="disabled")
            
            Label(
                info_dialog,
                text=self.translation_service.get(
                    "messages.export_bat_note",
                    "Note: The batch file contains all your current mod settings.\n"
                    "Re-export if you change mods or settings."
                ),
                wraplength=600,
                justify="left",
                pady=5,
                fg="gray"
            ).pack()
            
            Button(
                info_dialog,
                text=self.translation_service.get("messages.copy_to_clipboard", "Copy to Clipboard"),
                command=lambda: [
                    self.root.clipboard_clear(),
                    self.root.clipboard_append(steam_launch_option),
                    self.root.update()
                ],
                width=30,
                height=2
            ).pack(pady=5)
            
            Button(
                info_dialog,
                text=self.translation_service.get("messages.close", "Close"),
                command=info_dialog.destroy,
                width=30,
                height=2
            ).pack(pady=5)
            
        except Exception as e:
            messagebox.showerror(
                self.translation_service.get("messages.error", "Error"),
                f"Failed to export launch script:\n{str(e)}"
            )
    
    def _cleanup_dll_injection(self):
        """Clean up DLL manifest and chainloader configuration."""
        if not self.config.game_install_dir:
            messagebox.showwarning(
                self.translation_service.get("messages.warning", "Warning"),
                self.translation_service.get("messages.game_dir_not_set", "Game directory is not configured.")
            )
            return
        
        # Check if chainloader configuration exists
        if not self.dll_injection_service.is_chainloader_configured(self.config.game_install_dir):
            messagebox.showinfo(
                self.translation_service.get("messages.dll_cleanup_title", "DLL Cleanup"),
                self.translation_service.get(
                    "messages.dll_cleanup_nothing",
                    "No DLL manifest found in chainloader configuration."
                )
            )
            return
        
        # Confirm cleanup
        result = messagebox.askyesno(
            self.translation_service.get("messages.dll_cleanup_title", "DLL Cleanup"),
            self.translation_service.get(
                "messages.dll_cleanup_confirm",
                "This will clear the DLL manifest from chainloader configuration.\n\n"
                "Continue?"
            )
        )
        
        if not result:
            return
        
        # Perform cleanup
        try:
            self.dll_injection_service.clear_chainloader_manifest(self.config.game_install_dir, self.config.mod_folder)
            
            messagebox.showinfo(
                self.translation_service.get("messages.dll_cleanup_title", "DLL Cleanup"),
                self.translation_service.get(
                    "messages.dll_cleanup_success",
                    "DLL manifest has been cleared from chainloader configuration."
                )
            )
        except Exception as e:
            messagebox.showerror(
                self.translation_service.get("messages.error", "Error"),
                f"Error during DLL cleanup:\n{str(e)}"
            )
    
    def _auto_sort(self):
        """Auto-sort enabled mods alphabetically and by requirements."""
        if not self.mod_list.enabled_mods:
            messagebox.showinfo(
                self.translation_service.get("mod_list.auto_sort", "Auto-Sort"),
                self.translation_service.get("messages.no_mods_to_sort", "No mods are enabled to sort.")
            )
            return
        
        sorted_names, warnings = self.mod_service.auto_sort(self.mod_list)
        
        if sorted_names:
            self.mod_list.set_order(sorted_names)
            
            if warnings:
                warning_msg = "\n".join(warnings)
                messagebox.showwarning(
                    self.translation_service.get("mod_list.auto_sort", "Auto-Sort"),
                    self.translation_service.get("messages.auto_sort_warnings", "Mods sorted with warnings:\n\n{warnings}").format(warnings=warning_msg)
                )
            else:
                messagebox.showinfo(
                    self.translation_service.get("mod_list.auto_sort", "Auto-Sort"),
                    self.translation_service.get("messages.auto_sort_success", "Mods sorted successfully!")
                )
    
    def _unpack(self):
        output_dir = os.path.join(self.config.mod_folder, "_unpacked")
        os.makedirs(output_dir, exist_ok=True)
        
        pw = ProgressWindow(self.root, self.translation_service.get("progress.unpacking"), 100)
        
        try:
            def progress(current, total):
                pw.update(int((current / total) * 100))
            
            self.pack_service.unpack(self.config.game_install_dir, output_dir, progress)
            pw.close()
            messagebox.showinfo(
                self.translation_service.get("messages.success"),
                self.translation_service.get("messages.unpack_complete")
            )
        except Exception as e:
            pw.close()
            messagebox.showerror(
                self.translation_service.get("messages.error"),
                str(e)
            )
    
    def _repack(self):
        source_dir = os.path.join(self.config.mod_folder, "_unpacked")
        gpak_output = os.path.join(self.config.game_install_dir, "resources.gpak")
        
        pw = ProgressWindow(self.root, self.translation_service.get("progress.repacking"), 100)
        
        try:
            def progress(current, total):
                pw.update(int((current / total) * 100))
            
            self.pack_service.repack(source_dir, gpak_output, progress)
            pw.close()
            messagebox.showinfo(
                self.translation_service.get("messages.success"),
                self.translation_service.get("messages.repack_complete")
            )
        except Exception as e:
            pw.close()
            messagebox.showerror(
                self.translation_service.get("messages.error"),
                str(e)
            )
    
    def _import_modlist(self):
        with self.theme_service.file_dialog_safe_theme():
            filepath = filedialog.askopenfilename(
                parent=self.root,
                title=self.translation_service.get("messages.import_modlist", "Import Modlist"),
                filetypes=[
                    ("JSON files", "*.json"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )
        
        if not filepath:
            return
        
        try:
            if filepath.endswith(".json"):
                imported_names = self.modlist_io_service.import_modlist(filepath)
            else:
                imported_names = self.modlist_io_service.import_modlist_text(filepath)
            
            available_mod_names = {mod.name for mod in self.mod_list.all_mods}
            valid_names = [name for name in imported_names if name in available_mod_names]
            
            if len(valid_names) < len(imported_names):
                missing_count = len(imported_names) - len(valid_names)
                messagebox.showwarning(
                    "Warning",
                    f"Imported {len(valid_names)} mods successfully.\n{missing_count} mods were not found in your mods folder."
                )
            
            self.mod_list.set_order(valid_names)
            messagebox.showinfo("Success", f"Imported {len(valid_names)} mods!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import modlist: {str(e)}")
    
    def _export_modlist(self):
        with self.theme_service.file_dialog_safe_theme():
            filepath = filedialog.asksaveasfilename(
                parent=self.root,
                title=self.translation_service.get("messages.export_modlist", "Export Modlist"),
                defaultextension=".json",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )
        
        if not filepath:
            return
        
        try:
            enabled_names = self.mod_list.enabled_mod_names
            
            if filepath.endswith(".json"):
                default_name = os.path.splitext(os.path.basename(filepath))[0]
                modlist_name = simpledialog.askstring(
                    self.translation_service.get("messages.export_modlist", "Export Modlist"),
                    self.translation_service.get("messages.modlist_name_prompt", "Modlist name:"),
                    initialvalue=default_name,
                    parent=self.root
                )
                if modlist_name is None:
                    return

                self.modlist_io_service.export_modlist(enabled_names, filepath, modlist_name)
            else:
                self.modlist_io_service.export_modlist_text(enabled_names, filepath)
            
            messagebox.showinfo("Success", f"Exported {len(enabled_names)} mods!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export modlist: {str(e)}")
    
    def _show_settings(self):
        def on_save(new_config):
            self.config = new_config
            self.config_service.save_config(new_config)
            self.translation_service.load_language(new_config.language)
            self._reload_ui()
        
        SettingsWindow(self.root, self.config, self.translation_service, self.theme_service, on_save)

    def _show_info_dialog(self, title: str, message: str):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("500x220")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        theme_name = self.theme_service.normalize_theme_name(self.config.theme)
        colors = self.theme_service.get_color_scheme(theme_name)
        dialog.configure(bg=colors["bg"])
        self.theme_service.apply_titlebar(dialog, theme_name)

        container = ttk.Frame(dialog)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(container, text=title, font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(container, text=message, wraplength=460, justify="left").pack(anchor="w", pady=(0, 12))

        ttk.Button(container, text=self.translation_service.get("settings.confirm", "OK"), command=dialog.destroy).pack(anchor="e")
    
    def _show_dll_prompt_dialog(self, title: str, message: str, show_link: bool = True):
        """Show a custom yes/no dialog with optional clickable Mewjector link. Returns True if user clicks Yes."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("600x400" if show_link else "600x350")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        theme_name = self.theme_service.normalize_theme_name(self.config.theme)
        colors = self.theme_service.get_color_scheme(theme_name)
        dialog.configure(bg=colors["bg"])
        self.theme_service.apply_titlebar(dialog, theme_name)
        
        container = ttk.Frame(dialog)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        ttk.Label(container, text=title, font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 12))
        
        # Message
        ttk.Label(container, text=message, wraplength=560, justify="left").pack(anchor="w", pady=(0, 12))
        
        # Clickable link if requested
        if show_link:
            link_frame = ttk.Frame(container)
            link_frame.pack(anchor="w", pady=(0, 12))
            
            ttk.Label(
                link_frame,
                text=self.translation_service.get("messages.mewjector_link_text", "Get Mewjector here: "),
                font=("Arial", 10)
            ).pack(side="left")
            
            mewjector_url = "https://www.nexusmods.com/mewgenics/mods/218"
            link_color = "#5DADE2" if theme_name == "dark" else "#2E7DBE"
            link_label = tk.Label(
                link_frame,
                text=self.translation_service.get("messages.mewjector_url_display", "nexusmods.com/mewgenics/mods/218"),
                font=("Arial", 10, "underline"),
                fg=link_color,
                bg=colors["bg"],
                cursor="hand2"
            )
            link_label.pack(side="left")
            link_label.bind("<Button-1>", lambda e: webbrowser.open(mewjector_url))
        
        # Button frame
        button_frame = ttk.Frame(container)
        button_frame.pack(anchor="e", pady=(20, 0))
        
        result = {"value": False}
        
        def on_yes():
            result["value"] = True
            dialog.destroy()
        
        def on_no():
            result["value"] = False
            dialog.destroy()
        
        ttk.Button(button_frame, text=self.translation_service.get("dialog.no", "No"), command=on_no, width=10).pack(side="left", padx=5)
        ttk.Button(button_frame, text=self.translation_service.get("dialog.yes", "Yes"), command=on_yes, width=10).pack(side="left", padx=5)
        
        # Wait for dialog to close
        dialog.wait_window()
        
        return result["value"]
    
    def _change_language(self, language: str):
        self.config.language = language
        self.config_service.save_config(self.config)
        self.translation_service.load_language(language)
        self._reload_ui()
    
    def _change_theme(self, theme: str):
        try:
            normalized = self.theme_service.normalize_theme_name(theme)
            self.theme_service.set_theme(normalized)
            self.config.theme = normalized
            self.config_service.save_config(self.config)
            if self.window is not None:
                self.window.apply_theme(self.theme_service, normalized)
                self.window.menu_bar.update_theme_selection(normalized)
        except Exception as e:
            messagebox.showerror(
                self.translation_service.get("messages.error"),
                f"Failed to change theme: {str(e)}"
            )
    
    def _reload_ui(self):
        try:
            self.root.after_cancel(self._check_reload_id)
        except (AttributeError, ValueError):
            pass
        
        self.root.destroy()
        
        from app.infrastructure.mod_repository import ModRepository
        mod_repo = ModRepository(self.config.mod_folder)
        from app.core.services.mod_service import ModService
        new_mod_service = ModService(mod_repo)
        
        new_root = tk.Tk()
        self.theme_service.bind_root(new_root)
        self.theme_service.set_theme(self.config.theme)
        new_controller = MainController(
            new_root,
            self.config_service,
            new_mod_service,
            self.launcher_service,
            self.translation_service,
            self.pack_service,
            self.modlist_io_service,
            self.theme_service
        )
        new_controller.start()
    
    def _setup_auto_refresh(self):
        from app.infrastructure.mod_repository import ModRepository
        
        repo = ModRepository(self.config.mod_folder)
        self.last_mtime = repo.get_modlist_mtime()
        self.last_mod_folders = set(repo.get_mod_folders())
        
        self._check_reload_id = self.root.after(1000, self._check_reload)
    
    def _check_reload(self):
        from app.infrastructure.mod_repository import ModRepository
        
        repo = ModRepository(self.config.mod_folder)
        
        mtime = repo.get_modlist_mtime()
        if mtime != self.last_mtime:
            self.last_mtime = mtime
            self.mod_list = self.mod_service.load_mods()
            self.mod_list.add_observer(self._on_mod_list_changed)
            self.mod_service.validate_requirements(self.mod_list)
            self._refresh_lists()
        
        current_mod_folders = set(repo.get_mod_folders())
        if current_mod_folders != self.last_mod_folders:
            self.last_mod_folders = current_mod_folders
            self.mod_list = self.mod_service.load_mods()
            self.mod_list.add_observer(self._on_mod_list_changed)
            self.mod_service.validate_requirements(self.mod_list)
            self._refresh_lists()
        
        self._check_reload_id = self.root.after(1000, self._check_reload)
