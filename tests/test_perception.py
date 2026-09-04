"""
Unit tests for Nova Phase A Perception Layer.
"""

from pathlib import Path
import tempfile
import time
from unittest.mock import patch, MagicMock

from nova.perception.models import DisplayInfo, ScreenObservation
from nova.perception.screen import ScreenPerception
from nova.tools.screen_observe import ScreenObserveTool, ScreenObserveInput
from nova.tools.registry import create_default_registry
from nova.providers.base import ModelProvider, ModelCapability, ChatMessage, ModelResponse, ToolCallRequest
from nova.providers.gemini_provider import GeminiProvider
from nova.runtime.agent import Agent
from nova.permissions.level import ActionContext


class NoVisionProvider(ModelProvider):
    """Test provider without VISION capability."""
    capabilities = {ModelCapability.TEXT, ModelCapability.TOOL_CALLING}

    def generate(self, messages, tools):
        return ModelResponse(text="No vision supported.")


def test_screen_observation_model_validation():
    obs = ScreenObservation(
        timestamp="2026-08-28T18:00:00Z",
        width=1920,
        height=1080,
        cursor_x=500,
        cursor_y=300,
        active_window_title="Calculator",
        image_path="C:\\temp\\obs_test.png"
    )
    assert obs.width == 1920
    assert obs.height == 1080
    assert obs.cursor_x == 500
    assert obs.active_window_title == "Calculator"


def test_screen_perception_display_and_win32_info():
    perception = ScreenPerception()
    display = perception.get_display_info()
    assert display.width > 0
    assert display.height > 0

    cursor_x, cursor_y = perception.get_cursor_position()
    assert isinstance(cursor_x, int)
    assert isinstance(cursor_y, int)

    title = perception.get_active_window_title()
    assert isinstance(title, str)


def test_screen_perception_capture_and_cleanup():
    with tempfile.TemporaryDirectory() as tmpdir:
        perception = ScreenPerception(screenshot_dir=Path(tmpdir))
        obs = perception.capture_observation(reason="unit_test")
        
        assert Path(obs.image_path).exists()
        assert obs.width > 0
        assert obs.height > 0
        assert obs.metadata["reason"] == "unit_test"

        # Test cleanup logic
        perception.cleanup_ephemeral_screenshots(max_age_seconds=-1)
        assert not Path(obs.image_path).exists()


def test_screen_observe_tool_execution():
    tool = ScreenObserveTool()
    ctx = ActionContext()
    
    args = ScreenObserveInput(reason="testing_perception", include_active_window=True)
    res = tool.execute(args, ctx)

    assert res.success is True
    assert isinstance(res.output, dict)
    assert "image_path" in res.output
    assert "width" in res.output
    assert "active_window_title" in res.output


def test_tool_registry_includes_screen_observe():
    registry = create_default_registry()
    tool = registry.get_tool("screen_observe")
    assert tool is not None
    assert tool.name == "screen_observe"


def test_provider_capability_detection():
    gemini = GeminiProvider(api_key="fake")
    assert gemini.supports_capability(ModelCapability.VISION) is True

    no_vision = NoVisionProvider()
    assert no_vision.supports_capability(ModelCapability.VISION) is False


def test_agent_rejects_vision_on_non_vision_provider():
    no_vision = NoVisionProvider()
    agent = Agent(provider=no_vision)
    
    # Mock model requesting screen_observe
    no_vision.generate = MagicMock(return_value=ModelResponse(
        tool_calls=[
            ToolCallRequest(id="call_1", name="screen_observe", arguments={"reason": "test"})
        ]
    ))

    result = agent.run("What is on my screen?")
    assert result.success is False
    assert "does not support vision" in result.final_text


@patch("httpx.Client.post")
def test_gemini_provider_multimodal_payload(mock_post):
    """Verify GeminiProvider creates base64 multimodal image content when image_path is present."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "I see your desktop."}}]
    }
    mock_post.return_value = mock_resp

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01")
        temp_img_path = f.name

    try:
        provider = GeminiProvider(api_key="fake_key_123")
        messages = [
            ChatMessage(role="user", content="Describe this image", image_path=temp_img_path)
        ]
        res = provider.generate(messages, [])

        assert res.text == "I see your desktop."
        assert mock_post.called
        call_json = mock_post.call_args[1]["json"]
        
        # Verify content array with image_url base64 format appended in user message
        assert len(call_json["messages"]) == 2
        img_msg = call_json["messages"][1]
        assert isinstance(img_msg["content"], list)
        assert img_msg["content"][1]["type"] == "image_url"
        assert "data:image/png;base64," in img_msg["content"][1]["image_url"]["url"]

    finally:
        Path(temp_img_path).unlink(missing_ok=True)


@patch("httpx.Client.post")
def test_text_only_request_does_not_attach_image(mock_post):
    """Verify text-only requests (e.g. 'What is 2 + 2?') do NOT generate image payloads."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "2 + 2 = 4"}}]
    }
    mock_post.return_value = mock_resp

    provider = GeminiProvider(api_key="fake_key_123")
    res = provider.generate([ChatMessage(role="user", content="What is 2 + 2?")], [])

    assert res.text == "2 + 2 = 4"
    call_json = mock_post.call_args[1]["json"]
    assert len(call_json["messages"]) == 1
    msg_payload = call_json["messages"][0]
    
    # Verify string content, NOT multimodal list array
    assert isinstance(msg_payload["content"], str)
    assert msg_payload["content"] == "What is 2 + 2?"
