"""
Unit tests for PermissionEngine, AppResolver, and User Path Resolution.
"""

from pathlib import Path
import tempfile

from nova.permissions.level import PermissionLevel, ActionContext
from nova.permissions.engine import PermissionEngine
from nova.tools.app_resolver import AppResolver
from nova.tools.create_folder import CreateFolderInput, CreateFolderTool
from nova.config import Settings


def test_permission_level_ranks():
    assert PermissionEngine._level_rank(PermissionLevel.SAFE) == 1
    assert PermissionEngine._level_rank(PermissionLevel.REQUIRES_CONFIRMATION) == 2
    assert PermissionEngine._level_rank(PermissionLevel.DANGEROUS) == 3


def test_app_resolver_safe_apps():
    # Test Notepad
    res_notepad = AppResolver.resolve("notepad")
    assert res_notepad.is_allowed is True
    assert res_notepad.executable == "notepad.exe"

    res_notepad_exe = AppResolver.resolve("notepad.exe")
    assert res_notepad_exe.is_allowed is True

    # Test Calculator
    res_calc = AppResolver.resolve("calculator")
    assert res_calc.is_allowed is True
    assert res_calc.executable == "calc.exe"

    res_calc_short = AppResolver.resolve("calc")
    assert res_calc_short.is_allowed is True
    assert res_calc_short.executable == "calc.exe"

    res_calc_exe = AppResolver.resolve("calc.exe")
    assert res_calc_exe.is_allowed is True
    assert res_calc_exe.executable == "calc.exe"

    res_open_calc = AppResolver.resolve("Open Calculator")
    assert res_open_calc.is_allowed is True
    assert res_open_calc.executable == "calc.exe"


def test_app_resolver_blocked_command_interpreters():
    # Security requirement: Explicitly test CMD, PowerShell, Terminal variants
    blocked_inputs = [
        "cmd",
        "cmd.exe",
        "powershell",
        "powershell.exe",
        "pwsh",
        "pwsh.exe",
        "wt.exe",
        "Windows Terminal",
        "bash",
        "bash.exe",
        "wsl",
        "wsl.exe",
        "C:\\Windows\\System32\\cmd.exe",
        "C:\\Program Files\\PowerShell\\7\\pwsh.exe",
    ]

    for app_name in blocked_inputs:
        res = AppResolver.resolve(app_name)
        assert res.is_allowed is False, f"Expected '{app_name}' to be blocked, but was allowed."
        assert "blocked" in res.reason.lower() or "not permitted" in res.reason.lower()


def test_app_resolver_unknown_and_arbitrary_paths():
    # Reject unknown apps
    res_unknown = AppResolver.resolve("random_unknown_app_xyz")
    assert res_unknown.is_allowed is False
    assert "not in the validated" in res_unknown.reason

    # Reject arbitrary executable paths
    res_arbitrary = AppResolver.resolve("C:\\Users\\Public\\malicious.exe")
    assert res_arbitrary.is_allowed is False
    assert "not permitted" in res_arbitrary.reason or "arbitrary" in res_arbitrary.reason.lower()


def test_desktop_path_resolution_and_containment():
    # Verify Desktop resolves to actual user Desktop
    desktop_path = Settings.resolve_user_path("Desktop/NovaTest")
    expected_desktop = (Path.home() / "Desktop" / "NovaTest").resolve()
    assert desktop_path == expected_desktop

    # Verify path containment passes for user Desktop
    assert Settings.is_path_allowed(desktop_path) is True

    # Traversal/out-of-root paths remain blocked
    traversal_path = Path("C:\\Windows\\System32\\NovaTest")
    assert Settings.is_path_allowed(traversal_path) is False


def test_permission_engine_path_evaluation():
    engine = PermissionEngine()
    tool = CreateFolderTool()
    ctx = ActionContext()

    # System directory path -> DANGEROUS
    sys_args = CreateFolderInput(folder_path="C:\\Windows\\System32\\TestDir")
    perm_sys = engine.evaluate(tool, sys_args, ctx)
    assert perm_sys == PermissionLevel.DANGEROUS

    # User Desktop path -> REQUIRES_CONFIRMATION (default for folder creation)
    desktop_dir = str(Settings.USER_DESKTOP / "NovaTest")
    safe_args = CreateFolderInput(folder_path=desktop_dir)
    perm_safe = engine.evaluate(tool, safe_args, ctx)
    assert perm_safe == PermissionLevel.REQUIRES_CONFIRMATION
