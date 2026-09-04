"""
Test switching thread desktop context to 'Default' desktop station.
"""

import ctypes
from ctypes import wintypes
import comtypes
import comtypes.client

# Load UIAutomationCore
comtypes.client.GetModule("UIAutomationCore.dll")
from comtypes.gen import UIAutomationClient

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_desktop_name():
    h_desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
    buf = ctypes.create_unicode_buffer(256)
    needed = wintypes.DWORD()
    if user32.GetUserObjectInformationW(h_desk, 2, buf, 256, ctypes.byref(needed)):  # UOI_NAME = 2
        return buf.value
    return "unknown"

print(f"Initial Thread Desktop: {get_desktop_name()}")

# Try opening and setting thread desktop to 'Default'
GENERIC_ALL = 0x10000000
h_desk_default = user32.OpenDesktopW("Default", 0, False, GENERIC_ALL)
print(f"OpenDesktopW('Default') Handle: {h_desk_default}")

if h_desk_default:
    res = user32.SetThreadDesktop(h_desk_default)
    print(f"SetThreadDesktop Result: {res} | New Thread Desktop: {get_desktop_name()}")

ctypes.windll.ole32.CoInitialize(None)
automation = comtypes.client.CreateObject(UIAutomationClient.CUIAutomation)

root = automation.GetRootElement()
cond_true = automation.CreateTrueCondition()
children = root.FindAll(UIAutomationClient.TreeScope_Children, cond_true)

print(f"\nUIA Root Children Count on Desktop '{get_desktop_name()}': {children.Length}")

for i in range(min(children.Length, 30)):
    e = children.GetElement(i)
    try:
        name = str(e.CurrentName or "")
        pid = int(e.CurrentProcessId or 0)
        auto_id = str(e.CurrentAutomationId or "")
        cls_name = str(e.CurrentClassName or "")
        print(f"  [{i}] Title='{name}' | PID={pid} | AutoID='{auto_id}' | Class='{cls_name}'")
    except Exception as ex:
        print(f"  [{i}] Error: {ex}")
