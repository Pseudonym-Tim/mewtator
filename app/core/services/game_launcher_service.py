import os
import shlex
import sys
import json
from typing import List
from app.core.strategies.platform_strategy import PlatformFactory
from app.core.strategies.launch_strategy import LaunchStrategyFactory
from app.core.strategies.path_strategy import PathStrategyFactory
from app.core.services.dll_injection_service import DllInjectionService
from app.utils.logging_utils import get_logger


class GameLauncherService:
    def __init__(self, dll_injection_service: DllInjectionService = None):
        self.platform = PlatformFactory.create()
        self.dll_injection_service = dll_injection_service or DllInjectionService()
    
    def find_executable(self, game_dir: str) -> str:
        exe_names = self.platform.get_executable_names()
        
        for name in exe_names:
            exe_path = os.path.join(game_dir, name)
            if os.path.isfile(exe_path):
                return exe_path
        
        return os.path.join(game_dir, exe_names[0])
    
    def _build_extra_args(self, config, mod_list) -> List[str]:
        """Build extra launch arguments from config and mod list."""
        extra_args = []
        
        if not config:
            return extra_args
        
        if config.custom_launch_options:
            try:
                custom_args = shlex.split(config.custom_launch_options)
                extra_args.extend(custom_args)
            except ValueError:
                extra_args.extend(config.custom_launch_options.split())
        
        if config.dev_mode_enabled:
            extra_args.extend(["-dev_mode", "true"])
        
        if config.debug_console_enabled:
            extra_args.extend(["-enable_debugconsole", "true"])
        
        # TEMPORARILY DISABLED: These features are not yet functional in the game
        # savefile_suffix = config.savefile_suffix_override
        # if not savefile_suffix and mod_list:
        #     enabled_mods = mod_list.enabled_mods
        #     mod_iter = enabled_mods if config.use_original_load_order else reversed(enabled_mods)
        #     for mod in mod_iter:
        #         if mod.savefile_suffix:
        #             savefile_suffix = mod.savefile_suffix
        #             break
        # if savefile_suffix:
        #     extra_args.extend(["-savesuffix", savefile_suffix])
        # 
        # inherit_save = config.inherit_save_override
        # if not inherit_save and mod_list:
        #     enabled_mods = mod_list.enabled_mods
        #     mod_iter = enabled_mods if config.use_original_load_order else reversed(enabled_mods)
        #     for mod in mod_iter:
        #         if mod.inherit_save:
        #             inherit_save = mod.inherit_save
        #             break
        # if inherit_save:
        #     extra_args.extend(["-inheritsave", inherit_save])
        
        return extra_args
    
    def _apply_load_order(self, mod_paths: List[str], config) -> List[str]:
        """Apply load order logic to mod paths."""
        if config and config.use_original_load_order:
            return mod_paths
        else:
            return list(reversed(mod_paths))
    
    def launch_game(self, game_dir: str, mod_paths: List[str], config=None, mod_list=None):
        exe_path = self.find_executable(game_dir)
        
        if not os.path.isfile(exe_path):
            raise FileNotFoundError(f"Game executable not found: {exe_path}")
        
        # Handle DLL injection if enabled
        dll_setup_successful = False
        if config and config.dll_injection_enabled and mod_list:
            dll_mods = self.dll_injection_service.scan_for_dll_mods(mod_list)
            if dll_mods:
                logger = get_logger()
                logger.info("Setting up DLL injection for %d mod(s)", len(dll_mods))
                dll_setup_successful = self.dll_injection_service.setup_dll_injection(game_dir, dll_mods)
                if dll_setup_successful:
                    logger.info("DLL injection setup successful")
                else:
                    logger.warning("DLL injection setup failed")
        
        launch_strategy = LaunchStrategyFactory.create(game_dir)
        path_strategy = PathStrategyFactory.create(game_dir)
        
        extra_args = self._build_extra_args(config, mod_list)
        final_paths = self._apply_load_order(mod_paths, config)
        converted_paths = path_strategy.convert_mod_paths(final_paths, game_dir)
        
        logger = get_logger()
        logger.info("Launch executable: %s", exe_path)
        for arg in extra_args:
            logger.info("Launch extra arg: %s", arg)
        for path in converted_paths:
            logger.info("Launch mod path: %s", path)
        
        launch_strategy.launch(exe_path, converted_paths, game_dir, extra_args)
    
    def get_launch_options(self, game_dir: str, mod_paths: List[str], config=None, mod_list=None) -> str:
        launch_strategy = LaunchStrategyFactory.create(game_dir)
        path_strategy = PathStrategyFactory.create(game_dir)
        
        extra_args = self._build_extra_args(config, mod_list)
        final_paths = self._apply_load_order(mod_paths, config)
        converted_paths = path_strategy.convert_mod_paths(final_paths, game_dir)
        
        return launch_strategy.get_launch_options(converted_paths, extra_args)
    
    def export_bat_file(self, game_dir: str, mod_paths: List[str], output_path: str, config=None, mod_list=None) -> str:
        """
        Export launch options to a .bat file.
        
        Args:
            game_dir: Game installation directory
            mod_paths: List of mod paths
            output_path: Path where to save the .bat file
            config: Config object with launch options
            mod_list: ModList object
            
        Returns:
            Steam launch option string to use with the .bat file
        """
        exe_path = self.find_executable(game_dir)
        path_strategy = PathStrategyFactory.create(game_dir)
        
        extra_args = self._build_extra_args(config, mod_list)
        final_paths = self._apply_load_order(mod_paths, config)
        converted_paths = path_strategy.convert_mod_paths(final_paths, game_dir)
        
        bat_content = "@echo off\n"
        bat_content += "REM Mewtator Auto-Generated Launch Script\n"
        bat_content += "REM This script launches Mewgenics with mods\n\n"
        
        # Add DLL injection setup if enabled
        dll_config_file = None
        if config and config.dll_injection_enabled and mod_list:
            dll_mods = self.dll_injection_service.scan_for_dll_mods(mod_list)
            if dll_mods:
                bat_content += "REM Setting up DLL mod injection\n"
                bat_content += "echo Setting up DLL mods...\n"
                
                # Save DLL configuration to companion JSON file
                dll_config_file = output_path.replace('.bat', '_dll_config.json')
                dll_config = {
                    "game_dir": game_dir,
                    "dll_mods": dll_mods
                }
                with open(dll_config_file, 'w', encoding='utf-8') as f:
                    json.dump(dll_config, f, indent=2)
                
                # Get path to Mewtator.exe (same directory as output .bat)
                mewtator_exe = os.path.join(os.path.dirname(output_path), "Mewtator.exe")
                if not os.path.exists(mewtator_exe):
                    # Try to use the current executable path
                    mewtator_exe = sys.executable
                    if not mewtator_exe.endswith(".exe"):
                        # Development mode - look for Mewtator.exe in parent directory
                        mewtator_exe = "Mewtator.exe"
                
                dll_config_basename = os.path.basename(dll_config_file)
                
                # Call Mewtator.exe with --setup-dlls flag
                bat_content += f'"{mewtator_exe}" --setup-dlls "%~dp0{dll_config_basename}"\n'
                bat_content += "if %ERRORLEVEL% NEQ 0 (\n"
                bat_content += "    echo Warning: DLL setup failed\n"
                bat_content += "    pause\n"
                bat_content += ")\n\n"
        
        cmd_parts = [f'start "" "{exe_path}"']
        cmd_parts.extend(f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in extra_args)
        
        if converted_paths:
            cmd_parts.append("-modpaths")
            cmd_parts.extend(f'"{path}"' for path in converted_paths)
        
        bat_content += " ".join(cmd_parts) + "\n"
        bat_content += "exit\n"
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        
        return f'"{output_path}" %command%'
    
    def should_warn_external_mods(self, game_dir: str, mod_paths: List[str]) -> bool:
        path_strategy = PathStrategyFactory.create(game_dir)
        return path_strategy.should_warn_about_external_mods(mod_paths, game_dir)
