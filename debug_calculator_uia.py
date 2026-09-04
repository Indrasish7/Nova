"""
UIA Diagnostic Script for Windows Calculator.
Enumerates top-level HWNDs, identifies Calculator window, and dumps its UIA tree hierarchy.
"""

import ctypes
from ctypes import wintypes
import comtypes
import comtypes.client
from pathlib import Path

# Load UIAutomationCore
comtypes.client.GetModule("UIAutomationCore.dll")
from comtypes.gen import UIAutomationClient

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_process_name(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return "unknown"
    buf = ctypes.create_unicode_buffer(1024)
    sz = wintypes.DWORD(1024)
    if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz)):
        kernel32.CloseHandle(h)
        return Path(buf.value).name
    kernel32.CloseHandle(h)
    return "unknown"

print("=== ENUMERATING WINDOWS TO FIND CALCULATOR ===")

calc_hwnds = []

def enum_cb(hwnd, lparam):
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            title_buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buf, length + 1)
            title = title_buf.value
            
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = get_process_name(pid.value)
            
            if "calculator" in title.lower() or "calc" in proc_name.lower():
                print(f"FOUND MATCHING WINDOW: HWND={hwnd} | Title='{title}' | PID={pid.value} | Proc='{proc_name}'")
                calc_hwnds.append((hwnd, title, pid.value, proc_name))
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

if not calc_hwnds:
    print("No Calculator window currently open. Launching 'calc.exe'...")
    import subprocess
    subprocess.Popen("calc.exe")
    import time
    time.sleep(2)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

print(f"\nFound {len(calc_hwnds)} Calculator window candidate(s).")

# Initialize UIA
ctypes.windll.ole32.CoInitialize(None)
automation = comtypes.client.CreateObject(UIAutomationClient.CUIAutomation)

CONTROL_TYPE_NAMES = {
    50000: "Button", 50001: "Calendar", 50002: "CheckBox", 50003: "ComboBox",
    50004: "Edit", 50005: "Hyperlink", 50006: "Image", 50007: "ListItem",
    50008: "List", 50009: "Menu", 50010: "MenuBar", 50011: "MenuItem",
    50012: "ProgressBar", 50013: "RadioButton", 50014: "ScrollBar", 50015: "Slider",
    50016: "Spinner", 50017: "StatusBar", 50018: "Tab", 50019: "TabItem",
    50020: "Text", 50021: "ToolBar", 50022: "ToolTip", 50023: "Tree",
    50024: "TreeItem", 50032: "Window", 50033: "Pane", 50034: "Group"
}

for hwnd, title, pid, proc_name in calc_hwnds:
    print(f"\n==================================================")
    print(f"INSPECTING UIA TREE FOR HWND={hwnd} ('{title}', Proc='{proc_name}')")
    print(f"==================================================")
    
    try:
        root_elem = automation.ElementFromHandle(hwnd)
        cond_true = automation.CreateTrueCondition()
        elems = root_elem.FindAll(UIAutomationClient.TreeScope_Subtree, cond_true)
        print(f"Total UIA descendants found in window subtree: {elems.Length}")
        
        button_matches = []
        
        for i in range(elems.Length):
            e = elems.GetElement(i)
            try:
                name = str(e.CurrentName or "")
                c_type_id = int(e.CurrentControlType)
                c_type_str = CONTROL_TYPE_NAMES.get(c_type_id, f"Unknown({c_type_id})")
                auto_id = str(e.CurrentAutomationId or "")
                cls_name = str(e.CurrentClassName or "")
                enabled = bool(e.CurrentIsEnabled)
                rect = e.CurrentBoundingRectangle
                rect_str = f"({rect.left}, {rect.top}, {rect.right}, {rect.bottom})"
                
                # Check patterns
                pats = []
                try:
                    if e.GetCurrentPattern(UIAutomationClient.UIA_InvokePatternId):
                        pats.append("InvokePattern")
                except: pass
                try:
                    if e.GetCurrentPattern(UIAutomationClient.UIA_SelectionItemPatternId):
                        pats.append("SelectionItemPattern")
                except: pass
                try:
                    if e.GetCurrentPattern(UIAutomationClient.UIA_TogglePatternId):
                        pats.append("TogglePattern")
                except: pass

                if name or auto_id or "num" in auto_id.lower() or c_type_str == "Button":
                    button_matches.append({
                        "index": i,
                        "name": name,
                        "control_type": c_type_str,
                        "auto_id": auto_id,
                        "class_name": cls_name,
                        "enabled": enabled,
                        "rect": rect_str,
                        "patterns": pats
                    })
            except Exception as ex:
                continue

        print(f"\n--- RELEVANT UIA CONTROLS ({len(button_matches)} matches) ---")
        for m in button_matches:
            print(f"  [{m['index']}] Name='{m['name']}' | Type={m['control_type']} | AutoID='{m['auto_id']}' | Enabled={m['enabled']} | Rect={m['rect']} | Patterns={m['patterns']}")

    except Exception as err:
        print(f"ERROR inspecting HWND {hwnd}: {err}")
