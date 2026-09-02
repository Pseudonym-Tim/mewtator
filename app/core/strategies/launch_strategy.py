from abc import ABC, abstractmethod
from typing import List
import os
import subprocess
from pathlib import Path
import shlex
from app.core.models.config import Config
from app.utils.logging_utils import get_logger
from app.utils.resource_utils import resource_path
from app.core.services.translation_service import TranslationService

MEWGENICS_STEAM_APP_ID = "686060"

def _steam_game_env():
    """Return child-process environment identifying Mewgenics to Steamworks!"""
    env = os.environ.copy()
    env["SteamAppId"] = MEWGENICS_STEAM_APP_ID
    env["SteamGameId"] = MEWGENICS_STEAM_APP_ID
    return env


class LaunchStrategy(ABC):
    @abstractmethod
    def launch(self, executable_path: str, mod_paths: List[str], game_dir: str, config: Config, extra_args: List[str], translation_service: TranslationService):
        pass
    
    @abstractmethod
    def get_launch_options(self, mod_paths: List[str], game_dir: str, config: Config, extra_args: List[str]) -> str:
        pass


class DirectLaunchStrategy(LaunchStrategy):
    def launch(self, executable_path: str, mod_paths: List[str], game_dir: str, config: Config, extra_args: List[str], translation_service: TranslationService):
        args = [executable_path]
        
        if extra_args:
            args.extend(extra_args)
        
        if mod_paths:
            args.append("-modpaths")
            args.extend(mod_paths)
        
        subprocess.Popen(args, cwd=game_dir, env=_steam_game_env())
    
    def get_launch_options(self, mod_paths: List[str], game_dir: str, config: Config, extra_args: List[str]) -> str:
        parts = []
        
        if extra_args:
            parts.extend(extra_args)
        
        if mod_paths:
            parts.append("-modpaths")
            parts.extend(f'"{p}"' for p in mod_paths)
        
        return " ".join(parts)


class ProtonLaunchStrategy(LaunchStrategy):
    def __init__(self, game_dir: str):
        self.game_dir = game_dir

    def launch(self, executable_path: str, mod_paths: List[str], game_dir: str, config: Config, extra_args: List[str], translation_service: TranslationService):
        # Launch Mewgenics.exe directly rather than through the Steam client...
        env = _steam_game_env()

        path_steam_client_root = Path.home() / '.steam/root'
        path_steam_gameoverlayrenderer64 = path_steam_client_root / 'ubuntu12_64/gameoverlayrenderer.so'

        path_game_dir = Path(game_dir)
        path_mod_folder = Path(config.mod_folder)
        path_steam_linux_runtime = Path(config.linux_steam_runtime_path) if config.linux_steam_runtime_path else None
        path_proton = Path(config.linux_proton_path) if config.linux_proton_path else None
        path_bundled_mods_dir = Path(resource_path("bundled_mods"))

        path_library_game = path_game_dir.parent.parent
        path_library_steam_linux_runtime = Path(config.linux_steam_runtime_path).parent.parent.parent if path_steam_linux_runtime else None
        path_library_proton = Path(config.linux_proton_path).parent.parent.parent if path_proton else None

        path_compat_data = (
            Path(config.linux_compatdata_override_dir)
            if config.linux_compatdata_override_dir
            else path_library_game / 'compatdata' / MEWGENICS_STEAM_APP_ID
        )

        mod_folder_in_game_dir = path_mod_folder.resolve().is_relative_to(path_game_dir.resolve())
        bundled_mods_dir_in_game_dir = path_bundled_mods_dir.resolve().is_relative_to(path_game_dir.resolve())

        steam_gameoverlayrenderer64_exists = path_steam_gameoverlayrenderer64.is_file()
        steam_linux_runtime_exists = path_steam_linux_runtime is not None and path_steam_linux_runtime.is_file()
        proton_exists = path_proton is not None and path_proton.is_file()
        path_compat_data_exists = path_compat_data.is_dir()

        if not config.linux_allow_undefined_steam_runtime_or_proton:
            missing_launchers = []
            if not steam_linux_runtime_exists:
                missing_launchers.append("Steam Linux Runtime")
            if not proton_exists:
                missing_launchers.append("Proton")
            if missing_launchers:
                required = "\n".join(
                    translation_service.get("messages.path_required").format(name=name)
                    for name in missing_launchers
                )
                raise RuntimeError(required)

        # We avoid blindly initializing Steam-managed compatdata (by making a directory that does not
        # already exist under steamapps/compatdata), because we'd potentially bypass first-time Steam Cloud
        # sync performed by the Steam client. Doing so could overwrite existing save data stored on the Steam Cloud.
        if not path_compat_data_exists:
            raise RuntimeError(
                translation_service.get("messages.proton_missing_compatdata_error") + 
                "\n\n" +
                translation_service.get("messages.copy_launch_options_advice")
            )

        # Steam Linux Runtime/Proton logging controls
        # env['PRESSURE_VESSEL_LOG_INFO'] = '1' # writes to stdout
        # env['PROTON_LOG'] = '1' # writes to ~/steam-686060.log

        # inject the library that enables Steam overlay functionality
        # https://partner.steamgames.com/doc/store/application/platforms/linux#FAQ
        if not config.linux_steam_gameoverlayrenderer_disabled and steam_gameoverlayrenderer64_exists:
            if 'LD_PRELOAD' not in env:
                env['LD_PRELOAD'] = ''
            env['LD_PRELOAD'] += ':' + str(path_steam_gameoverlayrenderer64.resolve())

        # prescribed Steam Linux Runtime/Proton configuration variables
        # https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/slr-for-game-developers.md#running-a-game-under-proton-in-the-steam-linux-runtime-environment
        env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = path_steam_client_root.resolve()
        env['STEAM_COMPAT_DATA_PATH'] = path_compat_data.resolve()
        env['STEAM_COMPAT_INSTALL_PATH'] = path_game_dir.resolve()
        env['STEAM_COMPAT_LIBRARY_PATHS'] = ':'.join(list(dict.fromkeys(str(x.resolve()) for x in [
            path_library_game,
            path_library_steam_linux_runtime,
            path_library_proton
        ] if x is not None)))

        # expose the mod directory under Z:\, in case it was not placed within Mewgenics' directory
        # https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/slr-for-game-developers.md#making-more-files-available-in-the-container
        env['STEAM_COMPAT_MOUNTS'] = ':'.join(list(dict.fromkeys(str(x.resolve()) for x in [
            path_mod_folder if not mod_folder_in_game_dir else None,
            path_bundled_mods_dir if not bundled_mods_dir_in_game_dir else None
        ] if x is not None)))

        # set WINEDLLOVERRIDES to enable loading Mewjector, which shadows version.dll
        if config.dll_injection_enabled:
            env['WINEDLLOVERRIDES'] = 'version=n,b'

        args = []
        # Steam Linux Runtime is not necessarily required if the user's system has the right
        # libraries to support the chosen Proton version.
        if steam_linux_runtime_exists:
            args.extend([config.linux_steam_runtime_path, '--'])

        # There probably isn't a good reason to launch without Proton, but if so, the system
        # will try to dispatch the exe file via binfmt, possibly using a native Wine installation.
        if proton_exists:
            args.extend([config.linux_proton_path, 'run'])

        args.append(executable_path)

        if extra_args:
            args.extend(extra_args)

        if mod_paths:
            args.append("-modpaths")
            args.extend(mod_paths)

        subprocess.Popen(args, cwd=game_dir, env=env)

    def get_launch_options(self, mod_paths: List[str], game_dir: str, config: Config, extra_args: List[str]) -> str:
        parts = []

        parts_has_prefix = False

        path_game_dir = Path(game_dir)
        path_mod_folder = Path(config.mod_folder)
        path_bundled_mods_dir = Path(resource_path("bundled_mods"))
        mod_folder_in_game_dir = path_mod_folder.resolve().is_relative_to(path_game_dir.resolve())
        bundled_mods_dir_in_game_dir = path_bundled_mods_dir.resolve().is_relative_to(path_game_dir.resolve())

        # expose the mod directory under Z:\, in case it was not placed within Mewgenics' directory
        # https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/slr-for-game-developers.md#making-more-files-available-in-the-container
        compat_mounts = ':'.join(list(dict.fromkeys(str(x.resolve()) for x in [
            path_mod_folder if not mod_folder_in_game_dir else None,
            path_bundled_mods_dir if not bundled_mods_dir_in_game_dir else None
        ] if x is not None)))
        if compat_mounts:
            parts.append(f'STEAM_COMPAT_MOUNTS={shlex.quote(compat_mounts)}')
            parts_has_prefix = True

        # set WINEDLLOVERRIDES to enable loading Mewjector, which shadows version.dll
        if config.dll_injection_enabled:
            parts.append(f'WINEDLLOVERRIDES=version=n,b')
            parts_has_prefix = True

        if parts_has_prefix:
            parts.append('%command%')

        if extra_args:
            parts.extend(extra_args)

        if mod_paths:
            parts.append("-modpaths")
            parts.extend(shlex.quote(str(p)) for p in mod_paths)

        return " ".join(parts)


class LaunchStrategyFactory:
    @staticmethod
    def create(game_dir: str) -> LaunchStrategy:
        from app.core.strategies.path_strategy import PathStrategyFactory, ProtonPathStrategy
        
        path_strategy = PathStrategyFactory.create(game_dir)
        
        if isinstance(path_strategy, ProtonPathStrategy):
            return ProtonLaunchStrategy(game_dir)
        
        return DirectLaunchStrategy()
