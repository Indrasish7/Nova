"""
Windows UI Automation Perception & Interaction Engine.

Provides native Windows UI Automation COM interfaces (UIAutomationCore.dll) for resolving
semantic desktop UI elements (TabItems, Buttons, Edits, MenuItems, CheckBoxes), extracting
element properties (Name, ControlType, AutomationId, ProcessName, BoundingRectangle, Enabled, Selected),
attaching to active user desktop station ("Default"), and executing direct UIA COM pattern invocations
(SelectionItemPattern.Select(), InvokePattern.Invoke(), TogglePattern.Toggle(), ExpandCollapsePattern.Expand()).
"""

import os
import ctypes
from ctypes import wintypes
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path

from nova.perception.models import UIElementMetadata, UIResolutionResult, SemanticTarget

def _attach_default_desktop() -> bool:
    """
    Switch current process window station to 'WinSta0' and thread desktop to the interactive user's 'Default' desktop.
    Ensures background tasks & subprocesses can access live desktop UIA elements.
    MUST be called before initializing COM or importing comtypes on the target thread.
    """
    try:
        user32 = ctypes.windll.user32
        WINSTA_ALL_ACCESS = 0x037F
        h_winsta = user32.OpenWindowStationW("WinSta0", False, WINSTA_ALL_ACCESS)
        if h_winsta:
            user32.SetProcessWindowStation(h_winsta)

        DESKTOP_ALL_ACCESS = 0x0100 | 0x0080 | 0x0040 | 0x0020 | 0x0010 | 0x0008 | 0x0004 | 0x0002 | 0x0001
        h_desk = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
            return True
    except Exception:
        pass
    return False

# Attach process/thread desktop to Default WinSta BEFORE importing comtypes
_attach_default_desktop()

# Load comtypes UIAutomationClient
UIAutomationClient = None
try:
    import comtypes
    import comtypes.client
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient
except Exception:
    pass


CONTROL_TYPE_NAMES: Dict[int, str] = {
    50000: "Button",
    50001: "Calendar",
    50002: "CheckBox",
    50003: "ComboBox",
    50004: "Edit",
    50005: "Hyperlink",
    50006: "Image",
    50007: "ListItem",
    50008: "List",
    50009: "Menu",
    50010: "MenuBar",
    50011: "MenuItem",
    50012: "ProgressBar",
    50013: "RadioButton",
    50014: "ScrollBar",
    50015: "Slider",
    50016: "Spinner",
    50017: "StatusBar",
    50018: "Tab",
    50019: "TabItem",
    50020: "Text",
    50021: "ToolBar",
    50022: "ToolTip",
    50023: "Tree",
    50024: "TreeItem",
    50032: "Window",
    50033: "Pane",
    50034: "Group"
}

# Semantic aliases for digits, operators, and common control names
SEMANTIC_ALIASES: Dict[str, List[str]] = {
    "0": ["0", "zero", "num0button"],
    "1": ["1", "one", "num1button"],
    "2": ["2", "two", "num2button"],
    "3": ["3", "three", "num3button"],
    "4": ["4", "four", "num4button"],
    "5": ["5", "five", "num5button"],
    "6": ["6", "six", "num6button"],
    "7": ["7", "seven", "num7button"],
    "8": ["8", "eight", "num8button"],
    "9": ["9", "nine", "num9button"],
    "+": ["+", "plus", "plusbutton", "add"],
    "-": ["-", "minus", "minusbutton", "subtract"],
    "*": ["*", "multiply", "multiplyby", "multiplybutton"],
    "/": ["/", "divide", "divideby", "dividebutton"],
    "=": ["=", "equals", "equalbutton"],
    "c": ["c", "clear", "clearbutton"],
    "ce": ["ce", "clearentry", "clearentrybutton"]
}


def _get_process_name_from_pid(pid: int) -> str:
    """Retrieve executable name from Process ID using Win32 API."""
    if pid <= 0:
        return "unknown"
    try:
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_process:
            return "unknown"
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
                return Path(buf.value).name.lower()
        finally:
            kernel32.CloseHandle(h_process)
    except Exception:
        pass
    return "unknown"



class UIAutomationResolver:
    """Resolver managing Windows UI Automation element discovery and COM pattern invocation."""

    def __init__(self):
        self._automation = None
        self._com_initialized = False
        self._self_pid = os.getpid()

    def _ensure_automation(self):
        """Initialize COM and CUIAutomation object lazily attached to Default desktop station."""
        _attach_default_desktop()
        if not UIAutomationClient:
            raise RuntimeError("Windows UIAutomationClient module is not available.")
        if not self._com_initialized:
            try:
                ctypes.windll.ole32.CoInitialize(None)
                self._com_initialized = True
            except Exception:
                pass
        if not self._automation:
            self._automation = comtypes.client.CreateObject(UIAutomationClient.CUIAutomation)

    def extract_element_metadata(self, element) -> UIElementMetadata:
        """Extract structured UIElementMetadata from a raw UIA element."""
        try:
            name = str(element.CurrentName or "")
        except Exception:
            name = ""

        try:
            ctrl_type_id = int(element.CurrentControlType)
            ctrl_type_str = CONTROL_TYPE_NAMES.get(ctrl_type_id, "Unknown")
        except Exception:
            ctrl_type_str = "Unknown"

        try:
            loc_ctrl_type = str(element.CurrentLocalizedControlType or "")
        except Exception:
            loc_ctrl_type = ""

        try:
            auto_id = str(element.CurrentAutomationId or "")
        except Exception:
            auto_id = ""

        try:
            cls_name = str(element.CurrentClassName or "")
        except Exception:
            cls_name = ""

        try:
            pid = int(element.CurrentProcessId or 0)
        except Exception:
            pid = 0

        proc_name = _get_process_name_from_pid(pid)

        try:
            enabled = bool(element.CurrentIsEnabled)
        except Exception:
            enabled = True

        try:
            hwnd = int(element.CurrentNativeWindowHandle or 0)
        except Exception:
            hwnd = 0

        # Extract bounding box
        rect_tuple = (0, 0, 0, 0)
        center_pt = (0, 0)
        try:
            rect = element.CurrentBoundingRectangle
            rect_tuple = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
            center_pt = (
                (rect_tuple[0] + rect_tuple[2]) // 2,
                (rect_tuple[1] + rect_tuple[3]) // 2
            )
        except Exception:
            pass

        # Check pattern support
        supported_patterns: List[str] = []
        selected_state = None

        try:
            pat_sel = element.GetCurrentPattern(UIAutomationClient.UIA_SelectionItemPatternId)
            if pat_sel:
                supported_patterns.append("SelectionItemPattern")
                sel_interface = pat_sel.QueryInterface(UIAutomationClient.IUIAutomationSelectionItemPattern)
                selected_state = bool(sel_interface.CurrentIsSelected)
        except Exception:
            pass

        try:
            pat_inv = element.GetCurrentPattern(UIAutomationClient.UIA_InvokePatternId)
            if pat_inv:
                supported_patterns.append("InvokePattern")
        except Exception:
            pass

        try:
            pat_tog = element.GetCurrentPattern(UIAutomationClient.UIA_TogglePatternId)
            if pat_tog:
                supported_patterns.append("TogglePattern")
        except Exception:
            pass

        try:
            pat_exp = element.GetCurrentPattern(UIAutomationClient.UIA_ExpandCollapsePatternId)
            if pat_exp:
                supported_patterns.append("ExpandCollapsePattern")
        except Exception:
            pass

        return UIElementMetadata(
            name=name,
            control_type=ctrl_type_str,
            localized_control_type=loc_ctrl_type,
            automation_id=auto_id,
            class_name=cls_name,
            process_id=pid,
            process_name=proc_name,
            enabled=enabled,
            selected=selected_state,
            supported_patterns=supported_patterns,
            bounding_box=rect_tuple,
            center_point=center_pt,
            handle=hwnd
        )

    def metadata_to_semantic_target(self, meta: UIElementMetadata, resolver_source: str = "uia", confidence: float = 1.0) -> SemanticTarget:
        """Convert UIElementMetadata to canonical SemanticTarget instance."""
        return SemanticTarget(
            target_name=meta.name,
            control_type=meta.control_type,
            automation_id=meta.automation_id,
            class_name=meta.class_name,
            process_id=meta.process_id,
            process_name=meta.process_name,
            window_handle=meta.handle,
            window_title=meta.name,
            enabled=meta.enabled,
            selected=meta.selected,
            bounding_rectangle=meta.bounding_box,
            center_point=meta.center_point,
            supported_patterns=meta.supported_patterns,
            resolver_source=resolver_source,
            confidence=confidence
        )

    def diagnose_application_uia(self, application_context: str) -> List[Dict[str, Any]]:
        """
        Enumerate and return structured UIA descendants of the target application window.
        Used for UIA diagnostic inspection.
        """
        self._ensure_automation()
        app_clean = application_context.strip().lower()

        root_element = self._automation.GetRootElement()
        cond_true = self._automation.CreateTrueCondition()
        children = root_element.FindAll(UIAutomationClient.TreeScope_Children, cond_true)

        target_root = None
        for i in range(children.Length):
            e = children.GetElement(i)
            meta = self.extract_element_metadata(e)
            if meta.process_id == self._self_pid:
                continue
            if app_clean in meta.name.lower() or app_clean in meta.process_name.lower():
                target_root = e
                break

        if not target_root:
            return []

        sub_elems = target_root.FindAll(UIAutomationClient.TreeScope_Subtree, cond_true)
        descendants: List[Dict[str, Any]] = []

        for i in range(min(sub_elems.Length, 500)):
            try:
                e = sub_elems.GetElement(i)
                meta = self.extract_element_metadata(e)
                descendants.append(meta.model_dump())
            except Exception:
                continue

        return descendants

    def resolve_element(
        self,
        target_name: str,
        control_type: Optional[str] = None,
        window_title: Optional[str] = None,
        process_name: Optional[str] = None,
        application_context: Optional[str] = None
    ) -> UIResolutionResult:
        """
        Locate target application window first and search its UIA subtree for matching element.
        Supports digit & alias semantic matching ('1' -> '1', 'One', 'num1Button').
        Excludes Nova's own Process ID (os.getpid()).
        """
        try:
            self._ensure_automation()
        except Exception as e:
            return UIResolutionResult(success=False, error=f"UIA initialization failed: {str(e)}")

        target_clean = target_name.strip().lower()
        app_clean = (application_context or process_name or window_title or "").strip().lower()

        # Step 1: Locate target application window element
        root_element = self._automation.GetRootElement()
        cond_true = self._automation.CreateTrueCondition()
        top_children = root_element.FindAll(UIAutomationClient.TreeScope_Children, cond_true)

        target_app_window = None
        for i in range(top_children.Length):
            e = top_children.GetElement(i)
            try:
                pid = int(e.CurrentProcessId or 0)
                if pid == self._self_pid:
                    continue
                name_low = str(e.CurrentName or "").strip().lower()
                proc_low = _get_process_name_from_pid(pid).lower()

                if app_clean:
                    if app_clean in name_low or app_clean in proc_low or name_low in app_clean or proc_low in app_clean or ("calc" in app_clean and ("calc" in name_low or "applicationframe" in proc_low)):
                        target_app_window = e
                        break
                elif "nova" not in name_low and "nova" not in proc_low and name_low != "":
                    # Fallback to top non-Nova window
                    target_app_window = e
            except Exception:
                continue

        search_root = target_app_window if target_app_window else root_element

        # Step 2: Search subtree elements
        try:
            elements_array = search_root.FindAll(UIAutomationClient.TreeScope_Subtree, cond_true)
            count = elements_array.Length
        except Exception as e:
            return UIResolutionResult(success=False, error=f"UIA tree search failed: {str(e)}")

        alias_list = SEMANTIC_ALIASES.get(target_clean, [target_clean])
        matches: List[Tuple[Any, UIElementMetadata]] = []

        for i in range(min(count, 500)):
            try:
                elem = elements_array.GetElement(i)
                meta = self.extract_element_metadata(elem)

                # EXCLUSION GUARD: Exclude Nova's own Process ID
                if meta.process_id == self._self_pid or "nova" in meta.process_name or "nova launcher" in meta.name.lower():
                    continue

                elem_name_clean = meta.name.strip().lower()
                auto_id_clean = meta.automation_id.strip().lower()

                # Semantic alias & name/automation_id matching
                name_match = any(
                    alias in elem_name_clean or elem_name_clean in alias or alias in auto_id_clean
                    for alias in alias_list
                )

                if name_match:
                    # Filter by control_type if specified
                    if control_type:
                        c_type_clean = control_type.strip().lower()
                        meta_type_clean = meta.control_type.strip().lower()
                        if c_type_clean not in meta_type_clean and meta_type_clean not in c_type_clean:
                            continue

                    matches.append((elem, meta))
            except Exception:
                continue

        if not matches:
            return UIResolutionResult(
                success=False,
                disambiguation_count=0,
                error=f"No UIA element matching '{target_name}' was found for application_context='{app_clean}'."
            )

        # Step 3: Disambiguation & Preference
        enabled_matches = [m for m in matches if m[1].enabled]
        candidates = enabled_matches if enabled_matches else matches

        exact_matches = [
            m for m in candidates
            if any(alias == m[1].name.strip().lower() or alias == m[1].automation_id.strip().lower() for alias in alias_list)
        ]
        best_match = exact_matches[0] if exact_matches else candidates[0]

        return UIResolutionResult(
            success=True,
            element=best_match[1],
            match_confidence=1.0 if exact_matches else 0.85,
            disambiguation_count=len(matches)
        )

    def invoke_element_pattern(
        self,
        target_name: str,
        control_type: Optional[str] = None,
        application_context: Optional[str] = None
    ) -> Tuple[bool, str, Optional[UIElementMetadata]]:
        """
        Primary Execution Mechanism: Direct UIA COM Pattern Invocation attached to 'Default' desktop station.
        Resolves element and executes SelectionItemPattern.Select(), InvokePattern.Invoke(), TogglePattern.Toggle(), or ExpandCollapsePattern.Expand().
        Returns (success: bool, detail_message: str, element_metadata: Optional[UIElementMetadata]).
        NO physical SendInput hardware mouse events are generated during UIA pattern invocation.
        """
        res = self.resolve_element(target_name=target_name, control_type=control_type, application_context=application_context)
        if not res.success or not res.element:
            return False, f"UIA resolution failed: {res.error}", None

        meta = res.element
        if not meta.enabled:
            return False, f"Target element '{meta.name}' is disabled.", meta

        # Find raw UIA element for pattern execution
        try:
            self._ensure_automation()
            cond_true = self._automation.CreateTrueCondition()
            root = self._automation.GetRootElement()
            children = root.FindAll(UIAutomationClient.TreeScope_Children, cond_true)

            target_app_window = None
            app_clean = (application_context or meta.process_name).strip().lower()
            for i in range(children.Length):
                e = children.GetElement(i)
                try:
                    pid = int(e.CurrentProcessId or 0)
                    if pid == self._self_pid:
                        continue
                    n_low = str(e.CurrentName or "").strip().lower()
                    p_low = _get_process_name_from_pid(pid).lower()
                    if app_clean in n_low or app_clean in p_low or n_low in app_clean or p_low in app_clean or ("calc" in app_clean and ("calc" in n_low or "applicationframe" in p_low)):
                        target_app_window = e
                        break
                except Exception:
                    continue

            search_root = target_app_window if target_app_window else root
            elems = search_root.FindAll(UIAutomationClient.TreeScope_Subtree, cond_true)

            meta_auto_id = meta.automation_id.strip().lower() if meta.automation_id else ""
            meta_name = meta.name.strip().lower() if meta.name else ""

            # Pass 1: Exact automation_id or exact name match
            for i in range(min(elems.Length, 500)):
                e = elems.GetElement(i)
                try:
                    if int(e.CurrentProcessId or 0) == self._self_pid:
                        continue
                    n_clean = str(e.CurrentName or "").strip().lower()
                    a_clean = str(e.CurrentAutomationId or "").strip().lower()
                    if (meta_auto_id and a_clean == meta_auto_id) or (meta_name and n_clean == meta_name):
                        target_elem = e
                        break
                except Exception:
                    continue

            # Pass 2: Fallback to exact alias match if Pass 1 found nothing
            if not target_elem:
                for i in range(min(elems.Length, 500)):
                    e = elems.GetElement(i)
                    try:
                        if int(e.CurrentProcessId or 0) == self._self_pid:
                            continue
                        n_clean = str(e.CurrentName or "").strip().lower()
                        a_clean = str(e.CurrentAutomationId or "").strip().lower()
                        if any(alias == n_clean or alias == a_clean for alias in alias_list):
                            target_elem = e
                            break
                    except Exception:
                        continue

            if not target_elem:
                return False, f"Target COM element reference lost for '{meta.name}'.", meta

            # 1. Try SelectionItemPattern for TabItems / RadioButtons
            try:
                pat_sel = target_elem.GetCurrentPattern(UIAutomationClient.UIA_SelectionItemPatternId)
                if pat_sel:
                    sel_pat = pat_sel.QueryInterface(UIAutomationClient.IUIAutomationSelectionItemPattern)
                    sel_pat.Select()
                    meta.selected = True
                    return True, f"Successfully executed SelectionItemPattern.Select() on '{meta.name}' ({meta.control_type}).", meta
            except Exception:
                pass

            # 2. Try InvokePattern for Buttons / MenuItems
            try:
                pat_inv = target_elem.GetCurrentPattern(UIAutomationClient.UIA_InvokePatternId)
                if pat_inv:
                    inv_pat = pat_inv.QueryInterface(UIAutomationClient.IUIAutomationInvokePattern)
                    inv_pat.Invoke()
                    return True, f"Successfully executed InvokePattern.Invoke() on '{meta.name}' ({meta.control_type}).", meta
            except Exception:
                pass

            # 3. Try TogglePattern for CheckBoxes
            try:
                pat_tog = target_elem.GetCurrentPattern(UIAutomationClient.UIA_TogglePatternId)
                if pat_tog:
                    tog_pat = pat_tog.QueryInterface(UIAutomationClient.IUIAutomationTogglePattern)
                    tog_pat.Toggle()
                    return True, f"Successfully executed TogglePattern.Toggle() on '{meta.name}' ({meta.control_type}).", meta
            except Exception:
                pass

            # 4. Try ExpandCollapsePattern for TreeItems / Dropdowns
            try:
                pat_exp = target_elem.GetCurrentPattern(UIAutomationClient.UIA_ExpandCollapsePatternId)
                if pat_exp:
                    exp_pat = pat_exp.QueryInterface(UIAutomationClient.IUIAutomationExpandCollapsePattern)
                    exp_pat.Expand()
                    return True, f"Successfully executed ExpandCollapsePattern.Expand() on '{meta.name}' ({meta.control_type}).", meta
            except Exception:
                pass

            return False, f"UIA element '{meta.name}' resolved, but exposes no usable COM invocation pattern.", meta
        except Exception as e:
            return False, f"UIA pattern invocation failed: {str(e)}", meta
