"""
OpenAI Compatible Model Provider.

Generic HTTP provider for OpenAI-compatible APIs (OpenAI, Gemini, Ollama, LM Studio).
"""

import json
from typing import List
import httpx

from nova.providers.base import ModelProvider, ChatMessage, ModelResponse, ToolCallRequest
from nova.tools.base import ToolDefinition
from nova.config import Settings


class OpenAICompatibleProvider(ModelProvider):
    """Provider for OpenAI-compatible HTTP Chat Completions endpoint."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model_name: str = ""
    ):
        self.api_key = api_key or Settings.OPENAI_API_KEY
        self.base_url = (base_url or Settings.OPENAI_BASE_URL).rstrip("/")
        self.model_name = model_name or Settings.MODEL_NAME

    def generate(
        self,
        messages: List[ChatMessage],
        tools: List[ToolDefinition]
    ) -> ModelResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
        }

        formatted_messages = []
        for msg in messages:
            item = {"role": msg.role, "content": msg.content or ""}
            if msg.name:
                item["name"] = msg.name
            if msg.tool_call_id:
                item["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in msg.tool_calls
                ]
            formatted_messages.append(item)

        formatted_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            }
            for t in tools
        ] if tools else None

        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
        }
        if formatted_tools:
            payload["tools"] = formatted_tools

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            choice = data["choices"][0]["message"]
            text_content = choice.get("content")

            tool_calls = []
            if "tool_calls" in choice and choice["tool_calls"]:
                for tc in choice["tool_calls"]:
                    fn = tc["function"]
                    args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                    tool_calls.append(
                        ToolCallRequest(
                            id=tc["id"],
                            name=fn["name"],
                            arguments=args
                        )
                    )

            return ModelResponse(text=text_content, tool_calls=tool_calls)

        except Exception as e:
            return ModelResponse(
                text=f"Error connecting to LLM provider ({self.model_name}): {str(e)}"
            )
