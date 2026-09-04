"""
Inspect all visible top-level windows and process executable names (robust).
"""

import ctypes
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_process_name(pid):
    if pid <= 0:
        return "unknown"
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return "unknown"
    buf = ctypes.create_unicode_buffer(1024)
    sz = wintypes.DWORD(1024)
    res = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz))
    kernel32.CloseHandle(h)
    if res:
        return Path(buf.value).name
    return "unknown"

print("=== ALL VISIBLE TOP-LEVEL WINDOWS ===")

def enum_cb(hwnd, lparam):
    try:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                title_buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, title_buf, length + 1)
                title = title_buf.value
            
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = get_process_name(pid.value)
            
            if title:
                print(f"HWND={hwnd:<10} | PID={pid.value:<6} | Proc='{proc_name:<20}' | Title='{title}'")
    except Exception as e:
        print(f"Error in enum_cb: {e}")
    return 1

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
cb = WNDENUMPROC(enum_cb)
user32.EnumWindows(cb, 0)
