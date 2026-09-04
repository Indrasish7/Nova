"""
Application Resolution Layer for Nova V0.1.

Maps friendly app names to validated executable commands or Windows App URIs.
Strictly blocks command interpreters, shell access, and arbitrary unverified paths.
"""

from typing import Optional, Dict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResolvedApp:
    """Resolved application details."""
    name: str
    executable: str
    is_allowed: bool
    reason: Optional[str] = None


class AppResolver:
    """Application resolver and allowlist manager."""

    # Explicit Allowlist for V0.1 (normalized name -> target executable)
    SAFE_APP_MAP: Dict[str, str] = {
        "notepad": "notepad.exe",
        "notepad.exe": "notepad.exe",
        "text editor": "notepad.exe",
        "calc": "calc.exe",
        "calc.exe": "calc.exe",
        "calculator": "calc.exe",
        "calculator.exe": "calc.exe",
        "explorer": "explorer.exe",
        "explorer.exe": "explorer.exe",
        "file explorer": "explorer.exe",
        "windows explorer": "explorer.exe",
        "paint": "mspaint.exe",
        "mspaint": "mspaint.exe",
        "mspaint.exe": "mspaint.exe",
        "edge": "msedge.exe",
        "msedge": "msedge.exe",
        "msedge.exe": "msedge.exe",
        "browser": "msedge.exe",
        "wordpad": "wordpad.exe",
        "wordpad.exe": "wordpad.exe",
        "control panel": "control.exe",
        "control": "control.exe",
        "control.exe": "control.exe",
        "task manager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe",
        "taskmgr.exe": "taskmgr.exe",
        "snipping tool": "snippingtool.exe",
        "snippingtool.exe": "snippingtool.exe",
    }

    # Explicitly Blocked Shell Interpreters, Command Tools & Executable Variants
    BLOCKED_PATTERNS = {
        "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe",
        "terminal", "windows terminal", "wt", "wt.exe", "bash", "bash.exe",
        "wsl", "wsl.exe", "sh", "sh.exe", "cscript", "cscript.exe",
        "wscript", "wscript.exe", "regedit", "regedit.exe", "conhost",
        "conhost.exe"
    }

    @classmethod
    def resolve(cls, app_name: str) -> ResolvedApp:
        """
        Resolve a requested application name against allowlist & blocklist.
        Returns ResolvedApp metadata.
        """
        if not app_name or not isinstance(app_name, str):
            return ResolvedApp(
                name=str(app_name),
                executable="",
                is_allowed=False,
                reason="Invalid or empty application name."
            )

        raw_clean = app_name.strip().lower()

        # Reject path separators or arbitrary executable paths (e.g. C:\foo\bar.exe or ./script.sh)
        if "/" in raw_clean or "\\" in raw_clean:
            # Check if it's a known blocked path or unverified path
            path_filename = Path(raw_clean).name.lower()
            if path_filename in cls.BLOCKED_PATTERNS or any(b in path_filename for b in ["cmd", "powershell", "terminal", "bash", "wsl"]):
                return ResolvedApp(
                    name=app_name,
                    executable="",
                    is_allowed=False,
                    reason=f"Command interpreter '{app_name}' is explicitly blocked for security reasons."
                )
            return ResolvedApp(
                name=app_name,
                executable="",
                is_allowed=False,
                reason=f"Arbitrary path execution '{app_name}' is not permitted."
            )

        # Normalize prefix/suffix (e.g. "open calculator", "launch notepad app")
        clean_name = raw_clean
        for prefix in ["open ", "launch ", "start ", "the "]:
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix):].strip()

        for suffix in [" app", " application"]:
            if clean_name.endswith(suffix):
                clean_name = clean_name[:-len(suffix)].strip()

        # Check blocklist explicitly against raw input, cleaned input, and filename
        if (
            raw_clean in cls.BLOCKED_PATTERNS
            or clean_name in cls.BLOCKED_PATTERNS
            or any(b in clean_name for b in ["cmd", "powershell", "pwsh", "terminal", "bash", "wsl"])
        ):
            return ResolvedApp(
                name=app_name,
                executable="",
                is_allowed=False,
                reason=f"Application or interpreter '{app_name}' is explicitly blocked for security reasons."
            )

        # Check exact safe allowlist map
        if clean_name in cls.SAFE_APP_MAP:
            return ResolvedApp(
                name=app_name,
                executable=cls.SAFE_APP_MAP[clean_name],
                is_allowed=True
            )

        # Partial matching within safe apps
        for key, exe in cls.SAFE_APP_MAP.items():
            if key in clean_name or clean_name in key:
                return ResolvedApp(
                    name=app_name,
                    executable=exe,
                    is_allowed=True
                )

        return ResolvedApp(
            name=app_name,
            executable="",
            is_allowed=False,
            reason=f"Application '{app_name}' is not in the validated V0.1 allowlist."
        )
