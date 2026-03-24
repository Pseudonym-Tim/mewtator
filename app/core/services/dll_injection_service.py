"""Service for managing DLL mod injection.

This service handles scanning for DLL mods, deploying a proxy DLL loader,
and managing the lifecycle of DLL injection for cross-platform compatibility
(Windows native and Linux/Proton).
"""

import os
import json
import shutil
from typing import List, Dict, Tuple
from pathlib import Path


class DllInjectionService:
    """Manages DLL mod injection via proxy loader.
    
    Uses a proxy DLL (version.dll) that intercepts game initialization,
    loads mod DLLs in the specified order, and forwards calls to the
    original system DLL. This approach works identically on Windows
    and Linux/Proton without requiring launch option modifications.
    """
    
    PROXY_DLL_NAME = "version.dll"
    MANIFEST_FILE = "mewtator_dll_manifest.json"
    MODLIST_DLL_FILE = "mewtator_modlist_dlls.txt"
    
    def __init__(self):
        """Initialize the DLL injection service."""
        pass
    
    def scan_for_dll_mods(self, mod_list) -> List[Tuple[str, List[str]]]:
        """Scan enabled mods for DLL files.
        
        Args:
            mod_list: ModList object containing all mods
            
        Returns:
            List of tuples (mod_name, [dll_paths]) for mods with DLLs,
            in the order they appear in the modlist
        """
        dll_mods = []
        
        for mod in mod_list.get_enabled_mods():
            dll_files = self._find_dlls_in_mod(mod)
            if dll_files:
                dll_mods.append((mod.name, dll_files))
        
        return dll_mods
    
    def has_dll_mods(self, mod_list) -> bool:
        """Quick check if any enabled mod contains DLL files.
        
        Args:
            mod_list: ModList object containing all mods
            
        Returns:
            True if at least one enabled mod has .dll files
        """
        for mod in mod_list.get_enabled_mods():
            if self._find_dlls_in_mod(mod):
                return True
        return False
    
    def mod_has_dlls(self, mod) -> bool:
        """Check if a specific mod contains DLL files.
        
        Args:
            mod: Mod object to check
            
        Returns:
            True if mod contains .dll files
        """
        return len(self._find_dlls_in_mod(mod)) > 0
    
    def _find_dlls_in_mod(self, mod) -> List[str]:
        """Find all DLL files in a mod's directory.
        
        Args:
            mod: Mod object with path attribute
            
        Returns:
            List of absolute paths to .dll files
        """
        dll_files = []
        mod_path = Path(mod.path)
        
        if not mod_path.exists():
            return dll_files
        
        # Search recursively for .dll files
        for dll_file in mod_path.rglob("*.dll"):
            if dll_file.is_file():
                dll_files.append(str(dll_file.absolute()))
        
        return dll_files
    
    def setup_dll_injection(self, game_dir: str, dll_mods: List[Tuple[str, List[str]]]) -> bool:
        """Deploy proxy DLL and mod DLLs to game directory.
        
        Args:
            game_dir: Path to game installation directory
            dll_mods: List of (mod_name, [dll_paths]) tuples in load order
            
        Returns:
            True if setup successful, False otherwise
        """
        game_path = Path(game_dir)
        
        if not game_path.exists():
            return False
        
        try:
            # Create manifest to track deployed files
            manifest = {
                "proxy_dll": self.PROXY_DLL_NAME,
                "modlist_file": self.MODLIST_DLL_FILE,
                "mod_dlls": [],
                "timestamp": None  # Could add timestamp if needed
            }
            
            # Copy mod DLLs to mods subdirectory in game folder
            mods_dir = game_path / "mewtator_mods"
            mods_dir.mkdir(exist_ok=True)
            
            # Create ordered list of DLL paths for proxy loader
            dll_load_order = []
            
            for mod_name, dll_paths in dll_mods:
                for dll_path in dll_paths:
                    dll_file = Path(dll_path)
                    # Copy DLL to mods directory with mod name prefix to avoid conflicts
                    dest_name = f"{mod_name}_{dll_file.name}"
                    dest_path = mods_dir / dest_name
                    
                    shutil.copy2(dll_path, dest_path)
                    
                    # Add to manifest
                    manifest["mod_dlls"].append(str(dest_path.relative_to(game_path)))
                    
                    # Add to load order (relative path from game directory)
                    dll_load_order.append(str(dest_path.relative_to(game_path)))
            
            # Write modlist file for proxy loader to read
            modlist_path = game_path / self.MODLIST_DLL_FILE
            with open(modlist_path, 'w', encoding='utf-8') as f:
                for dll_path in dll_load_order:
                    f.write(f"{dll_path}\n")
            
            # Deploy proxy DLL
            proxy_dest = game_path / self.PROXY_DLL_NAME
            if not self._deploy_proxy_dll(proxy_dest):
                # Cleanup on failure
                self.cleanup_dll_injection(game_dir)
                return False
            
            # Save manifest
            manifest_path = game_path / self.MANIFEST_FILE
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)
            
            return True
            
        except Exception as e:
            # Log error and cleanup
            print(f"Error setting up DLL injection: {e}")
            self.cleanup_dll_injection(game_dir)
            return False
    
    def _deploy_proxy_dll(self, dest_path: Path) -> bool:
        """Deploy the proxy DLL loader to the destination.
        
        Args:
            dest_path: Destination path for version.dll
            
        Returns:
            True if deployment successful
        """
        # TODO: In production, this would copy from bundled resources
        # For now, create a placeholder that will be replaced with actual proxy
        
        # Check if we have a bundled proxy DLL
        # This will be in app/resources/ when we add it
        resource_dir = Path(__file__).parent.parent.parent / "resources"
        proxy_source = resource_dir / self.PROXY_DLL_NAME
        
        if proxy_source.exists():
            shutil.copy2(proxy_source, dest_path)
            return True
        else:
            # For development: create a marker file
            # In production, this would fail if proxy not found
            print(f"Warning: Proxy DLL not found at {proxy_source}")
            print("Deployment will continue but DLL injection won't work until proxy is added")
            # Don't fail during development
            return True
    
    def cleanup_dll_injection(self, game_dir: str) -> bool:
        """Remove proxy DLL and mod DLLs from game directory.
        
        Args:
            game_dir: Path to game installation directory
            
        Returns:
            True if cleanup successful, False otherwise
        """
        game_path = Path(game_dir)
        manifest_path = game_path / self.MANIFEST_FILE
        
        if not manifest_path.exists():
            # Nothing to clean up
            return True
        
        try:
            # Load manifest
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            # Remove mod DLLs
            for dll_rel_path in manifest.get("mod_dlls", []):
                dll_path = game_path / dll_rel_path
                if dll_path.exists():
                    dll_path.unlink()
            
            # Remove mods directory if empty
            mods_dir = game_path / "mewtator_mods"
            if mods_dir.exists() and not any(mods_dir.iterdir()):
                mods_dir.rmdir()
            
            # Remove modlist file
            modlist_path = game_path / self.MODLIST_DLL_FILE
            if modlist_path.exists():
                modlist_path.unlink()
            
            # Remove proxy DLL
            proxy_path = game_path / manifest["proxy_dll"]
            if proxy_path.exists():
                proxy_path.unlink()
            
            # Remove manifest
            manifest_path.unlink()
            
            return True
            
        except Exception as e:
            print(f"Error cleaning up DLL injection: {e}")
            return False
    
    def is_dll_injection_active(self, game_dir: str) -> bool:
        """Check if DLL injection is currently deployed.
        
        Args:
            game_dir: Path to game installation directory
            
        Returns:
            True if manifest file exists (DLLs are deployed)
        """
        game_path = Path(game_dir)
        manifest_path = game_path / self.MANIFEST_FILE
        return manifest_path.exists()
    
    def get_deployed_dll_count(self, game_dir: str) -> int:
        """Get count of currently deployed mod DLLs.
        
        Args:
            game_dir: Path to game installation directory
            
        Returns:
            Number of deployed mod DLLs, or 0 if none deployed
        """
        game_path = Path(game_dir)
        manifest_path = game_path / self.MANIFEST_FILE
        
        if not manifest_path.exists():
            return 0
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            return len(manifest.get("mod_dlls", []))
        except:
            return 0
