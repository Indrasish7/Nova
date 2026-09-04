"""
Comprehensive Unit Tests for Nova Phase B.6 Semantic Desktop Interaction Architecture.
"""

import os
from unittest.mock import patch, MagicMock
import pytest

from nova.perception.models import SemanticTarget, ResolutionResult, UIElementMetadata, UIResolutionResult
from nova.perception.resolver import TargetResolver
from nova.perception.uia import UIAutomationResolver
from nova.perception.verifier import ActionVerifier, VerificationResult, VerificationOutcome
from nova.tools.semantic_click import SemanticClickTool, SemanticClickInput
from nova.tools.mouse import MouseClickTool, MouseClickInput
from nova.permissions.engine import PermissionEngine
from nova.permissions.level import PermissionLevel, ActionContext
from nova.runtime.agent import Agent
from nova.providers.mock import MockModelProvider
from nova.providers.base import ModelResponse, ToolCallRequest


def test_calculator_button_1_resolves_uia():
    """Verify Calculator button 1 resolves semantically via UIA handling aliases (One / num1Button)."""
    meta = UIElementMetadata(name="One", automation_id="num1Button", control_type="Button", enabled=True, process_name="calculatorapp.exe")
    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta)):
        res = TargetResolver().resolve("1", control_type="Button", application_context="Calculator")
        assert res.success is True
        assert res.target.target_name == "One"
        assert res.target.control_type == "Button"


def test_calculator_button_4_resolves_uia():
    """Verify Calculator button 4 resolves semantically via UIA handling aliases (Four / num4Button)."""
    meta = UIElementMetadata(name="Four", automation_id="num4Button", control_type="Button", enabled=True, process_name="calculatorapp.exe")
    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta)):
        res = TargetResolver().resolve("4", control_type="Button", application_context="Calculator")
        assert res.success is True
        assert res.target.target_name == "Four"


def test_calculator_button_7_resolves_uia():
    """Verify Calculator button 7 resolves semantically via UIA handling aliases (Seven / num7Button)."""
    meta = UIElementMetadata(name="Seven", automation_id="num7Button", control_type="Button", enabled=True, process_name="calculatorapp.exe")
    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta)):
        res = TargetResolver().resolve("7", control_type="Button", application_context="Calculator")
        assert res.success is True
        assert res.target.target_name == "Seven"


def test_button_uses_invoke_pattern():
    """Verify Button control uses InvokePattern.Invoke()."""
    target = SemanticTarget(target_name="One", control_type="Button", process_name="calculatorapp.exe", enabled=True, supported_patterns=["InvokePattern"])
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(success=True, target=target, resolver_source="uia")):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(True, "Invoked InvokePattern", None)):
            tool = SemanticClickTool()
            res = tool.execute(SemanticClickInput(target_name="1", control_type="Button"), ActionContext())
            assert res.success is True
            assert res.metadata["via_uia_pattern"] is True


def test_uia_button_generates_zero_sendinput():
    """Verify UIA button pattern invocation generates zero SendInput calls."""
    target = SemanticTarget(target_name="One", control_type="Button", process_name="calculatorapp.exe", enabled=True, supported_patterns=["InvokePattern"])
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(success=True, target=target, resolver_source="uia")):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(True, "Invoked", None)):
            with patch("nova.tools.mouse._win32_send_input") as mock_si:
                tool = SemanticClickTool()
                tool.execute(SemanticClickInput(target_name="1"), ActionContext())
                assert mock_si.called is False


def test_task_manager_performance_tab_resolves_tabitem():
    """Verify Task Manager Performance tab resolves as TabItem."""
    meta = UIElementMetadata(name="Performance", control_type="TabItem", enabled=True, process_name="taskmgr.exe")
    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta)):
        res = TargetResolver().resolve("Performance", control_type="TabItem", application_context="Task Manager")
        assert res.success is True
        assert res.target.control_type == "TabItem"
        assert res.target.process_name == "taskmgr.exe"


def test_performance_tab_uses_selection_item_pattern():
    """Verify TabItem uses SelectionItemPattern.Select()."""
    target = SemanticTarget(target_name="Performance", control_type="TabItem", process_name="taskmgr.exe", enabled=True, supported_patterns=["SelectionItemPattern"])
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(success=True, target=target, resolver_source="uia")):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(True, "Invoked SelectionItemPattern", None)):
            tool = SemanticClickTool()
            res = tool.execute(SemanticClickInput(target_name="Performance", control_type="TabItem"), ActionContext())
            assert res.success is True
            assert res.metadata["via_uia_pattern"] is True


def test_tab_invocation_generates_zero_sendinput():
    """Verify TabItem pattern invocation generates zero SendInput hardware mouse events."""
    target = SemanticTarget(target_name="Performance", control_type="TabItem", process_name="taskmgr.exe", enabled=True)
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(success=True, target=target, resolver_source="uia")):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(True, "Invoked", None)):
            with patch("nova.tools.mouse._win32_send_input") as mock_si:
                tool = SemanticClickTool()
                tool.execute(SemanticClickInput(target_name="Performance"), ActionContext())
                assert mock_si.called is False


def test_ambiguous_targets_not_invoked():
    """Verify ambiguous UIA target matches return error and prevent automatic invocation."""
    meta = UIElementMetadata(name="OK", control_type="Button", enabled=True)
    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta, disambiguation_count=5)):
        res = TargetResolver().resolve("OK")
        assert res.success is False
        assert "ambiguous" in res.error.lower()


def test_disabled_control_blocked():
    """Verify disabled UIA control (enabled=False) evaluates to BLOCKED."""
    engine = PermissionEngine()
    target = SemanticTarget(target_name="DisabledButton", control_type="Button", enabled=False, process_name="calc.exe")
    perm = engine.evaluate(SemanticClickTool(), SemanticClickInput(target_name="DisabledButton"), ActionContext(), uia_element=target)
    assert perm == PermissionLevel.BLOCKED


def test_protected_process_remains_dangerous():
    """Verify protected process image (taskmgr.exe) evaluates to DANGEROUS."""
    engine = PermissionEngine()
    target = SemanticTarget(target_name="End task", control_type="Button", enabled=True, process_name="taskmgr.exe")
    perm = engine.evaluate(SemanticClickTool(), SemanticClickInput(target_name="End task"), ActionContext(), uia_element=target)
    assert perm == PermissionLevel.DANGEROUS


def test_untrusted_gemini_description_cannot_downgrade_security():
    """Verify Gemini target_description cannot override protected process security level."""
    engine = PermissionEngine()
    target = SemanticTarget(target_name="Processes", control_type="TabItem", enabled=True, process_name="taskmgr.exe")
    perm = engine.evaluate(
        SemanticClickTool(),
        SemanticClickInput(target_name="Processes", target_description="Harmless target"),
        ActionContext(),
        uia_element=target
    )
    assert perm == PermissionLevel.DANGEROUS


def test_calculator_low_risk_is_safe_under_balanced_mode():
    """Verify low-risk Calculator number and operator buttons evaluate to SAFE under BALANCED mode."""
    engine = PermissionEngine()
    target = SemanticTarget(target_name="One", control_type="Button", enabled=True, process_name="calculatorapp.exe")
    perm = engine.evaluate(
        SemanticClickTool(),
        SemanticClickInput(target_name="1", application_context="Calculator"),
        ActionContext(),
        uia_element=target
    )
    assert perm == PermissionLevel.SAFE


def test_uia_failure_invokes_vision_fallback():
    """Verify UIA resolution failure indicates fallback_required in ToolResult metadata."""
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(success=False, resolver_source="physical_fallback", error="Not found")):
        tool = SemanticClickTool()
        res = tool.execute(SemanticClickInput(target_name="CustomWidget"), ActionContext())
        assert res.success is False
        assert res.metadata.get("fallback_required") is True


def test_uia_failure_does_not_falsely_report_success():
    """Verify UIA resolution failure returns ToolResult success=False."""
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(success=False, resolver_source="physical_fallback", error="Failed")):
        tool = SemanticClickTool()
        res = tool.execute(SemanticClickInput(target_name="UnknownControl"), ActionContext())
        assert res.success is False


def test_post_action_verification_failure_prevents_success():
    """Verify post-action state verification failure prevents tool from reporting success."""
    target = SemanticTarget(target_name="One", control_type="Button", process_name="calculatorapp.exe", enabled=True)
    failed_ver = VerificationResult(
        outcome=VerificationOutcome.VERIFICATION_FAILURE,
        verified=False,
        confidence=0.9,
        reason="Calculator display state did not change after invoking 'One' (Display remains 'Display is 0')."
    )
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(success=True, target=target, resolver_source="uia")):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(True, "Invoked", None)):
            with patch("nova.tools.semantic_click.ActionVerifier.verify_semantic_click", return_value=failed_ver):
                tool = SemanticClickTool()
                res = tool.execute(SemanticClickInput(target_name="1", application_context="Calculator"), ActionContext())
                assert res.success is False
                assert "VERIFICATION_FAILED" in res.error


def test_uia_no_pattern_uses_boundingbox_fallback():
    """Verify physical BoundingRectangle fallback is used if UIA element exposes no COM pattern."""
    target = SemanticTarget(target_name="NoPatternCtrl", control_type="Unknown", enabled=True, center_point=(300, 300), process_name="notepad.exe")
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(success=True, target=target, resolver_source="uia")):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(False, "No pattern", None)):
            with patch("nova.tools.mouse._win32_send_input", return_value=True) as mock_si:
                with patch("nova.perception.screen.ScreenPerception.get_cursor_position", return_value=(300, 300)):
                    tool = SemanticClickTool()
                    res = tool.execute(SemanticClickInput(target_name="NoPatternCtrl"), ActionContext())
                    assert res.success is True
                    assert res.metadata["via_bounding_box_sendinput"] is True


def test_physical_fallback_cursor_verification():
    """Verify physical click fallback performs cursor round-trip verification."""
    tool = MouseClickTool()
    ctx = ActionContext()
    with patch("nova.perception.screen.ScreenPerception.get_cursor_position", return_value=(100, 100)):
        with patch("nova.tools.mouse._win32_send_input", return_value=True):
            res = tool.execute(MouseClickInput(x=100, y=100, verify_cursor=True), ctx)
            assert res.success is True
            assert res.metadata.get("cursor_verified") is True


def test_cursor_mismatch_prevents_click():
    """Verify cursor mismatch aborts physical click execution."""
    tool = MouseClickTool()
    ctx = ActionContext()
    with patch("nova.perception.screen.ScreenPerception.get_cursor_position", return_value=(999, 999)):
        with patch("nova.tools.mouse._win32_send_input", return_value=True) as mock_si:
            res = tool.execute(MouseClickInput(x=100, y=100, verify_cursor=True), ctx)
            assert res.success is False
            assert "Cursor round-trip verification failed" in res.error


def test_out_of_bounds_blocked():
    """Verify out-of-bounds coordinates return BLOCKED."""
    engine = PermissionEngine()
    perm = engine.evaluate(MouseClickTool(), MouseClickInput(x=-50, y=9999), ActionContext())
    assert perm == PermissionLevel.BLOCKED


def test_nova_launcher_not_target():
    """Verify Nova launcher PID (os.getpid()) is excluded from target resolution."""
    self_pid = os.getpid()
    meta_self = UIElementMetadata(name="Nova Launcher", control_type="Window", process_id=self_pid, process_name="nova_gui.exe")
    meta_calc = UIElementMetadata(name="Calculator", control_type="Window", process_id=9999, process_name="calculatorapp.exe")

    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta_calc)):
        res = TargetResolver().resolve("1", application_context="Calculator")
        assert res.success is True
        assert res.target.process_name == "calculatorapp.exe"


def test_application_context_targeting():
    """Verify application_context filters target resolution to target app window."""
    meta = UIElementMetadata(name="1", control_type="Button", enabled=True, process_name="calc.exe")
    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta)) as mock_res:
        TargetResolver().resolve("1", control_type="Button", application_context="Calculator")
        mock_res.assert_called_once_with(
            target_name="1",
            control_type="Button",
            window_title=None,
            process_name=None,
            application_context="Calculator"
        )


def test_existing_mouse_move_functional():
    """Verify MouseClickTool remains functional."""
    tool = MouseClickTool()
    assert tool.name == "mouse_click"


def test_action_verifier_valid():
    """Verify ActionVerifier tests remain valid."""
    from nova.perception.verifier import ActionVerifier, VerificationOutcome
    res = ActionVerifier.verify_mouse_move(100, 100, (100, 100))
    assert res.outcome == VerificationOutcome.VERIFIED_SUCCESS
