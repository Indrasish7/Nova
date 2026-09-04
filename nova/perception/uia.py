"""
Windows UI Automation Perception & Interaction Engine.

Provides native Windows UI Automation COM interfaces (UIAutomationCore.dll) for resolving
semantic desktop UI elements (TabItems, Buttons, Edits, MenuItems, CheckBoxes), extracting
element properties (Name, ControlType, AutomationId, ProcessName, BoundingRectangle, Enabled, Selected),
attaching to active user desktop station ("Default"), and executing direct UIA COM pattern invocations
(SelectionItemPattern.Select(), InvokePattern.Invoke(), TogglePattern.Toggle(), ExpandCollapsePattern.Expand()).
"""

import os
import re
import ctypes
from ctypes import wintypes
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path

from nova.perception.models import UIElementMetadata, UIResolutionResult, SemanticTarget, ResolutionStatus

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

# Semantic mappings for numeric digits and common controls
SEMANTIC_DIGITS: Dict[str, Dict[str, str]] = {
    "0": {"name": "zero", "auto_id": "num0button"},
    "1": {"name": "one", "auto_id": "num1button"},
    "2": {"name": "two", "auto_id": "num2button"},
    "3": {"name": "three", "auto_id": "num3button"},
    "4": {"name": "four", "auto_id": "num4button"},
    "5": {"name": "five", "auto_id": "num5button"},
    "6": {"name": "six", "auto_id": "num6button"},
    "7": {"name": "seven", "auto_id": "num7button"},
    "8": {"name": "eight", "auto_id": "num8button"},
    "9": {"name": "nine", "auto_id": "num9button"},
}

SEMANTIC_OPERATORS: Dict[str, Dict[str, str]] = {
    "+": {"name": "plus", "auto_id": "plusbutton"},
    "-": {"name": "minus", "auto_id": "minusbutton"},
    "*": {"name": "multiply by", "auto_id": "multiplybutton"},
    "/": {"name": "divide by", "auto_id": "dividebutton"},
    "=": {"name": "equals", "auto_id": "equalbutton"},
    "c": {"name": "clear", "auto_id": "clearbutton"},
    "ce": {"name": "clear entry", "auto_id": "clearentrybutton"},
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


def is_current_process_elevated() -> bool:
    """Check if the current process is running with administrative privileges (High Integrity)."""
    try:
        advapi32 = ctypes.windll.advapi32
        kernel32 = ctypes.windll.kernel32
        hToken = wintypes.HANDLE()
        if advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(hToken)):
            elevation = wintypes.DWORD()
            ret_len = wintypes.DWORD()
            if advapi32.GetTokenInformation(hToken, 20, ctypes.byref(elevation), ctypes.sizeof(elevation), ctypes.byref(ret_len)):
                kernel32.CloseHandle(hToken)
                return bool(elevation.value)
            kernel32.CloseHandle(hToken)
    except Exception:
        pass
    return False


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
            if meta.process_id == self._self_pid or "taskbar" in meta.name.lower():
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
        Enforces:
        - Exact AutomationId > Exact Name > Exact Semantic Alias > Secondary Whole-word heuristic
        - ControlType compatibility (e.g. Button for numeric digits)
        - Stable candidate deduplication
        - Fail-closed ambiguity guard (AMBIGUOUS status if > 1 candidate)
        """
        try:
            self._ensure_automation()
        except Exception as e:
            return UIResolutionResult(
                success=False,
                status=ResolutionStatus.ERROR,
                error=f"UIA initialization failed: {str(e)}"
            )

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

                # Always exclude the Windows taskbar
                if "taskbar" in name_low:
                    continue

                if app_clean:
                    is_tm = ("task" in app_clean and ("mgr" in app_clean or "manag" in app_clean)) or app_clean == "taskmgr"
                    is_calc = "calc" in app_clean

                    if is_tm:
                        if proc_low == "taskmgr.exe" or "task manager" in name_low or "taskmgr" in name_low:
                            target_app_window = e
                            break
                    elif is_calc:
                        if "calc" in name_low or "calc" in proc_low or "applicationframe" in proc_low:
                            target_app_window = e
                            break
                    elif (app_clean in name_low or app_clean in proc_low or 
                          name_low in app_clean or proc_low in app_clean):
                        target_app_window = e
                        break
                elif "nova" not in name_low and "nova" not in proc_low and name_low != "":
                    target_app_window = e
            except Exception:
                continue

        # Fallback window discovery via Win32 FindWindowW / EnumWindows if root children missed it
        if app_clean and not target_app_window:
            try:
                user32 = ctypes.windll.user32
                known_titles = [
                    app_clean,
                    app_clean.title(),
                    "Task Manager" if ("task" in app_clean or "mgr" in app_clean) else None,
                    "Calculator" if ("calc" in app_clean) else None,
                    "Notepad" if ("note" in app_clean) else None
                ]
                for title in known_titles:
                    if not title:
                        continue
                    hwnd_cand = user32.FindWindowW(None, title)
                    if hwnd_cand and user32.IsWindowVisible(hwnd_cand):
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd_cand, ctypes.byref(pid))
                        if pid.value != self._self_pid:
                            target_app_window = self._automation.ElementFromHandle(hwnd_cand)
                            break

                if not target_app_window:
                    matched_hwnd = None
                    def _enum_win_cb(h, _):
                        nonlocal matched_hwnd
                        if not user32.IsWindowVisible(h):
                            return True
                        length = user32.GetWindowTextLengthW(h)
                        if length == 0:
                            return True
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(h, buf, length + 1)
                        t_low = buf.value.strip().lower()
                        if "taskbar" in t_low:
                            return True
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                        if pid.value == self._self_pid:
                            return True
                        p_low = _get_process_name_from_pid(pid.value).lower()

                        is_tm = ("task" in app_clean and ("mgr" in app_clean or "manag" in app_clean)) or app_clean == "taskmgr"
                        is_calc = "calc" in app_clean

                        if is_tm:
                            if p_low == "taskmgr.exe" or "task manager" in t_low or "taskmgr" in t_low:
                                matched_hwnd = h
                                return False
                        elif is_calc:
                            if "calc" in t_low or "calc" in p_low:
                                matched_hwnd = h
                                return False
                        elif (app_clean in t_low or app_clean in p_low or 
                              t_low in app_clean or p_low in app_clean):
                            matched_hwnd = h
                            return False
                        return True

                    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
                    user32.EnumWindows(EnumWindowsProc(_enum_win_cb), 0)
                    if matched_hwnd:
                        target_app_window = self._automation.ElementFromHandle(matched_hwnd)
            except Exception as ex:
                logger.debug(f"[UIA] Fallback window discovery error: {ex}")

        if app_clean and not target_app_window:
            return UIResolutionResult(
                success=False,
                status=ResolutionStatus.UNAVAILABLE,
                disambiguation_count=0,
                error=f"Target application window for '{app_clean}' was not found or is unavailable."
            )

        search_root = target_app_window if target_app_window else root_element

        # Step 2: Search subtree elements
        try:
            elements_array = search_root.FindAll(UIAutomationClient.TreeScope_Subtree, cond_true)
            count = elements_array.Length
        except Exception as e:
            err_str = str(e)
            if "0x80070005" in err_str or "-2147024891" in err_str or "Access is denied" in err_str:
                return UIResolutionResult(
                    success=False,
                    status=ResolutionStatus.UNAVAILABLE,
                    disambiguation_count=0,
                    error=(
                        f"ELEVATION_REQUIRED: Target application '{app_clean or 'application'}' is running with elevated Administrator privileges. "
                        "Windows User Interface Privilege Isolation (UIPI) prevents interaction unless Nova is launched with 'Run as Administrator'."
                    )
                )
            return UIResolutionResult(
                success=False,
                status=ResolutionStatus.ERROR,
                error=f"UIA tree search failed: {err_str}"
            )

        # Check if target is an elevated process (e.g. taskmgr.exe) while Nova is running non-elevated
        if target_app_window:
            target_pid = int(target_app_window.CurrentProcessId or 0)
            target_pname = _get_process_name_from_pid(target_pid).lower()
            if target_pname == "taskmgr.exe" and count <= 2 and not is_current_process_elevated():
                return UIResolutionResult(
                    success=False,
                    status=ResolutionStatus.UNAVAILABLE,
                    disambiguation_count=0,
                    error=(
                        "ELEVATION_REQUIRED: Task Manager (taskmgr.exe) runs with elevated Administrator privileges. "
                        "Windows User Interface Privilege Isolation (UIPI) blocks access unless Nova is launched with 'Run as Administrator'."
                    )
                )

        # Base target extraction (e.g. "1 button" -> "1", "Performance tab" -> "performance")
        base_clean = target_clean
        inferred_control_type = None
        for suffix, inferred_type in [
            (" button", "Button"),
            (" tab", "TabItem"),
            (" item", None),
            (" icon", None),
            (" link", "Hyperlink"),
            (" checkbox", "CheckBox"),
            (" menu", "MenuItem")
        ]:
            if base_clean.endswith(suffix):
                base_clean = base_clean[:-len(suffix)].strip()
                if not inferred_control_type:
                    inferred_control_type = inferred_type
                break

        # Semantic aliases and expected control type
        digit_info = SEMANTIC_DIGITS.get(target_clean) or SEMANTIC_DIGITS.get(base_clean)
        op_info = SEMANTIC_OPERATORS.get(target_clean) or SEMANTIC_OPERATORS.get(base_clean)
        alias_set = set(SEMANTIC_ALIASES.get(target_clean, [target_clean]))
        alias_set.update(SEMANTIC_ALIASES.get(base_clean, [base_clean]))
        alias_set.add(target_clean)
        alias_set.add(base_clean)
        alias_list = list(alias_set)

        expected_control_type = control_type or inferred_control_type
        semantic_name = None
        semantic_auto_id = None
        if digit_info:
            semantic_name = digit_info["name"]
            semantic_auto_id = digit_info["auto_id"]
            if not expected_control_type:
                expected_control_type = "Button"
        elif op_info:
            semantic_name = op_info["name"]
            semantic_auto_id = op_info["auto_id"]
            if not expected_control_type:
                expected_control_type = "Button"

        seen_keys = set()
        p1_candidates: List[Tuple[Any, UIElementMetadata]] = []
        p2_candidates: List[Tuple[Any, UIElementMetadata]] = []
        p3_candidates: List[Tuple[Any, UIElementMetadata]] = []
        p4_candidates: List[Tuple[Any, UIElementMetadata]] = []

        for i in range(min(count, 500)):
            try:
                elem = elements_array.GetElement(i)
                meta = self.extract_element_metadata(elem)

                # EXCLUSION GUARD: Exclude Nova's own Process ID & Launcher
                if meta.process_id == self._self_pid or "nova" in meta.process_name or "nova launcher" in meta.name.lower():
                    continue

                # Candidate Deduplication: deduplicate by process_id, automation_id, control_type, name, bounding_box
                dedup_key = (meta.process_id, meta.automation_id, meta.control_type, meta.name, meta.bounding_box)
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)

                elem_name_clean = meta.name.strip().lower()
                auto_id_clean = meta.automation_id.strip().lower()

                # Guard: Never match empty names / IDs
                if not elem_name_clean and not auto_id_clean:
                    continue

                # ControlType Compatibility Check
                if expected_control_type:
                    req_type = expected_control_type.strip().lower()
                    meta_type = meta.control_type.strip().lower()
                    compatible_tabs = {"tabitem", "tab", "listitem", "button"}
                    if req_type in {"tabitem", "tab"} and meta_type in compatible_tabs:
                        pass
                    elif req_type in {"button"} and meta_type in {"button", "splitbutton", "hyperlink"}:
                        pass
                    elif req_type != meta_type and req_type not in meta_type:
                        continue

                # Priority 1: Exact AutomationId match
                p1_match = False
                if auto_id_clean:
                    if (
                        auto_id_clean == target_clean or
                        auto_id_clean == base_clean or
                        (semantic_auto_id and auto_id_clean == semantic_auto_id) or
                        (auto_id_clean in alias_list)
                    ):
                        p1_match = True

                # Priority 2: Exact UIA Name match
                p2_match = False
                if elem_name_clean:
                    if (
                        elem_name_clean == target_clean or
                        elem_name_clean == base_clean or
                        (semantic_name and elem_name_clean == semantic_name) or
                        (elem_name_clean in alias_list)
                    ):
                        p2_match = True

                # Priority 3: Exact Semantic Alias match
                p3_match = False
                if not p1_match and not p2_match:
                    if any(alias == elem_name_clean or alias == auto_id_clean for alias in alias_list):
                        p3_match = True

                # Priority 4: Secondary heuristic — Whole-word boundary match (len > 2 only)
                p4_match = False
                if not (p1_match or p2_match or p3_match):
                    for probe in [target_clean, base_clean]:
                        if len(probe) > 2 and elem_name_clean:
                            word_pattern = rf"\b{re.escape(probe)}\b"
                            if re.search(word_pattern, elem_name_clean):
                                p4_match = True
                                break

                if p1_match:
                    p1_candidates.append((elem, meta))
                elif p2_match:
                    p2_candidates.append((elem, meta))
                elif p3_match:
                    p3_candidates.append((elem, meta))
                elif p4_match:
                    p4_candidates.append((elem, meta))
            except Exception:
                continue

        # Select highest non-empty priority tier
        candidates = p1_candidates or p2_candidates or p3_candidates or p4_candidates

        if not candidates:
            return UIResolutionResult(
                success=False,
                status=ResolutionStatus.NOT_FOUND,
                disambiguation_count=0,
                error=f"No UIA element matching '{target_name}' was found for application_context='{app_clean}'."
            )

        # Check disabled state
        all_disabled = all(not c[1].enabled for c in candidates)
        if all_disabled:
            disabled_meta = candidates[0][1]
            return UIResolutionResult(
                success=False,
                status=ResolutionStatus.DISABLED,
                element=disabled_meta,
                candidates=[c[1] for c in candidates],
                disambiguation_count=len(candidates),
                error=f"Target UI element '{target_name}' is disabled and cannot be invoked."
            )

        # Filter to enabled candidates
        enabled_candidates = [c for c in candidates if c[1].enabled]

        # Ambiguity Guard: Fail Closed if multiple distinct candidates matched
        if len(enabled_candidates) > 1:
            err_msg = (
                f"AMBIGUOUS_TARGET: Multiple UI elements ({len(enabled_candidates)}) matched '{target_name}' "
                f"in {app_clean or 'application'}. No action was executed. Please provide additional context."
            )
            return UIResolutionResult(
                success=False,
                status=ResolutionStatus.AMBIGUOUS,
                candidates=[c[1] for c in enabled_candidates],
                disambiguation_count=len(enabled_candidates),
                error=err_msg
            )

        # Exactly one candidate resolved
        resolved_meta = enabled_candidates[0][1]
        return UIResolutionResult(
            success=True,
            status=ResolutionStatus.SUCCESS,
            element=resolved_meta,
            candidates=[resolved_meta],
            match_confidence=1.0,
            disambiguation_count=1
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

            target_elem = None
            # Pass 1: Exact automation_id match
            if meta_auto_id:
                for i in range(min(elems.Length, 500)):
                    e = elems.GetElement(i)
                    try:
                        if int(e.CurrentProcessId or 0) == self._self_pid:
                            continue
                        a_clean = str(e.CurrentAutomationId or "").strip().lower()
                        if a_clean == meta_auto_id:
                            target_elem = e
                            break
                    except Exception:
                        continue

            # Pass 2: Exact name match
            if not target_elem and meta_name:
                for i in range(min(elems.Length, 500)):
                    e = elems.GetElement(i)
                    try:
                        if int(e.CurrentProcessId or 0) == self._self_pid:
                            continue
                        n_clean = str(e.CurrentName or "").strip().lower()
                        if n_clean == meta_name:
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
