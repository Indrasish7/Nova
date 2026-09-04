"""
Enumerate top-level windows and UIA elements via UIA Root Element.
"""

import ctypes
import comtypes
import comtypes.client
from pathlib import Path

# Load UIAutomationCore
comtypes.client.GetModule("UIAutomationCore.dll")
from comtypes.gen import UIAutomationClient

ctypes.windll.ole32.CoInitialize(None)
automation = comtypes.client.CreateObject(UIAutomationClient.CUIAutomation)

root = automation.GetRootElement()
cond_true = automation.CreateTrueCondition()
children = root.FindAll(UIAutomationClient.TreeScope_Children, cond_true)

print(f"=== UIA ROOT CHILDREN COUNT: {children.Length} ===")

for i in range(children.Length):
    e = children.GetElement(i)
    try:
        name = str(e.CurrentName or "")
        pid = int(e.CurrentProcessId or 0)
        c_type = int(e.CurrentControlType)
        auto_id = str(e.CurrentAutomationId or "")
        cls_name = str(e.CurrentClassName or "")
        print(f"[{i}] Title='{name}' | PID={pid} | AutoID='{auto_id}' | Class='{cls_name}'")
    except Exception as ex:
        print(f"[{i}] Error reading element: {ex}")
