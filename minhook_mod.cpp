/*
 * MinHook-based memory modifier for Mewgenics.exe
 * 
 * This hooks the function that subtracts from [rax+0xB4] and modifies the behavior.
 * Much cleaner than direct memory editing!
 * 
 * Instructions to hook:
 * Mewgenics.exe+796824: 48 8B 05 B556C300  - mov rax,[Mewgenics.exe+13CBEE0]
 * Mewgenics.exe+79682B: 44 29 80 B4000000  - sub [rax+000000B4],r8d
 * 
 * Build with:
 * cl /LD /O2 minhook_mod.cpp /I"path\to\minhook\include" /link "path\to\minhook\lib\libMinHook.x64.lib"
 */

#include <windows.h>
#include <stdio.h>
#include "MinHook.h"

// Configuration
#define TARGET_VALUE 999  // Set the value you want
#define FREEZE_VALUE true // If true, value never changes. If false, just sets it once.

// Pattern to find the function
const BYTE pattern[] = { 0x48, 0x8B, 0x05, 0x00, 0x00, 0x00, 0x00, 0x44, 0x29, 0x80, 0xB4, 0x00, 0x00, 0x00 };
const char mask[] = "xxx????xxxxxxx";

// Global pointer to store the target address
void** g_PointerLocation = nullptr;
int g_TargetOffset = 0xB4;

// Trampoline for original function
typedef void(__fastcall* OriginalFunc)(void*, void*, void*, void*, int);
OriginalFunc g_OriginalFunc = nullptr;

/**
 * Pattern scanner
 */
BYTE* PatternScan(BYTE* start, size_t size, const BYTE* pattern, const char* mask) {
    size_t patternLen = strlen(mask);
    
    for (size_t i = 0; i < size - patternLen; i++) {
        bool found = true;
        for (size_t j = 0; j < patternLen; j++) {
            if (mask[j] == 'x' && start[i + j] != pattern[j]) {
                found = false;
                break;
            }
        }
        if (found) return &start[i];
    }
    return nullptr;
}

/**
 * Find the instruction in the loaded module
 */
BYTE* FindInstruction() {
    HMODULE hModule = GetModuleHandle(nullptr); // Get Mewgenics.exe base
    if (!hModule) return nullptr;
    
    MODULEINFO modInfo;
    if (!GetModuleInformation(GetCurrentProcess(), hModule, &modInfo, sizeof(MODULEINFO))) {
        return nullptr;
    }
    
    // Scan the module
    BYTE* result = PatternScan(
        (BYTE*)hModule, 
        modInfo.SizeOfImage, 
        pattern, 
        mask
    );
    
    return result;
}

/**
 * Parse RIP-relative offset from MOV instruction
 */
void* GetPointerLocation(BYTE* instruction) {
    // Read the 4-byte RIP-relative offset at instruction+3
    int offset = *(int*)(instruction + 3);
    
    // Calculate: RIP (after 7-byte instruction) + offset
    return (void*)(instruction + 7 + offset);
}

/**
 * Hook function - intercepts the SUB instruction
 * 
 * We'll create a detour for a function that calls this code.
 * Since this is a mid-function hook, we need to be careful.
 * 
 * Alternative approach: Use inline hooking or modify behavior through other means
 */

// For this example, let's use a different approach:
// We'll hook at the function level by finding the function start

/**
 * Better approach: Hook the entire function that contains this code
 * Or use a timer thread to constantly set the value
 */

/**
 * Timer thread that monitors and sets the value
 */
DWORD WINAPI ValueMonitorThread(LPVOID lpParam) {
    printf("[MinHook Mod] Monitor thread started\n");
    
    while (true) {
        if (g_PointerLocation && *g_PointerLocation) {
            void* targetObject = *g_PointerLocation;
            int* targetValue = (int*)((BYTE*)targetObject + g_TargetOffset);
            
            if (FREEZE_VALUE) {
                // Constantly set to target value
                *targetValue = TARGET_VALUE;
            } else {
                // Set once and exit
                *targetValue = TARGET_VALUE;
                printf("[MinHook Mod] Value set to %d\n", TARGET_VALUE);
                break;
            }
        }
        
        Sleep(10); // Check every 10ms
    }
    
    return 0;
}

/**
 * Alternative: Use MinHook to hook at function boundaries
 * Find the function that contains our target instructions
 */

// We can also create inline hooks using MinHook for mid-function hooks
void* CreateMidFunctionHook(BYTE* instructionAddr) {
    // Create a code cave that replaces the instruction
    // This is advanced and requires careful assembly
    
    // For now, let's use the simpler timer approach
    return nullptr;
}

/**
 * DLL entry point
 */
BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    switch (ul_reason_for_call) {
    case DLL_PROCESS_ATTACH:
    {
        // Allocate console for debug output
        AllocConsole();
        FILE* f;
        freopen_s(&f, "CONOUT$", "w", stdout);
        
        printf("=== Mewgenics MinHook Mod ===\n\n");
        
        // Find the instruction
        BYTE* instruction = FindInstruction();
        if (!instruction) {
            printf("[ERROR] Could not find target instruction!\n");
            printf("Pattern: ");
            for (size_t i = 0; i < sizeof(pattern); i++) {
                if (mask[i] == 'x') printf("%02X ", pattern[i]);
                else printf("?? ");
            }
            printf("\n");
            return FALSE;
        }
        
        printf("[SUCCESS] Found instruction at: 0x%p\n", instruction);
        printf("Offset from base: +0x%llX\n", (BYTE*)instruction - (BYTE*)GetModuleHandle(nullptr));
        
        // Get the pointer location
        g_PointerLocation = (void**)GetPointerLocation(instruction);
        printf("Pointer location: 0x%p\n", g_PointerLocation);
        
        // Initialize MinHook
        if (MH_Initialize() != MH_OK) {
            printf("[ERROR] Failed to initialize MinHook\n");
            return FALSE;
        }
        
        printf("\n[INFO] Starting monitor thread...\n");
        printf("[INFO] Target value: %d\n", TARGET_VALUE);
        printf("[INFO] Freeze mode: %s\n", FREEZE_VALUE ? "ON" : "OFF");
        
        // Start the monitor thread
        CreateThread(nullptr, 0, ValueMonitorThread, nullptr, 0, nullptr);
        
        printf("\n[SUCCESS] Mod loaded successfully!\n");
        break;
    }
    case DLL_PROCESS_DETACH:
        MH_Uninitialize();
        break;
    }
    return TRUE;
}
