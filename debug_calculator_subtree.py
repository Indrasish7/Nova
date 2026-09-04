"""
Inspect Calculator UIA Subtree on Default Desktop Station.
"""

import threading
import ctypes
from ctypes import wintypes
import comtypes
import comtypes.client

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

CONTROL_TYPE_NAMES = {
    50000: "Button", 50001: "Calendar", 50002: "CheckBox", 50003: "ComboBox",
    50004: "Edit", 50005: "Hyperlink", 50006: "Image", 50007: "ListItem",
    50008: "List", 50009: "Menu", 50010: "MenuBar", 50011: "MenuItem",
    50012: "ProgressBar", 50013: "RadioButton", 50014: "ScrollBar", 50015: "Slider",
    50016: "Spinner", 50017: "StatusBar", 50018: "Tab", 50019: "TabItem",
    50020: "Text", 50021: "ToolBar", 50022: "ToolTip", 50023: "Tree",
    50024: "TreeItem", 50032: "Window", 50033: "Pane", 50034: "Group"
}

def inspect_calculator():
    # 1. Switch to 'Default' desktop
    DESKTOP_ALL_ACCESS = 0x0100 | 0x0080 | 0x0040 | 0x0020 | 0x0010 | 0x0008 | 0x0004 | 0x0002 | 0x0001
    h_desk_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    if h_desk_default:
        user32.SetThreadDesktop(h_desk_default)

    # 2. Init COM and UIA
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient

    ctypes.windll.ole32.CoInitialize(None)
    automation = comtypes.client.CreateObject(UIAutomationClient.CUIAutomation)

    root = automation.GetRootElement()
    cond_true = automation.CreateTrueCondition()
    children = root.FindAll(UIAutomationClient.TreeScope_Children, cond_true)

    calc_window = None
    for i in range(children.Length):
        e = children.GetElement(i)
        if "calculator" in str(e.CurrentName or "").lower():
            calc_window = e
            break

    if not calc_window:
        print("Calculator window not found in UIA root children.")
        return

    print("==================================================")
    print(f"CALCULATOR WINDOW ROOT FOUND:")
    print(f"  Name:       '{calc_window.CurrentName}'")
    print(f"  Class:      '{calc_window.CurrentClassName}'")
    print(f"  PID:        {calc_window.CurrentProcessId}")
    print(f"  AutoID:     '{calc_window.CurrentAutomationId}'")
    print("==================================================\n")

    sub_elems = calc_window.FindAll(UIAutomationClient.TreeScope_Subtree, cond_true)
    print(f"Total UIA Subtree Elements: {sub_elems.Length}\n")

    print("--- DUMPING ALL UIA DESCENDANTS ---")
    for i in range(sub_elems.Length):
        e = sub_elems.GetElement(i)
        try:
            name = str(e.CurrentName or "")
            c_type_id = int(e.CurrentControlType)
            c_type_str = CONTROL_TYPE_NAMES.get(c_type_id, f"Unknown({c_type_id})")
            auto_id = str(e.CurrentAutomationId or "")
            cls_name = str(e.CurrentClassName or "")
            enabled = bool(e.CurrentIsEnabled)
            rect = e.CurrentBoundingRectangle
            rect_str = f"({rect.left}, {rect.top}, {rect.right}, {rect.bottom})"

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
                if e.GetCurrentPattern(UIAutomationClient.UIA_ValuePatternId):
                    pats.append("ValuePattern")
            except: pass

            # Filter interesting controls
            if name or auto_id or c_type_str in ["Button", "Text", "Edit", "Pane"]:
                print(f"[{i:<3}] Name='{name:<25}' | Type='{c_type_str:<10}' | AutoID='{auto_id:<20}' | Enabled={enabled} | Rect={rect_str} | Patterns={pats}")
        except Exception as ex:
            continue

t = threading.Thread(target=inspect_calculator)
t.start()
t.join()
