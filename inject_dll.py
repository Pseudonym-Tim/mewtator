"""
DLL Injector for Mewgenics mod

Injects mewgenics_mod.dll into the running Mewgenics.exe process.
"""

import ctypes
import ctypes.wintypes as wintypes
import os
import sys


# Windows API constants
PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04
TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260)
    ]


def find_process(process_name):
    """Find process ID by name."""
    snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return None
        
    process_entry = PROCESSENTRY32()
    process_entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    
    if ctypes.windll.kernel32.Process32First(snapshot, ctypes.byref(process_entry)):
        while True:
            if process_entry.szExeFile.decode('utf-8', errors='ignore').lower() == process_name.lower():
                pid = process_entry.th32ProcessID
                ctypes.windll.kernel32.CloseHandle(snapshot)
                return pid
                
            if not ctypes.windll.kernel32.Process32Next(snapshot, ctypes.byref(process_entry)):
                break
                
    ctypes.windll.kernel32.CloseHandle(snapshot)
    return None


def inject_dll(process_id, dll_path):
    """Inject a DLL into a process.
    
    Args:
        process_id: Target process ID
        dll_path: Full path to the DLL to inject
        
    Returns:
        True if successful, False otherwise
    """
    # Open the process
    process_handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_ALL_ACCESS, False, process_id
    )
    
    if not process_handle:
        print(f"Failed to open process {process_id}")
        return False
        
    try:
        # Allocate memory in the target process for the DLL path
        dll_path_bytes = dll_path.encode('utf-8') + b'\x00'
        path_len = len(dll_path_bytes)
        
        remote_memory = ctypes.windll.kernel32.VirtualAllocEx(
            process_handle,
            None,
            path_len,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_READWRITE
        )
        
        if not remote_memory:
            print("Failed to allocate memory in target process")
            return False
            
        # Write the DLL path to the allocated memory
        bytes_written = ctypes.c_size_t()
        success = ctypes.windll.kernel32.WriteProcessMemory(
            process_handle,
            remote_memory,
            dll_path_bytes,
            path_len,
            ctypes.byref(bytes_written)
        )
        
        if not success:
            print("Failed to write DLL path to target process")
            ctypes.windll.kernel32.VirtualFreeEx(process_handle, remote_memory, 0, 0x8000)
            return False
            
        # Get the address of LoadLibraryA
        kernel32 = ctypes.windll.kernel32
        load_library_addr = kernel32.GetProcAddress(
            kernel32.GetModuleHandleW("kernel32.dll"),
            b"LoadLibraryA"
        )
        
        if not load_library_addr:
            print("Failed to get LoadLibraryA address")
            ctypes.windll.kernel32.VirtualFreeEx(process_handle, remote_memory, 0, 0x8000)
            return False
            
        # Create a remote thread that calls LoadLibraryA with our DLL path
        thread_id = wintypes.DWORD()
        thread_handle = kernel32.CreateRemoteThread(
            process_handle,
            None,
            0,
            load_library_addr,
            remote_memory,
            0,
            ctypes.byref(thread_id)
        )
        
        if not thread_handle:
            print("Failed to create remote thread")
            ctypes.windll.kernel32.VirtualFreeEx(process_handle, remote_memory, 0, 0x8000)
            return False
            
        # Wait for the thread to complete
        kernel32.WaitForSingleObject(thread_handle, 0xFFFFFFFF)  # INFINITE
        
        # Clean up
        kernel32.CloseHandle(thread_handle)
        kernel32.VirtualFreeEx(process_handle, remote_memory, 0, 0x8000)
        
        print("DLL injected successfully!")
        return True
        
    finally:
        ctypes.windll.kernel32.CloseHandle(process_handle)


def main():
    print("=== Mewgenics DLL Injector ===\n")
    
    # Check if DLL exists
    dll_name = "mewgenics_mod.dll"
    dll_path = os.path.abspath(dll_name)
    
    if not os.path.exists(dll_path):
        print(f"ERROR: {dll_name} not found!")
        print(f"Expected location: {dll_path}")
        print("\nBuild the DLL first using: build_minhook_mod.bat")
        return
        
    print(f"DLL path: {dll_path}")
    
    # Find the process
    process_name = "Mewgenics.exe"
    print(f"\nSearching for {process_name}...")
    
    pid = find_process(process_name)
    if not pid:
        print(f"ERROR: {process_name} is not running!")
        print("Start the game first, then run this script.")
        return
        
    print(f"Found {process_name} (PID: {pid})")
    
    # Inject the DLL
    print(f"\nInjecting {dll_name}...")
    if inject_dll(pid, dll_path):
        print("\n✓ SUCCESS!")
        print("\nCheck the game window - a console should appear showing the mod status.")
        print("The value should now be set to the configured target value.")
    else:
        print("\n✗ FAILED!")
        print("Make sure you're running this script as Administrator.")


if __name__ == "__main__":
    main()
    input("\nPress Enter to exit...")
