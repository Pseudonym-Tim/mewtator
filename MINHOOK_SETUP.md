# MinHook Memory Mod Setup Guide

This is a cleaner alternative to direct memory editing - it uses MinHook to monitor and control values through DLL injection.

## Advantages over Direct Memory Editing
- ✓ More reliable - works even when pointers change
- ✓ Can freeze values in real-time
- ✓ Cleaner code architecture
- ✓ Can hook function calls for advanced mods

## Prerequisites

### 1. Download MinHook
```
https://github.com/TsudaKageyu/minhook/releases
```
Download the latest release (e.g., `MinHook_1_3_3.zip`) and extract it.

### 2. Install Visual Studio
You need Visual Studio with C++ support:
- Download Visual Studio 2022 Community (free)
- During installation, select "Desktop development with C++"

## Building the Mod

### Step 1: Configure MinHook Path
Edit `build_minhook_mod.bat` and update this line:
```batch
set MINHOOK_PATH=C:\path\to\minhook
```
Point it to where you extracted MinHook (should contain `include/` and `lib/` folders).

### Step 2: Configure the Mod
Edit `minhook_mod.cpp` to customize behavior:

```cpp
#define TARGET_VALUE 999      // The value you want
#define FREEZE_VALUE true     // true = constantly maintain value
                              // false = set once and stop
```

### Step 3: Build
1. Open **"x64 Native Tools Command Prompt for VS 2022"** (search in Start menu)
2. Navigate to the mewtator folder:
   ```
   cd F:\src\mewtator
   ```
3. Run the build script:
   ```
   build_minhook_mod.bat
   ```

This will create `mewgenics_mod.dll`.

## Using the Mod

### Step 1: Start the Game
Make sure Mewgenics.exe is running.

### Step 2: Inject the DLL
Run as Administrator (right-click → Run as administrator):
```
python inject_dll.py
```

### Step 3: Verify
- A console window should appear in the game showing mod status
- The console will display if the pattern was found
- If `FREEZE_VALUE` is true, the value will be constantly maintained

## Configuration Options

### Target Different Values
If you want to modify different memory addresses:

1. Find the instruction in Cheat Engine (right-click address → "Find out what accesses this")
2. Copy the instruction bytes
3. Update the pattern in `minhook_mod.cpp`:
```cpp
const BYTE pattern[] = { 0x48, 0x8B, 0x05, ... }; // Your bytes here
const char mask[] = "xxx????xxx";  // x = exact match, ? = wildcard
```

## Troubleshooting

### "Pattern not found"
- The game updated and code changed
- Get new instruction bytes from Cheat Engine
- Update the pattern in `minhook_mod.cpp` and rebuild

### "Failed to initialize MinHook"
- Another mod or anti-cheat is interfering
- Try injecting the DLL earlier in the game startup

### "Access Denied" when injecting
- Run `inject_dll.py` as Administrator
- Some anti-virus software blocks DLL injection

### Console doesn't appear
- The DLL might not be injecting properly
- Check if the DLL exists: `dir mewgenics_mod.dll`
- Try running the game as Administrator

## Advanced Usage

### Hook Function Calls
Instead of monitoring memory, you can hook entire functions:

```cpp
typedef int(__fastcall* OriginalFunction)(void* thisPtr, int arg);
OriginalFunction g_Original = nullptr;

int HookedFunction(void* thisPtr, int arg) {
    // Modify behavior
    int result = g_Original(thisPtr, arg);
    result = 999; // Override return value
    return result;
}

// In DllMain:
MH_CreateHook(targetFunction, &HookedFunction, (void**)&g_Original);
MH_EnableHook(targetFunction);
```

### Multiple Values
You can monitor multiple memory locations by creating multiple monitor threads or expanding the pattern matching.

## Comparison: Direct Memory vs MinHook

| Feature | memory_editor.py | MinHook Mod |
|---------|-----------------|-------------|
| Setup Complexity | Simple | Moderate |
| Pattern Scanning | ✓ | ✓ |
| Value Freezing | Manual loop | Built-in |
| Function Hooking | ✗ | ✓ |
| Code Modification | ✗ | ✓ |
| Reliability | Good | Excellent |
| Requires Compilation | ✗ | ✓ |

## Next Steps

- Learn x64 assembly to create more advanced hooks
- Hook game functions instead of just monitoring values
- Create a configuration file to load settings without recompiling
- Build a menu system using ImGui for in-game controls
