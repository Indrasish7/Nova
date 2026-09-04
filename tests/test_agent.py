"""
Unit tests for MockModelProvider and Agent Runtime orchestrator.
"""

from typing import Dict, Any
from pathlib import Path
import tempfile

from nova.runtime.agent import Agent, AgentStepResult
from nova.providers.mock import MockModelProvider
from nova.providers.base import ModelProvider, ChatMessage, ModelResponse
from nova.permissions.level import PermissionLevel
from nova.tools.registry import create_default_registry
from nova.config import Settings


class ErrorModelProvider(ModelProvider):
    """Provider simulating connection / API errors."""

    def generate(self, messages, tools):
        return ModelResponse(text="Error connecting to LLM provider: Connection Timeout")


def test_mock_provider_intent_matching():
    provider = MockModelProvider()
    tools = create_default_registry().get_definitions()

    # Notepad -> open_application(app_name="notepad")
    res_notepad = provider.generate([ChatMessage(role="user", content="Open Notepad")], tools)
    assert len(res_notepad.tool_calls) == 1
    assert res_notepad.tool_calls[0].name == "open_application"
    assert res_notepad.tool_calls[0].arguments["app_name"] == "notepad"

    # Calculator -> open_application(app_name="calculator")
    res_calc = provider.generate([ChatMessage(role="user", content="Open Calculator")], tools)
    assert len(res_calc.tool_calls) == 1
    assert res_calc.tool_calls[0].name == "open_application"
    assert res_calc.tool_calls[0].arguments["app_name"] == "calculator"

    # CMD -> open_application(app_name="cmd")
    res_cmd = provider.generate([ChatMessage(role="user", content="Open CMD")], tools)
    assert len(res_cmd.tool_calls) == 1
    assert res_cmd.tool_calls[0].name == "open_application"
    assert res_cmd.tool_calls[0].arguments["app_name"] == "cmd"

    # PowerShell -> open_application(app_name="powershell")
    res_ps = provider.generate([ChatMessage(role="user", content="Open PowerShell")], tools)
    assert len(res_ps.tool_calls) == 1
    assert res_ps.tool_calls[0].name == "open_application"
    assert res_ps.tool_calls[0].arguments["app_name"] == "powershell"

    # Folder creation on Desktop
    res_folder = provider.generate([ChatMessage(role="user", content="Create a folder called NovaTest on my Desktop")], tools)
    assert len(res_folder.tool_calls) == 1
    assert res_folder.tool_calls[0].name == "create_folder"
    expected_desktop_folder = str((Settings.USER_DESKTOP / "NovaTest").resolve())
    assert res_folder.tool_calls[0].arguments["folder_path"] == expected_desktop_folder

    # Screenshot
    res_shot = provider.generate([ChatMessage(role="user", content="Take a screenshot")], tools)
    assert len(res_shot.tool_calls) == 1
    assert res_shot.tool_calls[0].name == "take_screenshot"


def test_agent_full_pipeline_cmd_and_powershell_rejection():
    # Security requirement: Prove that CMD and PowerShell requests produce tool calls that reach AppResolver and are rejected
    provider = MockModelProvider()
    agent = Agent(provider=provider)

    # Auto-approve confirmation to allow tool call execution phase to reach AppResolver
    agent.set_confirmation_callback(lambda name, args, perm: True)

    # Test CMD rejection through full Agent -> ToolRegistry -> AppResolver
    result_cmd = agent.run("Open CMD")
    assert len(result_cmd.tool_calls_executed) == 1
    executed_cmd = result_cmd.tool_calls_executed[0]
    assert executed_cmd["tool"] == "open_application"
    assert executed_cmd["arguments"]["app_name"] == "cmd"
    assert executed_cmd["success"] is False
    assert "blocked" in str(executed_cmd["error"]).lower() or "not permitted" in str(executed_cmd["error"]).lower()

    # Test PowerShell rejection through full Agent -> ToolRegistry -> AppResolver
    result_ps = agent.run("Open PowerShell")
    assert len(result_ps.tool_calls_executed) == 1
    executed_ps = result_ps.tool_calls_executed[0]
    assert executed_ps["tool"] == "open_application"
    assert executed_ps["arguments"]["app_name"] == "powershell"
    assert executed_ps["success"] is False


def test_agent_safe_tool_execution():
    provider = MockModelProvider()
    agent = Agent(provider=provider)

    result: AgentStepResult = agent.run("Take a screenshot of my display")

    assert result.success is True
    assert len(result.tool_calls_executed) == 1
    executed = result.tool_calls_executed[0]
    assert executed["tool"] == "take_screenshot"
    assert executed["success"] is True


def test_agent_confirmation_approved():
    provider = MockModelProvider()
    agent = Agent(provider=provider)

    def approve_all(tool_name: str, args: Dict[str, Any], perm: PermissionLevel) -> bool:
        return True

    agent.set_confirmation_callback(approve_all)

    result: AgentStepResult = agent.run("Create a folder called NovaTest on my Desktop")
    
    assert result.success is True
    assert result.permission_denied is False
    assert len(result.tool_calls_executed) >= 1
    executed = result.tool_calls_executed[0]
    assert executed["tool"] == "create_folder"
    assert str(Settings.USER_DESKTOP / "NovaTest") in executed["arguments"]["folder_path"]


def test_agent_confirmation_denied():
    provider = MockModelProvider()
    agent = Agent(provider=provider)

    def deny_all(tool_name: str, args: Dict[str, Any], perm: PermissionLevel) -> bool:
        return False

    agent.set_confirmation_callback(deny_all)

    result: AgentStepResult = agent.run("Create a folder called NovaTest on my Desktop")

    assert result.success is False
    assert result.permission_denied is True
    assert "cancelled" in result.final_text.lower() or "denied" in result.final_text.lower()


def test_agent_provider_error_handling():
    error_provider = ErrorModelProvider()
    agent = Agent(provider=error_provider)

    result: AgentStepResult = agent.run("Hello Nova")

    assert result.success is True
    assert "Error connecting" in result.final_text
    assert len(result.tool_calls_executed) == 0
