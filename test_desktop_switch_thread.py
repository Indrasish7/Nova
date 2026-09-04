"""
Test SetThreadDesktop on a fresh un-initialized worker thread.
"""

import threading
import ctypes
from ctypes import wintypes
import comtypes
import comtypes.client

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_desktop_name():
    h_desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
    buf = ctypes.create_unicode_buffer(256)
    needed = wintypes.DWORD()
    if user32.GetUserObjectInformationW(h_desk, 2, buf, 256, ctypes.byref(needed)):  # UOI_NAME = 2
        return buf.value
    return "unknown"

def worker_thread():
    print(f"[Worker Thread] Initial Desktop: {get_desktop_name()}")
    
    # Open 'Default' desktop
    DESKTOP_ALL_ACCESS = 0x0100 | 0x0080 | 0x0040 | 0x0020 | 0x0010 | 0x0008 | 0x0004 | 0x0002 | 0x0001
    h_desk_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    print(f"[Worker Thread] OpenDesktopW('Default') Handle: {h_desk_default}")
    
    if h_desk_default:
        res = user32.SetThreadDesktop(h_desk_default)
        err = ctypes.GetLastError()
        print(f"[Worker Thread] SetThreadDesktop Result: {res} (error={err}) | New Desktop: {get_desktop_name()}")
    
    # Initialize COM and UIA inside worker thread
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient
    
    ctypes.windll.ole32.CoInitialize(None)
    automation = comtypes.client.CreateObject(UIAutomationClient.CUIAutomation)
    
    root = automation.GetRootElement()
    cond_true = automation.CreateTrueCondition()
    children = root.FindAll(UIAutomationClient.TreeScope_Children, cond_true)
    
    print(f"[Worker Thread] UIA Root Children Count on '{get_desktop_name()}': {children.Length}")
    for i in range(children.Length):
        e = children.GetElement(i)
        try:
            print(f"  [{i}] Title='{e.CurrentName}' | AutoID='{e.CurrentAutomationId}' | Class='{e.CurrentClassName}' | PID={e.CurrentProcessId}")
        except Exception as ex:
            print(f"  [{i}] Error: {ex}")

t = threading.Thread(target=worker_thread)
t.start()
t.join()
