"""
Unit tests for Nova Phase B.5 Semantic UI Interaction Layer.
"""

from unittest.mock import patch, MagicMock
import pytest

from nova.perception.models import UIElementMetadata, UIResolutionResult
from nova.perception.uia import UIAutomationResolver
from nova.tools.semantic_click import SemanticClickTool, SemanticClickInput
from nova.permissions.engine import PermissionEngine
from nova.permissions.level import PermissionLevel, ActionContext
from nova.runtime.agent import Agent
from nova.providers.mock import MockModelProvider
from nova.providers.base import ModelResponse, ToolCallRequest


def test_tab_item_resolved_uses_selection_item_pattern():
    """Verify TabItem element uses SelectionItemPattern.Select() without generating SendInput."""
    meta = UIElementMetadata(
        name="Performance",
        control_type="TabItem",
        enabled=True,
        selected=False,
        supported_patterns=["SelectionItemPattern"],
        bounding_box=(100, 200, 200, 250),
        center_point=(150, 225),
        process_name="taskmgr.exe"
    )

    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta)):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(True, "Invoked SelectionItemPattern", meta)):
            with patch("nova.tools.mouse._win32_send_input") as mock_send_input:
                tool = SemanticClickTool()
                res = tool.execute(SemanticClickInput(target_name="Performance", control_type="TabItem"), ActionContext())

                assert res.success is True
                assert res.metadata["via_uia_pattern"] is True
                assert res.metadata["hardware_mouse_event"] is False
                assert mock_send_input.called is False


def test_button_resolved_uses_invoke_pattern():
    """Verify Button element uses InvokePattern.Invoke() without generating SendInput."""
    meta = UIElementMetadata(
        name="1",
        control_type="Button",
        enabled=True,
        supported_patterns=["InvokePattern"],
        bounding_box=(50, 50, 100, 100),
        center_point=(75, 75),
        process_name="calc.exe"
    )

    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta)):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(True, "Invoked InvokePattern", meta)):
            with patch("nova.tools.mouse._win32_send_input") as mock_send_input:
                tool = SemanticClickTool()
                res = tool.execute(SemanticClickInput(target_name="1", control_type="Button"), ActionContext())

                assert res.success is True
                assert res.metadata["via_uia_pattern"] is True
                assert res.metadata["hardware_mouse_event"] is False
                assert mock_send_input.called is False


def test_uia_invocation_generates_no_mouse_event():
    """Verify zero hardware mouse events (SendInput) are generated during UIA pattern invocation."""
    meta = UIElementMetadata(
        name="Submit",
        control_type="Button",
        enabled=True,
        supported_patterns=["InvokePattern"],
        bounding_box=(100, 100, 200, 150),
        center_point=(150, 125),
        process_name="notepad.exe"
    )

    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta)):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(True, "Invoked", meta)):
            with patch("nova.tools.mouse._win32_send_input") as mock_send_input:
                tool = SemanticClickTool()
                tool.execute(SemanticClickInput(target_name="Submit"), ActionContext())

                assert mock_send_input.called is False


def test_uia_element_resolved_without_pattern_falls_back_to_bounding_box():
    """Verify physical SendInput at bounding box center is used if UIA element exposes no COM pattern."""
    meta = UIElementMetadata(
        name="CustomControl",
        control_type="Unknown",
        enabled=True,
        supported_patterns=[],
        bounding_box=(300, 300, 400, 400),
        center_point=(350, 350),
        process_name="notepad.exe"
    )

    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta)):
        with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(False, "No pattern", meta)):
            with patch("nova.tools.mouse._win32_send_input", return_value=True) as mock_send_input:
                with patch("nova.perception.screen.ScreenPerception.get_cursor_position", return_value=(350, 350)):
                    tool = SemanticClickTool()
                    res = tool.execute(SemanticClickInput(target_name="CustomControl"), ActionContext())

                assert res.success is True
                assert res.metadata["via_uia_pattern"] is False
                assert res.metadata["via_bounding_box_sendinput"] is True
                assert res.metadata["hardware_mouse_event"] is True
                assert mock_send_input.called is True


def test_uia_resolution_failure_triggers_fallback_metadata():
    """Verify UIA resolution failure indicates fallback_required in metadata."""
    with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=False, error="Not found")):
        tool = SemanticClickTool()
        res = tool.execute(SemanticClickInput(target_name="UnknownWidget"), ActionContext())

        assert res.success is False
        assert res.metadata.get("fallback_required") is True


def test_permission_engine_denial_blocks_disabled_elements():
    """Verify PermissionEngine blocks interaction with disabled UIA elements."""
    engine = PermissionEngine()
    meta = UIElementMetadata(
        name="DisabledButton",
        control_type="Button",
        enabled=False,
        process_name="calc.exe"
    )

    perm = engine.evaluate(SemanticClickTool(), SemanticClickInput(target_name="DisabledButton"), ActionContext(), uia_element=meta)
    assert perm == PermissionLevel.BLOCKED


def test_protected_process_security_check_for_uia_element():
    """Verify protected process image (e.g. taskmgr.exe) rates DANGEROUS for UIA element."""
    engine = PermissionEngine()
    meta = UIElementMetadata(
        name="Performance",
        control_type="TabItem",
        enabled=True,
        process_name="taskmgr.exe"
    )

    perm = engine.evaluate(SemanticClickTool(), SemanticClickInput(target_name="Performance"), ActionContext(), uia_element=meta)
    assert perm == PermissionLevel.DANGEROUS


def test_untrusted_gemini_description_cannot_downgrade_protected_target():
    """Verify Gemini target_description='Harmless' cannot override protected process security level."""
    engine = PermissionEngine()
    meta = UIElementMetadata(
        name="Processes",
        control_type="TabItem",
        enabled=True,
        process_name="taskmgr.exe"
    )

    perm = engine.evaluate(
        SemanticClickTool(),
        SemanticClickInput(target_name="Processes", target_description="Harmless safe button"),
        ActionContext(),
        uia_element=meta
    )
    assert perm == PermissionLevel.DANGEROUS
