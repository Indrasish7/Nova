"""
Unit tests for all initial Nova tools.
"""

from pathlib import Path
import tempfile
import pytest

from nova.permissions.level import ActionContext, PermissionLevel
from nova.tools.open_app import OpenAppTool, OpenAppInput
from nova.tools.create_folder import CreateFolderTool, CreateFolderInput
from nova.tools.find_file import FindFileTool, FindFileInput
from nova.tools.screenshot import TakeScreenshotTool, TakeScreenshotInput


def test_open_app_tool_notepad_and_calculator():
    tool = OpenAppTool()
    ctx = ActionContext()

    # Test Notepad evaluation
    notepad_input = OpenAppInput(app_name="notepad")
    assert tool.evaluate_permission(notepad_input, ctx) == PermissionLevel.SAFE

    # Test Calculator evaluation & resolution
    calc_input = OpenAppInput(app_name="calculator")
    assert tool.evaluate_permission(calc_input, ctx) == PermissionLevel.SAFE

    calc_short = OpenAppInput(app_name="calc")
    assert tool.evaluate_permission(calc_short, ctx) == PermissionLevel.SAFE


def test_open_app_tool_blocked_command_interpreters():
    tool = OpenAppTool()
    ctx = ActionContext()

    # Blocked app validation: CMD, PowerShell, Terminal
    for app in ["cmd", "cmd.exe", "powershell", "powershell.exe", "wt.exe", "Windows Terminal"]:
        app_input = OpenAppInput(app_name=app)
        perm = tool.evaluate_permission(app_input, ctx)
        assert perm == PermissionLevel.DANGEROUS

        res = tool.execute(app_input, ctx)
        assert res.success is False
        assert "not permitted" in res.error.lower() or "blocked" in res.error.lower()


def test_create_folder_tool():
    tool = CreateFolderTool()
    ctx = ActionContext()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        new_folder = Path(tmpdir) / "sub_folder_test"
        args = CreateFolderInput(folder_path=str(new_folder))
        
        result = tool.execute(args, ctx)
        assert result.success is True
        assert new_folder.exists()
        assert new_folder.is_dir()

        # Test idempotency (creating existing folder)
        result_again = tool.execute(args, ctx)
        assert result_again.success is True
        assert "already exists" in result_again.output


def test_find_file_tool():
    tool = FindFileTool()
    ctx = ActionContext()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = Path(tmpdir) / "sample_data.txt"
        test_file.write_text("Hello Nova Test", encoding="utf-8")

        args = FindFileInput(pattern="sample_*.txt", search_root=tmpdir)
        result = tool.execute(args, ctx)

        assert result.success is True
        assert isinstance(result.output, list)
        assert len(result.output) >= 1

        file_metadata = result.output[0]
        # Verify required metadata fields
        assert "filename" in file_metadata
        assert file_metadata["filename"] == "sample_data.txt"
        assert "absolute_path" in file_metadata
        assert "extension" in file_metadata
        assert file_metadata["extension"] == ".txt"
        assert "size_bytes" in file_metadata
        assert file_metadata["size_bytes"] > 0
        assert "created_at" in file_metadata
        assert "modified_at" in file_metadata


def test_take_screenshot_tool():
    tool = TakeScreenshotTool()
    ctx = ActionContext()

    args = TakeScreenshotInput(filename_prefix="unittest")
    result = tool.execute(args, ctx)

    assert result.success is True
    assert isinstance(result.output, dict)
    
    metadata = result.output
    assert "image_path" in metadata
    assert "width" in metadata
    assert "height" in metadata
    assert "timestamp" in metadata
    assert "bounds" in metadata

    saved_path = Path(metadata["image_path"])
    assert saved_path.exists()
    assert saved_path.suffix == ".png"
