"""Memory editor for Mewgenics.exe using Cheat Engine pointer offsets.

This script demonstrates how to:
1. Find and attach to the Mewgenics process
2. Resolve pointer chains (base address + offsets)
3. Read and write memory values
"""

import ctypes
import ctypes.wintypes as wintypes
import struct
import sys


# Windows API constants
PROCESS_ALL_ACCESS = 0x1F0FFF
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010

# Windows API structures
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


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(wintypes.BYTE)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260)
    ]


class MemoryEditor:
    """Memory editor for reading and writing process memory."""
    
    def __init__(self):
        self.process_handle = None
        self.process_id = None
        self.base_address = None
        
    def find_process(self, process_name):
        """Find process ID by name.
        
        Args:
            process_name: Name of the process (e.g., "Mewgenics.exe")
            
        Returns:
            Process ID if found, None otherwise
        """
        snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == -1:
            print("Failed to create process snapshot")
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
        
    def get_module_base_address(self, process_id, module_name):
        """Get the base address of a module in a process.
        
        Args:
            process_id: Target process ID
            module_name: Name of the module (e.g., "Mewgenics.exe")
            
        Returns:
            Base address of the module if found, None otherwise
        """
        snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(
            TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, process_id
        )
        if snapshot == -1:
            print("Failed to create module snapshot")
            return None
            
        module_entry = MODULEENTRY32()
        module_entry.dwSize = ctypes.sizeof(MODULEENTRY32)
        
        if ctypes.windll.kernel32.Module32First(snapshot, ctypes.byref(module_entry)):
            while True:
                if module_entry.szModule.decode('utf-8', errors='ignore').lower() == module_name.lower():
                    base_addr = ctypes.cast(module_entry.modBaseAddr, ctypes.c_void_p).value
                    ctypes.windll.kernel32.CloseHandle(snapshot)
                    return base_addr
                    
                if not ctypes.windll.kernel32.Module32Next(snapshot, ctypes.byref(module_entry)):
                    break
                    
        ctypes.windll.kernel32.CloseHandle(snapshot)
        return None
        
    def open_process(self, process_name):
        """Open a process for memory operations.
        
        Args:
            process_name: Name of the process (e.g., "Mewgenics.exe")
            
        Returns:
            True if successful, False otherwise
        """
        self.process_id = self.find_process(process_name)
        if not self.process_id:
            print(f"Process '{process_name}' not found!")
            return False
            
        print(f"Found process '{process_name}' with PID: {self.process_id}")
        
        self.process_handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_ALL_ACCESS, False, self.process_id
        )
        
        if not self.process_handle:
            print(f"Failed to open process {self.process_id}")
            return False
            
        # Get base address of the main module
        self.base_address = self.get_module_base_address(self.process_id, process_name)
        if not self.base_address:
            print(f"Failed to get base address of '{process_name}'")
            return False
            
        print(f"Base address: 0x{self.base_address:X}")
        return True
        
    def read_memory(self, address, size=4):
        """Read memory from the process.
        
        Args:
            address: Memory address to read from
            size: Number of bytes to read (default: 4)
            
        Returns:
            Bytes read, or None on failure
        """
        if not self.process_handle:
            print("Process not opened!")
            return None
            
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        
        success = ctypes.windll.kernel32.ReadProcessMemory(
            self.process_handle,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(bytes_read)
        )
        
        if not success:
            print(f"Failed to read memory at 0x{address:X}")
            return None
            
        return buffer.raw
        
    def write_memory(self, address, data):
        """Write memory to the process.
        
        Args:
            address: Memory address to write to
            data: Bytes to write
            
        Returns:
            True if successful, False otherwise
        """
        if not self.process_handle:
            print("Process not opened!")
            return False
            
        bytes_written = ctypes.c_size_t()
        
        success = ctypes.windll.kernel32.WriteProcessMemory(
            self.process_handle,
            ctypes.c_void_p(address),
            data,
            len(data),
            ctypes.byref(bytes_written)
        )
        
        if not success:
            print(f"Failed to write memory at 0x{address:X}")
            return False
            
        return True
        
    def resolve_pointer_chain(self, base_offset, offsets):
        """Resolve a pointer chain to get the final address.
        
        Args:
            base_offset: Offset from the module base address
            offsets: List of offsets to follow through the pointer chain
            
        Returns:
            Final address if successful, None otherwise
        """
        if not self.base_address:
            print("Base address not set!")
            return None
            
        # Start with base address + initial offset
        address = self.base_address + base_offset
        print(f"Starting address: 0x{address:X}")
        
        # Follow each pointer in the chain (except the last offset)
        for i, offset in enumerate(offsets[:-1]):
            # Read the pointer at the current address
            data = self.read_memory(address, 8)  # 64-bit pointer
            if not data:
                return None
                
            # Unpack as 64-bit unsigned integer
            address = struct.unpack('<Q', data)[0]
            print(f"  Pointer {i+1}: 0x{address:X}")
            
            # Add the offset
            address += offset
            print(f"  + offset 0x{offset:X} = 0x{address:X}")
            
        # Add the final offset
        if offsets:
            address += offsets[-1]
            print(f"Final address: 0x{address:X}")
            
        return address
        
    def pattern_scan(self, pattern, mask=None, start_offset=0, end_offset=None, chunk_size=1024*1024):
        """Scan memory for a byte pattern (AOB scan).
        
        Args:
            pattern: Byte pattern to search for (e.g., b"\\x48\\x8B\\x05\\x00\\x00\\x00\\x00")
            mask: Mask string where 'x' = match, '?' = wildcard (e.g., "xxx????")
                  If None, all bytes must match exactly
            start_offset: Offset from base address to start scanning
            end_offset: Offset from base address to end scanning (None = scan 50MB)
            chunk_size: Size of memory to read per iteration (default: 1MB)
            
        Returns:
            Address where pattern was found, or None if not found
        """
        if not self.base_address or not self.process_handle:
            print("Process not opened!")
            return None
            
        # Default scan range: 50MB from base
        if end_offset is None:
            end_offset = start_offset + (50 * 1024 * 1024)
            
        start_address = self.base_address + start_offset
        end_address = self.base_address + end_offset
        
        print(f"Scanning from 0x{start_address:X} to 0x{end_address:X}")
        print(f"Pattern: {pattern.hex()}")
        
        pattern_len = len(pattern)
        current_address = start_address
        overlap = pattern_len - 1  # Overlap to catch patterns spanning chunks
        
        # Scan memory in chunks
        while current_address < end_address:
            # Calculate chunk size (don't exceed end)
            remaining = end_address - current_address
            read_size = min(chunk_size, remaining)
            
            # Read this chunk
            buffer = ctypes.create_string_buffer(read_size)
            bytes_read = ctypes.c_size_t()
            
            success = ctypes.windll.kernel32.ReadProcessMemory(
                self.process_handle,
                ctypes.c_void_p(current_address),
                buffer,
                read_size,
                ctypes.byref(bytes_read)
            )
            
            if not success or bytes_read.value == 0:
                # Skip this chunk if read failed (might be unallocated memory)
                current_address += chunk_size
                continue
                
            memory = buffer.raw[:bytes_read.value]
            
            # Search for the pattern in this chunk
            if mask:
                # Search with wildcards
                for i in range(len(memory) - pattern_len + 1):
                    match = True
                    for j in range(pattern_len):
                        if mask[j] == 'x' and memory[i + j] != pattern[j]:
                            match = False
                            break
                    if match:
                        found_address = current_address + i
                        print(f"Pattern found at: 0x{found_address:X}")
                        print(f"Offset from base: +0x{found_address - self.base_address:X}")
                        return found_address
            else:
                # Exact match
                index = memory.find(pattern)
                if index != -1:
                    found_address = current_address + index
                    print(f"Pattern found at: 0x{found_address:X}")
                    print(f"Offset from base: +0x{found_address - self.base_address:X}")
                    return found_address
            
            # Move to next chunk with overlap to catch patterns on boundaries
            current_address += read_size - overlap
                
        print("Pattern not found")
        return None
    
    def resolve_instruction_pointer(self, instruction_address, offset_from_opcode=3):
        """Read RIP-relative offset from an instruction and calculate the target address.
        
        For x64 MOV instructions like: 48 8B 05 [B556C300]
        The offset is at instruction+3 (after the opcode bytes)
        
        Args:
            instruction_address: Address of the instruction
            offset_from_opcode: Bytes from instruction start to offset (default: 3)
            
        Returns:
            Calculated target address, or None on failure
        """
        # Read the 4-byte RIP-relative offset
        offset_bytes = self.read_memory(instruction_address + offset_from_opcode, 4)
        if not offset_bytes:
            return None
            
        # Unpack as signed 32-bit integer
        rip_offset = struct.unpack('<i', offset_bytes)[0]
        
        # Calculate: RIP (instruction_address + instruction_length) + offset
        # For "48 8B 05 XX XX XX XX" the instruction is 7 bytes long
        instruction_length = 7
        target_address = instruction_address + instruction_length + rip_offset
        
        print(f"RIP-relative offset: 0x{rip_offset:X}")
        print(f"Calculated pointer location: 0x{target_address:X}")
        
        return target_address
    
    def close(self):
        """Close the process handle."""
        if self.process_handle:
            ctypes.windll.kernel32.CloseHandle(self.process_handle)
            self.process_handle = None


def main():
    """Example usage based on Cheat Engine findings:
    
    From Cheat Engine disassembly:
    Mewgenics.exe+796824: 48 8B 05 B556C300  - mov rax,[Mewgenics.exe+13CBEE0]
    Mewgenics.exe+79682B: 44 29 80 B4000000  - sub [rax+000000B4],r8d
    
    This accesses: [[Mewgenics.exe+13CBEE0] + 0xB4]
    
    TWO METHODS:
    Method 1: Static offset (breaks on restart)
    Method 2: Pattern scan (reliable every time)
    """
    
    editor = MemoryEditor()
    
    # Open the process
    if not editor.open_process("Mewgenics.exe"):
        return
        
    try:
        # ========================================
        # METHOD 1: Static offset
        # ========================================
        USE_PATTERN_SCAN = True  # Set to False to use static offset
        
        if not USE_PATTERN_SCAN:
            # Static pointer chain (will break on game restart!)
            # From: mov rax,[Mewgenics.exe+13CBEE0] then [rax+0xB4]
            base_offset = 0x013CBEE0  # This changes between sessions!
            offsets = [0xB4]
            
            # Resolve the pointer chain
            final_address = editor.resolve_pointer_chain(base_offset, offsets)
        else:
            # ========================================
            # METHOD 2: Pattern scan (RECOMMENDED - works every time!)
            # ========================================
            # Pattern from Cheat Engine:
            # 7FF71DED6824 - 48 8B 05 B556C300  - mov rax,[Mewgenics.exe+13CBEE0]
            # 7FF71DED682B - 44 29 80 B4000000  - sub [rax+000000B4],r8d
            #
            # We search for these instruction bytes with wildcards for addresses
            
            # Pattern: "mov rax,[rip+offset]" followed by "sub [rax+0xB4],r8d"
            pattern = b"\x48\x8B\x05\x00\x00\x00\x00\x44\x29\x80\xB4\x00\x00\x00"
            mask    = "xxx????xxxxxxx"  # Wildcard the RIP-relative offset
            
            print("\n--- Pattern Scanning ---")
            instruction_address = editor.pattern_scan(pattern, mask, start_offset=0)
            if not instruction_address:
                print("Pattern not found! The game code may have changed.")
                return
                
            print(f"Found instruction at: 0x{instruction_address:X}")
            print(f"Offset from base: +0x{instruction_address - editor.base_address:X}")
            
            # Parse the RIP-relative offset from the MOV instruction
            pointer_location = editor.resolve_instruction_pointer(instruction_address)
            if not pointer_location:
                print("Failed to resolve instruction pointer")
                return
                
            # Read the pointer value
            pointer_data = editor.read_memory(pointer_location, 8)  # 64-bit pointer
            if not pointer_data:
                print("Failed to read pointer")
                return
                
            pointer_value = struct.unpack('<Q', pointer_data)[0]
            print(f"Pointer value: 0x{pointer_value:X}")
            
            # Add the final offset (0xB4 from the instruction)
            final_address = pointer_value + 0xB4
            print(f"Final address: 0x{final_address:X}")
        
        if not final_address:
            print("Failed to resolve pointer chain")
            return
            
        print("\n--- Reading Current Value ---")
        # Read the value (assuming it's a 4-byte integer)
        data = editor.read_memory(final_address, 4)
        if data:
            value = struct.unpack('<i', data)[0]  # Signed 32-bit int
            print(f"Current value: {value}")
            
            # You can also read as different types:
            # unsigned int: struct.unpack('<I', data)[0]
            # float: struct.unpack('<f', data)[0]
            # unsigned byte: data[0]
            
        print("\n--- Writing New Value ---")
        # Write a new value
        new_value = 25  # Change this to whatever you want
        new_data = struct.pack('<i', new_value)  # Pack as signed 32-bit int
        
        if editor.write_memory(final_address, new_data):
            print(f"Successfully wrote value: {new_value}")
            
            # Verify the write
            data = editor.read_memory(final_address, 4)
            if data:
                verify_value = struct.unpack('<i', data)[0]
                print(f"Verified value: {verify_value}")
        else:
            print("Failed to write memory")
            
    finally:
        editor.close()


if __name__ == "__main__":
    print("=== Mewgenics Memory Editor ===\n")
    main()
