"""
Unit tests for Nova Phase B Controlled Mouse Interaction & Risk-Based Security Policy.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from nova.tools.mouse import (
    MouseMoveTool, MouseClickTool, MouseDoubleClickTool, MouseScrollTool,
    MouseMoveInput, MouseClickInput, MouseDoubleClickInput, MouseScrollInput,
    validate_screen_bounds, transform_coordinates
)
from nova.perception.screen import ScreenPerception
from nova.perception.verifier import ActionVerifier, VerificationOutcome
from nova.permissions.engine import PermissionEngine, PROTECTED_PROCESSES, get_foreground_process_name
from nova.permissions.level import PermissionLevel, ActionContext
from nova.tools.registry import create_default_registry
from nova.runtime.agent import Agent
from nova.providers.mock import MockModelProvider
from nova.providers.base import ModelResponse, ToolCallRequest
from nova.config import Settings


def test_screen_bounds_validation_0_indexed():
    """Verify 0-indexed bounds checking (0 <= X <= W-1, 0 <= Y <= H-1)."""
    disp = ScreenPerception().get_display_info()
    
    # Valid coordinates inside display bounds
    assert validate_screen_bounds(0, 0) is None
    assert validate_screen_bounds(100, 100) is None
    assert validate_screen_bounds(disp.width - 1, disp.height - 1) is None

    # Negative coordinates
    err1 = validate_screen_bounds(-1, 50)
    assert err1 is not None
    assert "outside valid display bounds" in err1

    err2 = validate_screen_bounds(50, -5)
    assert err2 is not None
    assert "outside valid display bounds" in err2

    # Out of bounds coordinates (W or H)
    err3 = validate_screen_bounds(disp.width, 100)
    assert err3 is not None
    assert "outside valid display bounds" in err3

    err4 = validate_screen_bounds(100, disp.height)
    assert err4 is not None
    assert "outside valid display bounds" in err4


def test_coordinate_transformation_and_sendinput_normalization():
    """Verify transform_coordinates scaling from image space to physical screen and SendInput normalization."""
    # Test 1:1 screen mapping (2560x1600 image to 2560x1600 display)
    with patch.object(ScreenPerception, "get_display_info", return_value=MagicMock(width=2560, height=1600)):
        tx, ty, nx, ny, dw, dh = transform_coordinates(250, 710, img_w=2560, img_h=1600)
        assert tx == 250
        assert ty == 710
        assert nx == round(250 * 65535 / 2559)
        assert ny == round(710 * 65535 / 1599)

    # Test scaling from scaled image space (1280x800 image to 2560x1600 display)
    with patch.object(ScreenPerception, "get_display_info", return_value=MagicMock(width=2560, height=1600)):
        tx, ty, nx, ny, dw, dh = transform_coordinates(125, 355, img_w=1280, img_h=800)
        assert tx == round(125 * 2559 / 1279)
        assert ty == round(355 * 1599 / 799)


def test_mouse_move_tool_execution():
    """Verify MouseMoveTool moves cursor and validates position."""
    tool = MouseMoveTool()
    ctx = ActionContext()
    
    args = MouseMoveInput(x=150, y=150, target_description="Test location")
    res = tool.execute(args, ctx)

    assert res.success is True
    assert "Successfully moved cursor" in res.output
    assert res.metadata["transformed_x"] == 150
    assert res.metadata["transformed_y"] == 150


def test_mouse_click_and_scroll_tools_execution():
    """Verify MouseClickTool and MouseScrollTool execute schemas correctly."""
    ctx = ActionContext()

    click_tool = MouseClickTool()
    click_res = click_tool.execute(MouseClickInput(x=200, y=200, button="left"), ctx)
    assert click_res.success is True

    dbl_tool = MouseDoubleClickTool()
    dbl_res = dbl_tool.execute(MouseDoubleClickInput(x=200, y=200, button="left"), ctx)
    assert dbl_res.success is True

    scroll_tool = MouseScrollTool()
    scroll_res = scroll_tool.execute(MouseScrollInput(x=200, y=200, clicks=2, direction="down"), ctx)
    assert scroll_res.success is True


def test_out_of_bounds_click_rejected():
    """Verify out-of-bounds click attempt is rejected by tool."""
    tool = MouseClickTool()
    ctx = ActionContext()
    
    res = tool.execute(MouseClickInput(x=-10, y=99999), ctx)
    assert res.success is False
    assert "outside valid display bounds" in res.error


@patch("nova.permissions.engine.get_foreground_process_name", return_value="calc.exe")
def test_calculator_low_risk_click_is_safe_under_balanced_mode(mock_proc):
    """Verify Calculator number button clicks evaluate to SAFE under BALANCED mode."""
    engine = PermissionEngine()
    ctx = ActionContext()
    click_tool = MouseClickTool()

    perm = engine.evaluate(click_tool, MouseClickInput(x=100, y=100, target_description="Button 1"), ctx)
    assert perm == PermissionLevel.SAFE


@patch("nova.permissions.engine.get_foreground_process_name", return_value="notepad.exe")
def test_consequential_target_requires_confirmation(mock_proc):
    """Verify clicks on consequential keywords (e.g. Delete, Submit, Save) require confirmation."""
    engine = PermissionEngine()
    ctx = ActionContext()
    click_tool = MouseClickTool()

    perm1 = engine.evaluate(click_tool, MouseClickInput(x=100, y=100, target_description="Delete File"), ctx)
    assert perm1 == PermissionLevel.REQUIRES_CONFIRMATION

    perm2 = engine.evaluate(click_tool, MouseClickInput(x=100, y=100, target_description="Submit Order"), ctx)
    assert perm2 == PermissionLevel.REQUIRES_CONFIRMATION


@patch("nova.permissions.engine.get_foreground_process_name", return_value="taskmgr.exe")
def test_protected_process_rated_dangerous(mock_proc):
    """Verify targeting protected system process (taskmgr.exe, regedit.exe, mmc.exe) rates action DANGEROUS."""
    engine = PermissionEngine()
    ctx = ActionContext()
    click_tool = MouseClickTool()

    perm = engine.evaluate(click_tool, MouseClickInput(x=100, y=100, target_description="Harmless Button"), ctx)
    assert perm == PermissionLevel.DANGEROUS


def test_out_of_bounds_rated_blocked():
    """Verify out-of-bounds coordinates evaluate to BLOCKED by PermissionEngine."""
    engine = PermissionEngine()
    ctx = ActionContext()
    click_tool = MouseClickTool()

    perm = engine.evaluate(click_tool, MouseClickInput(x=-50, y=9999), ctx)
    assert perm == PermissionLevel.BLOCKED


def test_agent_safe_action_does_not_trigger_confirmation_callback():
    """Verify SAFE mouse action executes without prompting confirmation callback."""
    mock_provider = MagicMock()
    mock_provider.supports_capability.return_value = True

    # Turn 1: tool call, Turn 2: final text
    mock_provider.generate.side_effect = [
        ModelResponse(tool_calls=[ToolCallRequest(id="c1", name="mouse_move", arguments={"x": 100, "y": 100})]),
        ModelResponse(text="Done moving mouse.")
    ]
    agent = Agent(provider=mock_provider)
    
    cb_called = False
    def mock_cb(tool, args, perm):
        nonlocal cb_called
        cb_called = True
        return True

    agent.set_confirmation_callback(mock_cb)

    with patch("nova.permissions.engine.get_foreground_process_name", return_value="calc.exe"):
        res = agent.run("Move cursor to 100, 100")
        assert res.success is True
        assert cb_called is False


def test_agent_requires_confirmation_action_triggers_callback():
    """Verify REQUIRES_CONFIRMATION mouse action triggers confirmation callback."""
    mock_provider = MagicMock()
    mock_provider.supports_capability.return_value = True

    mock_provider.generate.side_effect = [
        ModelResponse(tool_calls=[ToolCallRequest(id="c2", name="mouse_click", arguments={"x": 100, "y": 100, "target_description": "Submit"})]),
        ModelResponse(text="Clicked submit button.")
    ]
    agent = Agent(provider=mock_provider)
    
    cb_called = False
    def mock_cb(tool, args, perm):
        nonlocal cb_called
        cb_called = True
        return True

    agent.set_confirmation_callback(mock_cb)

    with patch("nova.permissions.engine.get_foreground_process_name", return_value="unknown.exe"):
        with patch.object(PermissionEngine, "evaluate", return_value=PermissionLevel.REQUIRES_CONFIRMATION):
            res = agent.run("Click the Submit button")
            assert cb_called is True


def test_blocked_action_cannot_reach_execution():
    """Verify BLOCKED action is rejected by Agent before tool execution."""
    mock_provider = MagicMock()
    mock_provider.supports_capability.return_value = True

    mock_provider.generate.return_value = ModelResponse(
        tool_calls=[ToolCallRequest(id="c3", name="mouse_click", arguments={"x": -50, "y": 9999})]
    )
    agent = Agent(provider=mock_provider)
    
    with patch.object(PermissionEngine, "evaluate", return_value=PermissionLevel.BLOCKED):
        res = agent.run("Click at -50, 9999")
        assert res.success is False
        assert res.permission_denied is True
        assert "BLOCKED" in res.final_text


def test_action_verifier_categorization():
    """Verify ActionVerifier categorizes outcomes into VERIFIED_SUCCESS, NO_OBSERVABLE_CHANGE, and VERIFICATION_FAILURE."""
    # Mouse move verification
    res_move = ActionVerifier.verify_mouse_move(100, 100, (100, 100))
    assert res_move.outcome == VerificationOutcome.VERIFIED_SUCCESS
    assert res_move.verified is True

    res_move_fail = ActionVerifier.verify_mouse_move(100, 100, (500, 500))
    assert res_move_fail.outcome == VerificationOutcome.VERIFICATION_FAILURE
    assert res_move_fail.verified is False

    # Window title change -> VERIFIED_SUCCESS
    pre_obs = {"active_window_title": "Desktop", "image_path": ""}
    post_obs = {"active_window_title": "Notepad", "image_path": ""}
    res_click = ActionVerifier.verify_mouse_click(100, 100, pre_obs, post_obs)
    assert res_click.outcome == VerificationOutcome.VERIFIED_SUCCESS
    assert res_click.verified is True

    # Same window title & no image diff -> NO_OBSERVABLE_CHANGE
    pre_obs2 = {"active_window_title": "Notepad", "image_path": ""}
    post_obs2 = {"active_window_title": "Notepad", "image_path": ""}
    res_click2 = ActionVerifier.verify_mouse_click(100, 100, pre_obs2, post_obs2)
    assert res_click2.outcome == VerificationOutcome.NO_OBSERVABLE_CHANGE
    assert res_click2.verified is True


def test_keyboard_tools_remain_unimplemented():
    """Verify Phase B boundary: Keyboard tools remain completely un-implemented."""
    registry = create_default_registry()
    assert registry.get_tool("keyboard_type") is None
    assert registry.get_tool("keyboard_press") is None
    assert registry.get_tool("keyboard_hotkey") is None
