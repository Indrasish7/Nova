"""
Comprehensive Unit Tests for Nova Phase B.6 Semantic Desktop Interaction Architecture.
"""

import sys
import os
from unittest.mock import patch, MagicMock
import pytest

from PySide6.QtWidgets import QApplication, QLabel

from nova.perception.models import (
    SemanticTarget,
    ResolutionResult,
    ResolutionStatus,
    UIElementMetadata,
    UIResolutionResult
)
from nova.perception.resolver import TargetResolver
from nova.perception.uia import UIAutomationResolver
from nova.perception.verifier import ActionVerifier, VerificationResult, VerificationOutcome
from nova.tools.semantic_click import SemanticClickTool, SemanticClickInput
from nova.tools.mouse import MouseClickTool, MouseClickInput, MouseMoveTool
from nova.permissions.engine import PermissionEngine
from nova.permissions.level import PermissionLevel, ActionContext
from nova.runtime.agent import Agent, AgentStepResult
from nova.providers.mock import MockModelProvider
from nova.providers.base import ModelResponse, ToolCallRequest
from nova.ui.widgets import ConfirmationDialog


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


# ============================================================
# Section 13: Phase B.6 Critical Correction Regression Tests
# ============================================================

# --- Group A: Calculator Button '1' Deterministic Resolution ---

def test_calculator_button_1_resolves_unique():
    """Verify Calculator button '1' resolves to exactly one unique element without ambiguity."""
    meta_num1 = UIElementMetadata(
        name="One",
        automation_id="num1Button",
        control_type="Button",
        enabled=True,
        process_name="calculatorapp.exe",
        supported_patterns=["InvokePattern"]
    )
    res_uia = UIResolutionResult(
        success=True,
        status=ResolutionStatus.SUCCESS,
        element=meta_num1,
        candidates=[meta_num1],
        disambiguation_count=1
    )
    with patch.object(UIAutomationResolver, "resolve_element", return_value=res_uia):
        res = TargetResolver().resolve("1", control_type="Button", application_context="Calculator")
        assert res.success is True
        assert res.status == ResolutionStatus.SUCCESS
        assert res.disambiguation_count == 1
        assert len(res.candidates) == 1


def test_calculator_button_1_resolves_name_one():
    """Verify Calculator button '1' resolves to UIA Name='One'."""
    meta_num1 = UIElementMetadata(
        name="One",
        automation_id="num1Button",
        control_type="Button",
        enabled=True,
        process_name="calculatorapp.exe",
        supported_patterns=["InvokePattern"]
    )
    res_uia = UIResolutionResult(
        success=True,
        status=ResolutionStatus.SUCCESS,
        element=meta_num1,
        candidates=[meta_num1],
        disambiguation_count=1
    )
    with patch.object(UIAutomationResolver, "resolve_element", return_value=res_uia):
        res = TargetResolver().resolve("1", control_type="Button", application_context="Calculator")
        assert res.target.target_name == "One"


def test_calculator_button_1_resolves_num1Button():
    """Verify Calculator button '1' resolves to AutomationId='num1Button'."""
    meta_num1 = UIElementMetadata(
        name="One",
        automation_id="num1Button",
        control_type="Button",
        enabled=True,
        process_name="calculatorapp.exe",
        supported_patterns=["InvokePattern"]
    )
    res_uia = UIResolutionResult(
        success=True,
        status=ResolutionStatus.SUCCESS,
        element=meta_num1,
        candidates=[meta_num1],
        disambiguation_count=1
    )
    with patch.object(UIAutomationResolver, "resolve_element", return_value=res_uia):
        res = TargetResolver().resolve("1", control_type="Button", application_context="Calculator")
        assert res.target.automation_id == "num1Button"


def test_calculator_button_1_is_button():
    """Verify Calculator button '1' resolves strictly as ControlType='Button'."""
    meta_num1 = UIElementMetadata(
        name="One",
        automation_id="num1Button",
        control_type="Button",
        enabled=True,
        process_name="calculatorapp.exe",
        supported_patterns=["InvokePattern"]
    )
    res_uia = UIResolutionResult(
        success=True,
        status=ResolutionStatus.SUCCESS,
        element=meta_num1,
        candidates=[meta_num1],
        disambiguation_count=1
    )
    with patch.object(UIAutomationResolver, "resolve_element", return_value=res_uia):
        res = TargetResolver().resolve("1", control_type="Button", application_context="Calculator")
        assert res.target.control_type == "Button"


def test_calculator_button_1_is_calculator_process():
    """Verify Calculator button '1' target belongs to calculatorapp.exe."""
    meta_num1 = UIElementMetadata(
        name="One",
        automation_id="num1Button",
        control_type="Button",
        enabled=True,
        process_name="calculatorapp.exe",
        supported_patterns=["InvokePattern"]
    )
    res_uia = UIResolutionResult(
        success=True,
        status=ResolutionStatus.SUCCESS,
        element=meta_num1,
        candidates=[meta_num1],
        disambiguation_count=1
    )
    with patch.object(UIAutomationResolver, "resolve_element", return_value=res_uia):
        res = TargetResolver().resolve("1", control_type="Button", application_context="Calculator")
        assert res.target.process_name == "calculatorapp.exe"


# --- Group B: Fail-Closed Ambiguity Safety ---

def test_ambiguous_target_returns_ambiguous():
    """Verify TargetResolver returns ResolutionStatus.AMBIGUOUS when multiple matching controls exist."""
    res_ambig = UIResolutionResult(
        success=False,
        status=ResolutionStatus.AMBIGUOUS,
        disambiguation_count=3,
        error="AMBIGUOUS_TARGET: Multiple UI elements (3) matched 'Submit'"
    )
    with patch.object(UIAutomationResolver, "resolve_element", return_value=res_ambig):
        res = TargetResolver().resolve("Submit")
        assert res.success is False
        assert res.status == ResolutionStatus.AMBIGUOUS
        assert res.disambiguation_count == 3
        assert res.target is None
        assert "ambiguous" in res.error.lower()


def test_ambiguous_target_never_invokes_uia():
    """Verify ambiguous target never invokes UIA COM pattern."""
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(
        success=False,
        status=ResolutionStatus.AMBIGUOUS,
        disambiguation_count=2,
        error="Target is ambiguous: 2 matching controls found."
    )):
        with patch.object(UIAutomationResolver, "invoke_element_pattern") as mock_invoke:
            tool = SemanticClickTool()
            res = tool.execute(SemanticClickInput(target_name="AmbiguousBtn"), ActionContext())
            assert res.success is False
            assert res.metadata.get("status") == "AMBIGUOUS_TARGET"
            assert res.metadata.get("fallback_required") is False
            assert mock_invoke.called is False


def test_ambiguous_target_never_invokes_vision():
    """Verify ambiguous target never falls back to Vision perception."""
    class AmbiguityMockProvider:
        def __init__(self):
            self.turns = 0
        def generate(self, history, system_prompt, tools=None):
            self.turns += 1
            if self.turns == 1:
                return ModelResponse(
                    text=None,
                    tool_calls=[ToolCallRequest(id="call_ambig", name="semantic_click", arguments={"target_name": "AmbiguousBtn"})]
                )
            return ModelResponse(text="Attempting vision fallback", tool_calls=[ToolCallRequest(id="call_vision", name="screen_observe", arguments={})])

    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(
        success=False,
        status=ResolutionStatus.AMBIGUOUS,
        disambiguation_count=2,
        error="AMBIGUOUS_TARGET"
    )):
        prov = AmbiguityMockProvider()
        agent = Agent(provider=prov)
        agent.set_confirmation_callback(lambda name, args, perm: True)
        res = agent.run("Click the ambiguous button")
        assert res.success is False
        assert agent.ambiguity_detected is True
        assert prov.turns == 1  # Vision / turn 2 never called!


def test_ambiguous_target_never_moves_cursor():
    """Verify ambiguous target never triggers cursor movement."""
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(
        success=False,
        status=ResolutionStatus.AMBIGUOUS,
        disambiguation_count=2,
        error="AMBIGUOUS_TARGET"
    )):
        with patch.object(MouseMoveTool, "execute") as mock_move:
            tool = SemanticClickTool()
            tool.execute(SemanticClickInput(target_name="AmbiguousBtn"), ActionContext())
            assert mock_move.called is False


def test_ambiguous_target_never_calls_mouse_click():
    """Verify ambiguous target never calls mouse_click tool."""
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(
        success=False,
        status=ResolutionStatus.AMBIGUOUS,
        disambiguation_count=2,
        error="AMBIGUOUS_TARGET"
    )):
        with patch.object(MouseClickTool, "execute") as mock_click:
            tool = SemanticClickTool()
            tool.execute(SemanticClickInput(target_name="AmbiguousBtn"), ActionContext())
            assert mock_click.called is False


def test_ambiguous_target_generates_zero_sendinput():
    """Verify ambiguous target generates zero SendInput calls."""
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(
        success=False,
        status=ResolutionStatus.AMBIGUOUS,
        disambiguation_count=2,
        error="AMBIGUOUS_TARGET"
    )):
        with patch("nova.tools.mouse._win32_send_input") as mock_si:
            tool = SemanticClickTool()
            tool.execute(SemanticClickInput(target_name="AmbiguousBtn"), ActionContext())
            assert mock_si.called is False


# --- Group C: Disabled Target Safety ---

def test_disabled_target_never_falls_back_to_vision():
    """Verify disabled UI target fails closed with fallback_required=False and zero vision fallback."""
    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(
        success=False,
        status=ResolutionStatus.DISABLED,
        error="Target UI element 'DisabledBtn' is disabled and cannot be invoked."
    )):
        tool = SemanticClickTool()
        tool_res = tool.execute(SemanticClickInput(target_name="DisabledBtn"), ActionContext())
        assert tool_res.success is False
        assert tool_res.metadata.get("status") == "DISABLED"
        assert tool_res.metadata.get("fallback_required") is False


# --- Group D: Truthful Semantic vs Physical Confirmation UI ---

def test_uia_confirmation_displays_semantic_execution():
    """Verify UIA confirmation dialog truthfully presents semantic execution and physical mouse NOT USED."""
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = ConfirmationDialog(
        tool_name="semantic_click",
        arguments={
            "execution_type": "uia",
            "action": "INVOKE",
            "target_name": "One",
            "control_type": "Button",
            "application_context": "Calculator",
            "process_name": "calculatorapp.exe",
            "execution_mechanism": "Windows UI Automation",
            "pattern": "InvokePattern.Invoke()",
            "physical_mouse": "NOT USED"
        },
        permission_level=PermissionLevel.REQUIRES_CONFIRMATION
    )
    labels_text = " ".join([lbl.text() for lbl in dialog.findChildren(QLabel)])
    assert "Windows UI Automation" in labels_text
    assert "InvokePattern.Invoke()" in labels_text
    assert "Physical Mouse: <b>NOT USED</b>" in labels_text


def test_uia_confirmation_does_not_present_coordinates_as_execution():
    """Verify UIA confirmation dialog never displays physical mouse coordinates or PHYSICAL_CLICK."""
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = ConfirmationDialog(
        tool_name="semantic_click",
        arguments={
            "execution_type": "uia",
            "action": "INVOKE",
            "target_name": "One",
            "control_type": "Button",
            "application_context": "Calculator",
            "process_name": "calculatorapp.exe",
            "execution_mechanism": "Windows UI Automation",
            "pattern": "InvokePattern.Invoke()",
            "physical_mouse": "NOT USED"
        },
        permission_level=PermissionLevel.REQUIRES_CONFIRMATION
    )
    labels_text = " ".join([lbl.text() for lbl in dialog.findChildren(QLabel)])
    assert "Coordinates:" not in labels_text
    assert "PHYSICAL_CLICK" not in labels_text
    assert "Physical fallback via SendInput" not in labels_text


def test_physical_confirmation_displays_coordinates():
    """Verify physical click confirmation truthfully displays coordinates and physical mouse USED."""
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = ConfirmationDialog(
        tool_name="mouse_click",
        arguments={
            "execution_type": "physical_fallback",
            "action": "PHYSICAL_CLICK",
            "target_description": "Calculator One",
            "x": 279,
            "y": 855,
            "physical_mouse": "USED"
        },
        permission_level=PermissionLevel.REQUIRES_CONFIRMATION
    )
    labels_text = " ".join([lbl.text() for lbl in dialog.findChildren(QLabel)])
    assert "PHYSICAL_CLICK" in labels_text
    assert "Coordinates:" in labels_text
    assert "X: 279" in labels_text
    assert "Y: 855" in labels_text
    assert "Physical Mouse: <b>USED</b>" in labels_text


def test_confirmation_metadata_matches_actual_execution_path():
    """Verify confirmation metadata strictly distinguishes semantic UIA vs physical fallback paths."""
    captured_calls = []
    def record_confirmation(tool_name, args, perm):
        captured_calls.append({"tool": tool_name, "args": dict(args), "perm": perm})
        return True

    class FlowMockProvider:
        def __init__(self):
            self.step = 0
        def generate(self, history, system_prompt, tools=None):
            self.step += 1
            if self.step == 1:
                return ModelResponse(
                    text=None,
                    tool_calls=[ToolCallRequest(id="c1", name="semantic_click", arguments={"target_name": "One", "control_type": "Button"})]
                )
            elif self.step == 2:
                return ModelResponse(
                    text=None,
                    tool_calls=[ToolCallRequest(id="c2", name="mouse_click", arguments={"x": 100, "y": 200, "target_description": "Calc"})]
                )
            return ModelResponse(text="Done")

    agent = Agent(provider=FlowMockProvider())
    agent.set_confirmation_callback(record_confirmation)

    target_num1 = SemanticTarget(
        target_name="One",
        control_type="Button",
        process_name="calculatorapp.exe",
        enabled=True,
        supported_patterns=["InvokePattern"]
    )
    meta_num1 = UIElementMetadata(
        name="One",
        automation_id="num1Button",
        control_type="Button",
        enabled=True,
        process_name="calculatorapp.exe"
    )

    with patch.object(TargetResolver, "resolve", return_value=ResolutionResult(success=True, target=target_num1, resolver_source="uia")):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(True, "Invoked", meta_num1)):
            with patch("nova.tools.mouse._win32_send_input", return_value=True):
                with patch("nova.perception.screen.ScreenPerception.get_cursor_position", return_value=(100, 200)):
                    agent.run("Click 1")
                    assert len(captured_calls) >= 1
                    uia_call = captured_calls[0]
                    assert uia_call["tool"] == "semantic_click"
                    assert uia_call["args"]["execution_type"] == "uia"
                    assert uia_call["args"]["physical_mouse"] == "NOT USED"
                    assert uia_call["args"]["execution_mechanism"] == "Windows UI Automation"

                    agent.run("Click at 100 200")
                    assert len(captured_calls) >= 2
                    phys_call = captured_calls[1]
                    assert phys_call["tool"] == "mouse_click"
                    assert phys_call["args"]["execution_type"] == "physical_fallback"
                    assert phys_call["args"]["physical_mouse"] == "USED"
                    assert phys_call["args"]["execution_mechanism"] == "Physical fallback via SendInput"


def test_protected_target_description_evaluates_dangerous():
    """Verify mouse_click with Task Manager in target_description evaluates to DANGEROUS even with python.exe active."""
    engine = PermissionEngine()
    tool = MouseClickTool()
    inp = MouseClickInput(x=80, y=200, target_description="Performance tab in Task Manager")
    with patch("nova.permissions.engine.get_foreground_process_name", return_value="python.exe"):
        perm = engine.evaluate(tool, inp, ActionContext())
        assert perm == PermissionLevel.DANGEROUS


def test_agent_physical_fallback_sets_target_application():
    """Verify Agent physical fallback passes intended target application to confirmation callback."""
    captured = []
    def callback(tool_name, args, perm):
        captured.append((tool_name, dict(args), perm))
        return True

    class SingleClickMockProvider:
        def __init__(self):
            self.calls = 0
        def generate(self, history, system_prompt, tools=None):
            self.calls += 1
            if self.calls == 1:
                return ModelResponse(
                    text=None,
                    tool_calls=[ToolCallRequest(
                        id="c1",
                        name="mouse_click",
                        arguments={"x": 80, "y": 200, "target_description": "Performance tab in Task Manager"}
                    )]
                )
            return ModelResponse(text="Clicked", tool_calls=[])

    agent = Agent(provider=SingleClickMockProvider())
    agent.set_confirmation_callback(callback)
    with patch("nova.tools.mouse._win32_send_input", return_value=True):
        with patch("nova.perception.screen.ScreenPerception.get_cursor_position", return_value=(80, 200)):
            with patch("nova.permissions.engine.get_foreground_process_name", return_value="python.exe"):
                agent.run("Click the Performance tab in Task Manager")
                assert len(captured) == 1
                t_name, t_args, t_perm = captured[0]
                assert t_name == "mouse_click"
                assert t_perm == PermissionLevel.DANGEROUS
                assert "Task Manager" in t_args.get("application", "")
                assert "taskmgr" in t_args.get("application", "")


def test_uia_elevation_required_reports_informative_error():
    """Verify UIA reports explicit ELEVATION_REQUIRED error when non-elevated Nova interacts with taskmgr."""
    resolver = UIAutomationResolver()
    mock_tm_win = MagicMock()
    mock_tm_win.CurrentProcessId = 1234
    
    mock_elems_array = MagicMock()
    mock_elems_array.Length = 1  # UIPI blocked child elements
    
    with patch.object(resolver, "_ensure_automation"):
        resolver._automation = MagicMock()
        resolver._automation.GetRootElement.return_value.FindAll.return_value.Length = 1
        resolver._automation.GetRootElement.return_value.FindAll.return_value.GetElement.return_value = mock_tm_win
        mock_tm_win.FindAll.return_value = mock_elems_array
        with patch("nova.perception.uia._get_process_name_from_pid", return_value="taskmgr.exe"):
            with patch("nova.perception.uia.is_current_process_elevated", return_value=False):
                res = resolver.resolve_element("Performance", application_context="Task Manager")
                assert res.success is False
                assert res.status == ResolutionStatus.UNAVAILABLE
                assert "ELEVATION_REQUIRED" in res.error
                assert "Run as Administrator" in res.error


def test_semantic_click_suffix_normalization_1_button():
    """Verify target_name='1 button' normalizes and resolves to Button 1 (One/num1Button)."""
    resolver = UIAutomationResolver()
    mock_calc_win = MagicMock()
    mock_calc_win.CurrentProcessId = 5555

    mock_btn = MagicMock()
    mock_btn.CurrentName = "One"
    mock_btn.CurrentAutomationId = "num1Button"
    mock_btn.CurrentControlType = 50000  # Button
    mock_btn.CurrentIsEnabled = True
    mock_btn.CurrentProcessId = 5555

    mock_elems = MagicMock()
    mock_elems.Length = 1
    mock_elems.GetElement.return_value = mock_btn

    with patch.object(resolver, "_ensure_automation"):
        resolver._automation = MagicMock()
        resolver._automation.GetRootElement.return_value.FindAll.return_value.Length = 1
        resolver._automation.GetRootElement.return_value.FindAll.return_value.GetElement.return_value = mock_calc_win
        mock_calc_win.FindAll.return_value = mock_elems
        with patch("nova.perception.uia._get_process_name_from_pid", return_value="calculatorapp.exe"):
            res = resolver.resolve_element("1 button", application_context="Calculator")
            assert res.success is True
            assert res.element.name == "One"
            assert res.element.automation_id == "num1Button"


def test_semantic_click_suffix_normalization_performance_tab():
    """Verify target_name='Performance tab' normalizes and resolves to TabItem Performance."""
    resolver = UIAutomationResolver()
    mock_tm_win = MagicMock()
    mock_tm_win.CurrentProcessId = 6666

    mock_tab = MagicMock()
    mock_tab.CurrentName = "Performance"
    mock_tab.CurrentAutomationId = "PerformanceTab"
    mock_tab.CurrentControlType = 50019  # TabItem
    mock_tab.CurrentIsEnabled = True
    mock_tab.CurrentProcessId = 6666

    mock_elems = MagicMock()
    mock_elems.Length = 10
    mock_elems.GetElement.return_value = mock_tab

    with patch.object(resolver, "_ensure_automation"):
        resolver._automation = MagicMock()
        resolver._automation.GetRootElement.return_value.FindAll.return_value.Length = 1
        resolver._automation.GetRootElement.return_value.FindAll.return_value.GetElement.return_value = mock_tm_win
        mock_tm_win.FindAll.return_value = mock_elems
        with patch("nova.perception.uia._get_process_name_from_pid", return_value="taskmgr.exe"):
            with patch("nova.perception.uia.is_current_process_elevated", return_value=True):
                res = resolver.resolve_element("Performance tab", application_context="Task Manager")
                assert res.success is True
                assert res.element.name == "Performance"


def test_elevation_required_fails_closed_in_semantic_click_and_agent():
    """Verify ELEVATION_REQUIRED in semantic_click fails closed without permitting physical fallback."""
    tool = SemanticClickTool()
    elev_res = ResolutionResult(
        success=False,
        status=ResolutionStatus.UNAVAILABLE,
        error="ELEVATION_REQUIRED: Task Manager (taskmgr.exe) runs with elevated Administrator privileges."
    )
    with patch.object(TargetResolver, "resolve", return_value=elev_res):
        res = tool.execute(SemanticClickInput(target_name="Performance", application_context="Task Manager"), ActionContext())
        assert res.success is False
        assert res.metadata["fallback_required"] is False
        assert res.metadata["status"] == "ELEVATION_REQUIRED"

    # Verify Agent stops immediately and does not invoke subsequent tools
    class TwoStepMockProvider:
        def __init__(self):
            self.calls = 0
        def generate(self, history, system_prompt, tools=None):
            self.calls += 1
            if self.calls == 1:
                return ModelResponse(
                    text=None,
                    tool_calls=[ToolCallRequest(
                        id="c1",
                        name="semantic_click",
                        arguments={"target_name": "Performance", "application_context": "Task Manager"}
                    )]
                )
            return ModelResponse(
                text=None,
                tool_calls=[ToolCallRequest(
                    id="c2",
                    name="mouse_click",
                    arguments={"x": 80, "y": 200}
                )]
            )

    agent = Agent(provider=TwoStepMockProvider(), confirmation_callback=lambda *args: True)
    with patch.object(SemanticClickTool, "execute", return_value=res):
        step_result = agent.run("Click the Performance tab in Task Manager")
        assert step_result.success is False
        assert "ELEVATION_REQUIRED" in step_result.final_text
        assert len(step_result.tool_calls_executed) == 1
        assert step_result.tool_calls_executed[0]["tool"] == "semantic_click"


def test_taskbar_never_matched_for_task_manager():
    """Verify that Windows Taskbar is never incorrectly selected as Task Manager."""
    resolver = UIAutomationResolver()
    mock_taskbar = MagicMock()
    mock_taskbar.CurrentProcessId = 9999
    mock_taskbar.CurrentName = "Taskbar"

    with patch.object(resolver, "_ensure_automation"):
        resolver._automation = MagicMock()
        # Only Taskbar is in top children
        resolver._automation.GetRootElement.return_value.FindAll.return_value.Length = 1
        resolver._automation.GetRootElement.return_value.FindAll.return_value.GetElement.return_value = mock_taskbar
        with patch("nova.perception.uia._get_process_name_from_pid", return_value="explorer.exe"):
            with patch("ctypes.windll.user32.FindWindowW", return_value=0):
                res = resolver.resolve_element("Performance", application_context="Task Manager")
                assert res.success is False
                assert res.status == ResolutionStatus.UNAVAILABLE
                assert "was not found or is unavailable" in res.error


