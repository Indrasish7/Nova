"""
Test CoInitializeEx options for UIA root element traversal.
"""

import ctypes
from ctypes import wintypes
import comtypes
import comtypes.client

# Load UIAutomationCore
comtypes.client.GetModule("UIAutomationCore.dll")
from comtypes.gen import UIAutomationClient

def test_coinit(init_flag, flag_name):
    print(f"\n--- Testing {flag_name} (flag={init_flag}) ---")
    try:
        hr = ctypes.windll.ole32.CoInitializeEx(None, init_flag)
        print(f"CoInitializeEx HRESULT: {hex(hr & 0xFFFFFFFF)}")
    except Exception as e:
        print(f"CoInitializeEx failed: {e}")

    try:
        automation = comtypes.client.CreateObject(UIAutomationClient.CUIAutomation)
        root = automation.GetRootElement()
        cond_true = automation.CreateTrueCondition()
        children = root.FindAll(UIAutomationClient.TreeScope_Children, cond_true)
        print(f"UIA Root Children Count under {flag_name}: {children.Length}")
        for i in range(min(children.Length, 10)):
            e = children.GetElement(i)
            print(f"  [{i}] Title='{e.CurrentName}' | AutoID='{e.CurrentAutomationId}' | Class='{e.CurrentClassName}'")
    except Exception as ex:
        print(f"UIA query failed under {flag_name}: {ex}")
    finally:
        try:
            ctypes.windll.ole32.CoUninitialize()
        except:
            pass

# COINIT_MULTITHREADED = 0x0
test_coinit(0, "COINIT_MULTITHREADED")

# COINIT_APARTMENTTHREADED = 0x2
test_coinit(2, "COINIT_APARTMENTTHREADED")
