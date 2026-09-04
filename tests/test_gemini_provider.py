"""
Unit tests for GeminiProvider and Gemini-driven Agent integration using mocked HTTP calls.
"""

from typing import Dict, Any
from unittest.mock import patch, MagicMock
import httpx
import pytest

from nova.providers.gemini_provider import GeminiProvider
from nova.providers.base import ChatMessage, ModelResponse, ToolCallRequest
from nova.runtime.agent import Agent, AgentStepResult
from nova.permissions.level import PermissionLevel
from nova.tools.registry import create_default_registry


def test_gemini_provider_missing_api_key():
    """Verify missing API key returns explicit configuration error without silent fallback."""
    provider = GeminiProvider(api_key="")
    tools = create_default_registry().get_definitions()
    
    response = provider.generate([ChatMessage(role="user", content="Hello")], tools)
    assert response.text is not None
    assert "Gemini API key is not configured" in response.text
    assert len(response.tool_calls) == 0


@patch("httpx.Client.post")
def test_gemini_provider_text_generation(mock_post):
    """Verify GeminiProvider parses text response from Chat Completions API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello! I am Nova."
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    provider = GeminiProvider(api_key="fake_key_123")
    response = provider.generate([ChatMessage(role="user", content="Hi")], [])

    assert response.text == "Hello! I am Nova."
    assert len(response.tool_calls) == 0


@patch("httpx.Client.post")
def test_gemini_provider_function_call_parsing(mock_post):
    """Verify GeminiProvider parses function call tool requests correctly."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_calc_99",
                            "type": "function",
                            "function": {
                                "name": "open_application",
                                "arguments": '{"app_name": "calculator"}'
                            }
                        }
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    provider = GeminiProvider(api_key="fake_key_123")
    tools = create_default_registry().get_definitions()
    response = provider.generate([ChatMessage(role="user", content="Open Calculator")], tools)

    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.id == "call_calc_99"
    assert call.name == "open_application"
    assert call.arguments["app_name"] == "calculator"


@patch("httpx.Client.post")
def test_gemini_provider_auth_failure(mock_post):
    """Verify 401 Unauthorized responses return clean user-facing error."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_post.return_value = mock_response

    provider = GeminiProvider(api_key="invalid_key")
    response = provider.generate([ChatMessage(role="user", content="Hi")], [])

    assert response.text is not None
    assert "401 Unauthorized" in response.text


@patch("httpx.Client.post")
def test_gemini_provider_timeout_failure(mock_post):
    """Verify timeout exceptions return clean timeout message."""
    mock_post.side_effect = httpx.TimeoutException("Timeout")

    provider = GeminiProvider(api_key="fake_key_123")
    response = provider.generate([ChatMessage(role="user", content="Hi")], [])

    assert response.text is not None
    assert "timed out" in response.text.lower()


@patch("httpx.Client.post")
def test_gemini_agent_cmd_security_rejection(mock_post):
    """
    SECURITY TEST:
    Mock a Gemini model response requesting open_application(app_name="cmd").
    Verify that the model tool call is treated as untrusted input and REJECTED
    by Agent -> ToolRegistry -> AppResolver.
    """
    resp_turn_1 = MagicMock()
    resp_turn_1.status_code = 200
    resp_turn_1.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_cmd_hack",
                            "type": "function",
                            "function": {
                                "name": "open_application",
                                "arguments": '{"app_name": "cmd"}'
                            }
                        }
                    ]
                }
            }
        ]
    }

    resp_turn_2 = MagicMock()
    resp_turn_2.status_code = 200
    resp_turn_2.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Action blocked: Command Prompt (cmd) is not permitted for security reasons."
                }
            }
        ]
    }

    mock_post.side_effect = [resp_turn_1, resp_turn_2]

    provider = GeminiProvider(api_key="fake_key_123")
    agent = Agent(provider=provider)
    agent.set_confirmation_callback(lambda name, args, perm: True)

    result = agent.run("Open CMD")

    assert len(result.tool_calls_executed) == 1
    executed = result.tool_calls_executed[0]
    assert executed["tool"] == "open_application"
    assert executed["arguments"]["app_name"] == "cmd"
    assert executed["success"] is False
    assert "blocked" in str(executed["error"]).lower() or "not permitted" in str(executed["error"]).lower()
    assert result.final_text == "Action blocked: Command Prompt (cmd) is not permitted for security reasons."


@patch("httpx.Client.post")
def test_gemini_agent_multi_turn_execution_flow(mock_post):
    """
    MULTI-TURN TEST:
    Turn 1: Gemini requests open_application(app_name="notepad").
    Turn 2: Agent executes tool, feeds tool result back to Gemini, Gemini returns final text response.
    """
    resp_turn_1 = MagicMock()
    resp_turn_1.status_code = 200
    resp_turn_1.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_notepad_1",
                            "type": "function",
                            "function": {
                                "name": "open_application",
                                "arguments": '{"app_name": "notepad"}'
                            }
                        }
                    ]
                }
            }
        ]
    }

    resp_turn_2 = MagicMock()
    resp_turn_2.status_code = 200
    resp_turn_2.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "I have successfully opened Notepad for you."
                }
            }
        ]
    }

    mock_post.side_effect = [resp_turn_1, resp_turn_2]

    provider = GeminiProvider(api_key="fake_key_123")
    agent = Agent(provider=provider)
    agent.set_confirmation_callback(lambda name, args, perm: True)

    result: AgentStepResult = agent.run("Launch Notepad please")

    assert result.success is True
    assert len(result.tool_calls_executed) == 1
    assert result.tool_calls_executed[0]["tool"] == "open_application"
    assert result.tool_calls_executed[0]["success"] is True
    assert result.final_text == "I have successfully opened Notepad for you."
