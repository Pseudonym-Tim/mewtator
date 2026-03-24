# DLL Injection Proxy Loader

This directory should contain the proxy DLL loader (`version.dll`) used for DLL mod injection.

## What is the Proxy DLL Loader?

The proxy DLL loader is a special DLL that intercepts game initialization, loads mod DLLs in a specific order, and forwards calls to the original system DLL. This is the industry-standard approach used by popular mod loaders like:

- Ultimate ASI Loader
- ReShade
- Script Hook V
- Various game modding frameworks

## How It Works

1. The proxy DLL is named `version.dll` (or `dinput8.dll`, `d3d9.dll`, etc.)
2. It's placed in the game directory
3. When the game starts, it loads the proxy instead of the original system DLL
4. The proxy reads `mewtator_modlist_dlls.txt` to get the ordered list of mod DLLs
5. It loads each mod DLL in order using `LoadLibraryW()`
6. It loads the original `version.dll` from the Windows system directory
7. It forwards all function calls to the original DLL

## Options for Obtaining the Proxy DLL

### Option 1: Adapt Ultimate ASI Loader (Recommended)

Ultimate ASI Loader is an open-source proxy DLL loader:
- Repository: https://github.com/ThirteenAG/Ultimate-ASI-Loader
- License: MIT (permissive)
- Already supports loading DLLs in order from a configuration file

**To adapt it:**
1. Clone the Ultimate ASI Loader repository
2. Modify the configuration reading to use `mewtator_modlist_dlls.txt`
3. Compile the project (requires Visual Studio with C++ tools)
4. Copy the resulting `version.dll` to this directory

### Option 2: Use dinput8 Proxy Template

A simpler alternative proxy DLL template:
- Repository: https://github.com/elishacloud/dinput8-wrapper
- License: Public Domain
- Minimal proxy forwarding dinput8.dll calls

**To adapt it:**
1. Add DLL loading logic before forwarding calls
2. Read `mewtator_modlist_dlls.txt` on initialization
3. Call `LoadLibraryW()` for each DLL in order
4. Compile and place in this directory

### Option 3: Create Minimal Custom Loader

Create a minimal proxy DLL in C++:

```cpp
// version_proxy.cpp
#include <windows.h>
#include <string>
#include <fstream>
#include <vector>

HMODULE hOriginal = NULL;
std::vector<HMODULE> loadedMods;

// Read mod DLL list from file
std::vector<std::wstring> ReadModList() {
    std::vector<std::wstring> mods;
    std::wifstream file(L"mewtator_modlist_dlls.txt");
    std::wstring line;
    while (std::getline(file, line)) {
        if (!line.empty()) {
            mods.push_back(line);
        }
    }
    return mods;
}

// Load mod DLLs in order
void LoadModDLLs() {
    auto mods = ReadModList();
    for (const auto& mod : mods) {
        HMODULE hMod = LoadLibraryW(mod.c_str());
        if (hMod) {
            loadedMods.push_back(hMod);
        }
    }
}

// DLL entry point
BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        // Load the original version.dll from system directory
        wchar_t sysPath[MAX_PATH];
        GetSystemDirectoryW(sysPath, MAX_PATH);
        wcscat_s(sysPath, L"\\version.dll");
        hOriginal = LoadLibraryW(sysPath);
        
        // Load mod DLLs
        LoadModDLLs();
    }
    else if (reason == DLL_PROCESS_DETACH) {
        // Unload mod DLLs
        for (auto hMod : loadedMods) {
            FreeLibrary(hMod);
        }
        if (hOriginal) {
            FreeLibrary(hOriginal);
        }
    }
    return TRUE;
}

// Export version.dll functions
extern "C" {
    __declspec(dllexport) void GetFileVersionInfoA() {
        if (hOriginal) {
            auto func = (void(*)())GetProcAddress(hOriginal, "GetFileVersionInfoA");
            if (func) func();
        }
    }
    
    // Add all other version.dll exports here...
    // See: https://docs.microsoft.com/en-us/windows/win32/api/winver/
}
```

**To compile:**
```bash
cl /LD version_proxy.cpp /Fe:version.dll /link /DEF:version.def
```

**Required files:**
- `version_proxy.cpp` - The proxy implementation
- `version.def` - Export definitions for version.dll functions

### Option 4: Download Pre-Built Proxy (Easiest)

If available, download a pre-built proxy DLL from the Mewtator releases or mod community.

## File Requirements

### Proxy DLL Location
Place the compiled `version.dll` in this directory:
```
app/resources/version.dll
```

### Architecture Support
- For 64-bit games: Compile as 64-bit DLL
- For 32-bit games: Compile as 32-bit DLL
- Consider providing both versions if game architecture is unknown

### Testing the Proxy

1. Place `version.dll` in a test game directory
2. Create `mewtator_modlist_dlls.txt` with test DLL paths:
   ```
   mewtator_mods\testmod_test.dll
   mewtator_mods\anothermod_plugin.dll
   ```
3. Launch the game
4. Verify mod DLLs are loaded (use Process Explorer or similar)

## Security Considerations

- Only load DLLs from trusted sources
- The proxy runs with game process privileges
- Malicious DLLs can compromise the system
- Always verify DLL signatures when possible

## BAT File Export Integration

When exporting to `.bat` file with DLL injection enabled, Mewtator uses a CLI approach:

### How It Works

1. **Export Process:**
   - User exports `.bat` file (e.g., `launch_mewgenics_mods.bat`)
   - Mewtator creates a companion `*_dll_config.json` file with DLL mod configuration
   - If running from packaged `.exe`, Mewtator copies itself to the same directory

2. **BAT File Contents:**
   ```batch
   @echo off
   REM Setting up DLL mod injection
   echo Setting up DLL mods...
   "Mewtator.exe" --setup-dlls "launch_mewgenics_mods_dll_config.json"
   if %ERRORLEVEL% NEQ 0 (
       echo Warning: DLL setup failed
       pause
   )
   
   REM Launch game with mods
   start "" "C:\Game\Mewgenics.exe" -modpaths "mod1" "mod2"
   exit
   ```

3. **CLI Mode:**
   - `Mewtator.exe --setup-dlls <config.json>` runs without GUI
   - Reads DLL configuration from JSON file
   - Copies proxy DLL and mod DLLs to game directory
   - Creates `mewtator_modlist_dlls.txt` with load order
   - Returns exit code (0 = success, 1 = failure)

4. **No Python Required:**
   - Self-contained in the Mewtator executable
   - Works on any Windows system (or Proton on Linux)
   - User just runs the `.bat` file from Steam launch options

### Configuration File Format

The `*_dll_config.json` file contains:
```json
{
  "game_dir": "C:\\Path\\To\\Game",
  "dll_mods": [
    ["ModName1", ["C:\\mods\\ModName1\\mod.dll"]],
    ["ModName2", ["C:\\mods\\ModName2\\hook.dll", "C:\\mods\\ModName2\\plugin.dll"]]
  ]
}
```

### Steam Integration

Users paste this in Steam launch options:
```
"C:\Game\launch_mewgenics_mods.bat" %command%
```

Steam will:
1. Run the `.bat` file first (sets up DLL injection)
2. Replace `%command%` with the normal game launch
3. Game launches with mods pre-loaded

### Benefits

- **No dependencies:** Just Mewtator.exe (self-contained)
- **Portable:** Copy `.bat`, `.json`, and `Mewtator.exe` anywhere
- **Automatic:** User doesn't need to manually run Mewtator
- **Steam-friendly:** Works with Steam's launch option system
- **Cross-platform:** Works on Windows and Proton/Linux

## Troubleshooting

### Proxy not working
- Ensure `version.dll` is in the game directory
- Check game is not using another proxy (conflict)
- Verify DLL architecture matches game (32-bit vs 64-bit)
- Some games have anti-tamper that blocks DLL loading

### Mod DLLs not loading
- Check `mewtator_modlist_dlls.txt` exists and is readable
- Verify paths in modlist file are correct (relative to game directory)
- Ensure mod DLLs are valid Windows DLLs
- Check for missing dependencies (use Dependency Walker)

### Crashes on launch
- One or more mod DLLs may be incompatible
- Try loading mods one at a time to identify the problem
- Check Windows Event Viewer for crash details
- Verify all DLLs have correct export signatures

## Cross-Platform Notes

### Linux/Proton
The same proxy DLL works under Wine/Proton without modification:
- Wine translates Windows DLL loading to Linux shared libraries
- `LoadLibraryW()` works as expected in Wine
- DLL paths are automatically converted by Wine
- No platform-specific code needed in the proxy

### macOS
If using Wine/CrossOver on macOS, behavior is similar to Linux/Proton.

## License Considerations

When using or adapting existing proxy loaders:
- Check the original project's license
- Ultimate ASI Loader: MIT License (permissive, attribution required)
- Some proxies may be public domain
- Ensure compatibility with Mewtator's license

## Future Enhancements

Possible improvements to the proxy loader:
- Configuration file for proxy settings
- Logging of loaded DLLs
- Error reporting to user
- Version checking for mod compatibility
- DLL signature verification
- Hot-reloading support
- Multiple proxy DLL options (version.dll, dinput8.dll, etc.)

## Resources

- [Ultimate ASI Loader GitHub](https://github.com/ThirteenAG/Ultimate-ASI-Loader)
- [dinput8 Wrapper Template](https://github.com/elishacloud/dinput8-wrapper)
- [Windows DLL Best Practices](https://docs.microsoft.com/en-us/windows/win32/dlls/dynamic-link-libraries)
- [Wine DLL Loading](https://wiki.winehq.org/Wine_Developer%27s_Guide/Architecture_Overview)
