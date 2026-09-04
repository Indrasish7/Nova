"""
Check Desktop Station, Session ID, and Window Station for background process (fixed).
"""

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_session_id():
    pid = kernel32.GetCurrentProcessId()
    session_id = wintypes.DWORD()
    if kernel32.ProcessIdToSessionId(pid, ctypes.byref(session_id)):
        return session_id.value
    return -1

def get_desktop_name():
    h_desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
    buf = ctypes.create_unicode_buffer(256)
    needed = wintypes.DWORD()
    if user32.GetUserObjectInformationW(h_desk, 2, buf, 256, ctypes.byref(needed)):  # UOI_NAME = 2
        return buf.value
    return "unknown"

def get_winsta_name():
    h_winsta = user32.GetProcessWindowStation()
    buf = ctypes.create_unicode_buffer(256)
    needed = wintypes.DWORD()
    if user32.GetUserObjectInformationW(h_winsta, 2, buf, 256, ctypes.byref(needed)):  # UOI_NAME = 2
        return buf.value
    return "unknown"

print(f"Current Process ID:       {kernel32.GetCurrentProcessId()}")
print(f"Current Session ID:       {get_session_id()}")
print(f"Current Window Station:   {get_winsta_name()}")
print(f"Current Thread Desktop:   {get_desktop_name()}")
