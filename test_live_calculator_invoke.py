"""
Live verification script: Execute InvokePattern on Calculator button 1 ('One' / 'num1Button')
and verify CalculatorResults state change from 'Display is 0' to 'Display is 1'.
"""

import threading
import ctypes
from ctypes import wintypes
import comtypes
import comtypes.client
import time

user32 = ctypes.windll.user32

def test_live_invoke():
    # 1. Switch thread desktop to 'Default'
    DESKTOP_ALL_ACCESS = 0x0100 | 0x0080 | 0x0040 | 0x0020 | 0x0010 | 0x0008 | 0x0004 | 0x0002 | 0x0001
    h_desk = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    if h_desk:
        user32.SetThreadDesktop(h_desk)

    # 2. Init COM & UIA
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
        print("Calculator window not found.")
        return

    sub_elems = calc_window.FindAll(UIAutomationClient.TreeScope_Subtree, cond_true)
    
    btn_1 = None
    display_elem = None

    for i in range(sub_elems.Length):
        e = sub_elems.GetElement(i)
        auto_id = str(e.CurrentAutomationId or "")
        name = str(e.CurrentName or "")
        if auto_id == "num1Button" or (name.lower() in ["1", "one"] and int(e.CurrentControlType) == 50000):
            btn_1 = e
        if auto_id == "CalculatorResults":
            display_elem = e

    if not btn_1:
        print("Button '1' ('num1Button') not found.")
        return

    pre_display = str(display_elem.CurrentName or "") if display_elem else "unknown"
    print(f"Pre-Invocation Display Text:  '{pre_display}'")

    # Execute InvokePattern.Invoke()
    pat_inv = btn_1.GetCurrentPattern(UIAutomationClient.UIA_InvokePatternId)
    inv_pat = pat_inv.QueryInterface(UIAutomationClient.IUIAutomationInvokePattern)
    
    print(f"Executing InvokePattern.Invoke() on '{btn_1.CurrentName}' (AutoID='{btn_1.CurrentAutomationId}')...")
    inv_pat.Invoke()
    
    time.sleep(0.3)

    post_display = str(display_elem.CurrentName or "") if display_elem else "unknown"
    print(f"Post-Invocation Display Text: '{post_display}'")

    if pre_display != post_display and "1" in post_display:
        print("\nSUCCESS: Direct UIA InvokePattern.Invoke() updated Calculator display state cleanly!")
    else:
        print("\nFAILURE: Display state did not change.")

t = threading.Thread(target=test_live_invoke)
t.start()
t.join()
