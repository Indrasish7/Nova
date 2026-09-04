"""
Mock Model Provider.

Provides deterministic responses for offline testing and evaluation without an API key.
"""

import uuid
import re
from typing import List, Optional, Set
from nova.providers.base import ModelProvider, ModelCapability, ChatMessage, ModelResponse, ToolCallRequest
from nova.tools.base import ToolDefinition
from nova.config import Settings


class MockModelProvider(ModelProvider):
    """Deterministic mock provider for offline agent testing."""

    capabilities: Set[ModelCapability] = {
        ModelCapability.TEXT,
        ModelCapability.TOOL_CALLING,
        ModelCapability.VISION,
    }

    def __init__(self, forced_response: Optional[ModelResponse] = None):
        self.forced_response = forced_response

    def generate(
        self,
        messages: List[ChatMessage],
        tools: List[ToolDefinition]
    ) -> ModelResponse:
        """Generate deterministic response or tool call based on input prompt."""
        if self.forced_response is not None:
            return self.forced_response

        # Find latest user prompt
        user_prompt = ""
        for msg in reversed(messages):
            if msg.role == "user" and msg.content:
                user_prompt = msg.content.strip()
                break

        prompt_lower = user_prompt.lower()

        # If previous message was a tool result, return formatted natural language response
        last_msg = messages[-1] if messages else None
        if last_msg and last_msg.role == "tool":
            return ModelResponse(
                text=f"Completed action for request '{user_prompt}': {last_msg.content}"
            )

        # 1. Perception / Screen Observe Intent Matching (Phase A)
        if any(kw in prompt_lower for kw in ["visible", "on my screen", "what application", "what buttons", "observe screen"]):
            return ModelResponse(
                tool_calls=[
                    ToolCallRequest(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="screen_observe",
                        arguments={"reason": "identify_visible_desktop"}
                    )
                ]
            )

        # 2. Application Launch Intent Matching
        if any(kw in prompt_lower for kw in ["open", "launch", "start", "run"]):
            target_app = "notepad"  # default fallback
            if "calculator" in prompt_lower or "calc" in prompt_lower:
                target_app = "calculator"
            elif "cmd" in prompt_lower:
                target_app = "cmd"
            elif "powershell" in prompt_lower or "pwsh" in prompt_lower:
                target_app = "powershell"
            elif "terminal" in prompt_lower or "wt" in prompt_lower:
                target_app = "wt.exe"
            elif "paint" in prompt_lower or "mspaint" in prompt_lower:
                target_app = "paint"
            elif "explorer" in prompt_lower:
                target_app = "explorer"
            elif "notepad" in prompt_lower:
                target_app = "notepad"
            else:
                match = re.search(r"(?:open|launch|start|run)\s+([a-zA-Z0-9_\-\.]+)", prompt_lower)
                if match:
                    target_app = match.group(1)

            return ModelResponse(
                tool_calls=[
                    ToolCallRequest(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="open_application",
                        arguments={"app_name": target_app}
                    )
                ]
            )

        # Direct app name keywords without "open"
        if "notepad" in prompt_lower:
            return ModelResponse(
                tool_calls=[
                    ToolCallRequest(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="open_application",
                        arguments={"app_name": "notepad"}
                    )
                ]
            )
        if "calculator" in prompt_lower or prompt_lower == "calc":
            return ModelResponse(
                tool_calls=[
                    ToolCallRequest(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="open_application",
                        arguments={"app_name": "calculator"}
                    )
                ]
            )

        # 3. Folder Creation Intent Matching
        if any(kw in prompt_lower for kw in ["folder", "directory", "make dir", "mkdir"]):
            match = re.search(r"(?:called|named)\s+([a-zA-Z0-9_\-\.]+)", user_prompt, re.IGNORECASE)
            if not match:
                match = re.search(r"(?:folder|directory)\s+([a-zA-Z0-9_\-\.]+)", user_prompt, re.IGNORECASE)

            folder_name = match.group(1) if match else "NovaFolder"
            if folder_name.lower() in ["on", "in", "the", "called", "named", "my"]:
                folder_name = "NovaFolder"

            if "desktop" in prompt_lower:
                target_path = Settings.USER_DESKTOP / folder_name
            elif "documents" in prompt_lower:
                target_path = Settings.USER_DOCUMENTS / folder_name
            else:
                target_path = Settings.DEFAULT_WORKSPACE / folder_name

            return ModelResponse(
                tool_calls=[
                    ToolCallRequest(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="create_folder",
                        arguments={"folder_path": str(target_path.resolve())}
                    )
                ]
            )

        # 4. File Search Intent Matching
        if any(kw in prompt_lower for kw in ["find", "search", "locate"]):
            return ModelResponse(
                tool_calls=[
                    ToolCallRequest(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="find_file",
                        arguments={"pattern": "*.txt", "max_results": 5}
                    )
                ]
            )

        # 5. Screenshot Intent Matching
        if any(kw in prompt_lower for kw in ["screenshot", "screen", "capture"]):
            return ModelResponse(
                tool_calls=[
                    ToolCallRequest(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="take_screenshot",
                        arguments={"filename_prefix": "nova_test"}
                    )
                ]
            )

        # Default fallback response
        return ModelResponse(
            text=f"Nova Mock Provider received request: '{user_prompt}'."
        )
