"""
Permission Engine.

Evaluates permissions for tool execution dynamically based on tool parameters,
system paths, Win32 process identity, UIA element metadata, and risk-based security policies.
"""

from pathlib import Path
import ctypes
from ctypes import wintypes
from typing import Optional, Dict, Any, List
from nova.permissions.level import PermissionLevel, ActionContext
from nova.config import Settings


PROTECTED_PROCESSES: List[str] = [
    "taskmgr.exe",
    "regedit.exe",
    "mmc.exe",        # hosts secpol.msc, services.msc, devmgmt.msc, etc.
    "cmd.exe",
    "powershell.exe",
    "wt.exe",
    "services.exe",
    "lsass.exe",
]

CONSEQUENTIAL_KEYWORDS: List[str] = [
    "delete", "remove", "send", "submit", "purchase", "buy", "install", 
    "upload", "download", "save", "login", "sign in", "sign out", "close", "exit"
]


def get_foreground_process_name() -> str:
    """Retrieve executable image name of current foreground window using Win32 API."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "unknown"

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return "unknown"

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h_process:
            return "unknown"

        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
                full_path = buf.value
                return Path(full_path).name.lower()
        finally:
            kernel32.CloseHandle(h_process)
    except Exception:
        pass
    return "unknown"


class PermissionEngine:
    """Dynamic permission evaluator for Nova actions."""

    def __init__(self):
        self.app_resolver = None

    @staticmethod
    def _level_rank(level: PermissionLevel) -> int:
        """Return numeric rank for permission comparison."""
        ranks = {
            PermissionLevel.SAFE: 1,
            PermissionLevel.REQUIRES_CONFIRMATION: 2,
            PermissionLevel.DANGEROUS: 3,
            PermissionLevel.BLOCKED: 4,
        }
        return ranks.get(level, 4)

    def evaluate(
        self,
        tool: Any,
        args: Any,
        context: Optional[ActionContext] = None,
        uia_element: Optional[Any] = None
    ) -> PermissionLevel:
        """
        Evaluate permission level for a given tool invocation.
        Inspects tool default permission, arguments, paths, UIA metadata, and Win32 target process identity.
        """
        tool_name = tool.name.lower()

        # Check for tool-specific permission override method
        if hasattr(tool, "evaluate_permission"):
            try:
                custom_perm = tool.evaluate_permission(args, context or ActionContext())
                if custom_perm != tool.default_permission:
                    return custom_perm
            except Exception:
                pass

        # Evaluate UIA element metadata if available
        if uia_element:
            # 1. Disabled element protection
            if not getattr(uia_element, "enabled", True):
                return PermissionLevel.BLOCKED

            # 2. Protected process identity check
            proc_name = (getattr(uia_element, "process_name", "") or "unknown").lower()
            if proc_name in PROTECTED_PROCESSES:
                return PermissionLevel.DANGEROUS

            # 3. Screen bounds check on element center
            center_x, center_y = getattr(uia_element, "center_point", (0, 0))
            from nova.tools.mouse import validate_screen_bounds
            bounds_err = validate_screen_bounds(center_x, center_y)
            if bounds_err:
                return PermissionLevel.BLOCKED

            # 4. Check for consequential action keywords
            elem_name = (getattr(uia_element, "target_name", None) or getattr(uia_element, "name", "") or getattr(args, "target_name", "") or "").lower()
            target_desc = (getattr(args, "target_description", "") or "").lower()
            combined_desc = f"{elem_name} {target_desc}"
            if any(kw in combined_desc for kw in CONSEQUENTIAL_KEYWORDS):
                return PermissionLevel.REQUIRES_CONFIRMATION

            # 5. Check Interaction Mode (BALANCED vs STRICT)
            mode = Settings.INTERACTION_MODE
            if mode == "STRICT":
                return PermissionLevel.REQUIRES_CONFIRMATION

            # 6. BALANCED Mode Low-Risk Classification
            if proc_name in ["calc.exe", "calculatorapp.exe", "calculator.exe"]:
                return PermissionLevel.SAFE

            if proc_name in ["notepad.exe", "mspaint.exe", "explorer.exe"]:
                return PermissionLevel.SAFE

            return PermissionLevel.REQUIRES_CONFIRMATION

        # Mouse & Semantic tool specific evaluations
        if tool_name in ["mouse_move", "mouse_click", "mouse_double_click", "mouse_scroll", "semantic_click"]:
            x = getattr(args, "x", None)
            y = getattr(args, "y", None)

            # 1. Check bounds validation if coordinates are present
            if x is not None and y is not None:
                from nova.tools.mouse import validate_screen_bounds
                bounds_err = validate_screen_bounds(x, y)
                if bounds_err:
                    return PermissionLevel.BLOCKED

            # 2. Check target process identity
            proc_name = get_foreground_process_name()
            app_ctx = (getattr(args, "application_context", "") or "").lower().strip()
            target_desc = (
                getattr(args, "target_name", "") or 
                getattr(args, "target_description", "") or ""
            ).lower().strip()

            is_protected = (
                proc_name in PROTECTED_PROCESSES or
                any(p.replace(".exe", "") in app_ctx for p in PROTECTED_PROCESSES) or
                any(p.replace(".exe", "") in target_desc for p in PROTECTED_PROCESSES) or
                ("task manager" in target_desc or "task manager" in app_ctx) or
                ("taskmgr" in target_desc or "taskmgr" in app_ctx)
            )
            if is_protected:
                return PermissionLevel.DANGEROUS

            # mouse_move is always SAFE
            if tool_name == "mouse_move":
                return PermissionLevel.SAFE

            # 3. Check for consequential action keywords in target description
            if any(kw in target_desc for kw in CONSEQUENTIAL_KEYWORDS):
                return PermissionLevel.REQUIRES_CONFIRMATION

            # 4. Check Interaction Mode (BALANCED vs STRICT)
            mode = Settings.INTERACTION_MODE
            if mode == "STRICT":
                return PermissionLevel.REQUIRES_CONFIRMATION

            # 5. BALANCED Policy: Deterministic Low-Risk Classification
            if proc_name in ["calc.exe", "calculatorapp.exe", "calculator.exe"] or any(c in app_ctx for c in ["calculator", "calc"]):
                return PermissionLevel.SAFE

            if proc_name in ["notepad.exe", "mspaint.exe", "explorer.exe"] or any(c in app_ctx for c in ["notepad", "paint", "explorer"]):
                return PermissionLevel.SAFE

            return PermissionLevel.REQUIRES_CONFIRMATION

        # Path-based tools evaluation
        target_path_str = None
        if hasattr(args, "folder_path"):
            target_path_str = args.folder_path
        elif hasattr(args, "target_dir"):
            target_path_str = args.target_dir
        elif hasattr(args, "file_path"):
            target_path_str = args.file_path

        if target_path_str:
            target_path = Settings.resolve_user_path(target_path_str)

            # Check system folder restrictions
            path_str = str(target_path).lower()
            if any(sys_dir in path_str for sys_dir in ["system32", "windows\\system", "program files"]):
                return PermissionLevel.DANGEROUS

            # Check root containment
            if not Settings.is_path_allowed(target_path):
                return PermissionLevel.REQUIRES_CONFIRMATION

        return tool.default_permission
