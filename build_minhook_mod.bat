@echo off
REM Build script for MinHook mod DLL
REM 
REM Prerequisites:
REM 1. Visual Studio installed (for cl.exe compiler)
REM 2. MinHook library downloaded from https://github.com/TsudaKageyu/minhook
REM 3. Update MINHOOK_PATH below to point to your MinHook directory

REM ===== CONFIGURATION =====
set MINHOOK_PATH=C:\path\to\minhook
REM =========================

echo === Building Mewgenics MinHook Mod ===
echo.

REM Check if Visual Studio is in PATH
where cl.exe >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] cl.exe not found! Run this from a Visual Studio Developer Command Prompt.
    echo.
    echo Open "x64 Native Tools Command Prompt for VS 2022" and run this script from there.
    pause
    exit /b 1
)

REM Check if MinHook path exists
if not exist "%MINHOOK_PATH%" (
    echo [ERROR] MinHook not found at: %MINHOOK_PATH%
    echo.
    echo Download MinHook from: https://github.com/TsudaKageyu/minhook/releases
    echo Extract it and update MINHOOK_PATH in this script.
    pause
    exit /b 1
)

echo [1/3] Compiling...
cl.exe /LD /O2 /MT ^
    /I"%MINHOOK_PATH%\include" ^
    minhook_mod.cpp ^
    /link "%MINHOOK_PATH%\lib\libMinHook.x64.lib" ^
    /OUT:mewgenics_mod.dll

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Compilation failed!
    pause
    exit /b 1
)

echo.
echo [2/3] Cleaning up build files...
del minhook_mod.obj minhook_mod.exp minhook_mod.lib >nul 2>&1

echo.
echo [3/3] Build complete!
echo.
echo Output: mewgenics_mod.dll
echo.
echo === Next Steps ===
echo 1. Inject mewgenics_mod.dll into Mewgenics.exe
echo 2. Use the Python injector: python inject_dll.py
echo.

pause
