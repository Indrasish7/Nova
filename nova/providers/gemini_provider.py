"""
Gemini Model Provider.

Official Gemini API Provider implementing the provider-agnostic ModelProvider interface
via Gemini's official OpenAI-compatible Chat Completions endpoint, with Vision support.
"""

import json
import base64
from pathlib import Path
from typing import List, Optional, Set
import httpx

from nova.providers.base import ModelProvider, ModelCapability, ChatMessage, ModelResponse, ToolCallRequest
from nova.tools.base import ToolDefinition
from nova.config import Settings
from nova.logger import log_provider_error


class GeminiProvider(ModelProvider):
    """
    Provider for official Google Gemini Models using the Chat Completions API.
    Supports TEXT, TOOL_CALLING, and VISION capabilities.
    Default model: gemini-2.5-flash.
    """

    capabilities: Set[ModelCapability] = {
        ModelCapability.TEXT,
        ModelCapability.TOOL_CALLING,
        ModelCapability.VISION,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "",
        model_name: str = ""
    ):
        self.api_key = Settings.GEMINI_API_KEY if api_key is None else api_key
        self.base_url = (base_url or Settings.GEMINI_BASE_URL).rstrip("/")
        self.model_name = model_name or Settings.MODEL_NAME

    def generate(
        self,
        messages: List[ChatMessage],
        tools: List[ToolDefinition]
    ) -> ModelResponse:
        """
        Generate model response or function calls from Gemini API.
        Supports multimodal image input payloads for vision tasks.
        """
        if not self.api_key:
            err_msg = (
                "Gemini API key is not configured. Please set the NOVA_GEMINI_API_KEY "
                "environment variable to run with Gemini."
            )
            log_provider_error("Gemini", err_msg)
            return ModelResponse(text=err_msg)

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
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
                            "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments)
                        }
                    }
                    for tc in msg.tool_calls
                ]
            
            formatted_messages.append(item)

            # If message attaches an image artifact, append user multimodal message containing base64 data
            if msg.image_path and Path(msg.image_path).exists():
                try:
                    with open(msg.image_path, "rb") as img_file:
                        b64_data = base64.b64encode(img_file.read()).decode("utf-8")
                    
                    formatted_messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Screen observation artifact:"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_data}"}}
                        ]
                    })
                except Exception:
                    pass

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
                
                if response.status_code == 401:
                    err_msg = "Gemini API authentication failed (401 Unauthorized). Please check your NOVA_GEMINI_API_KEY."
                    log_provider_error("Gemini", err_msg)
                    return ModelResponse(text=err_msg)

                response.raise_for_status()
                data = response.json()

            choice = data["choices"][0]["message"]
            text_content = choice.get("content")

            tool_calls = []
            if "tool_calls" in choice and choice["tool_calls"]:
                for tc in choice["tool_calls"]:
                    fn = tc["function"]
                    raw_args = fn.get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args)
                        except Exception:
                            args = {}
                    else:
                        args = raw_args

                    tool_calls.append(
                        ToolCallRequest(
                            id=tc.get("id", "call_gemini"),
                            name=fn["name"],
                            arguments=args
                        )
                    )

            return ModelResponse(text=text_content, tool_calls=tool_calls)

        except httpx.TimeoutException:
            err_msg = f"Gemini API request timed out ({self.model_name})."
            log_provider_error("Gemini", err_msg)
            return ModelResponse(text=err_msg)

        except Exception as e:
            err_msg = f"Error connecting to Gemini API ({self.model_name}): {str(e)}"
            log_provider_error("Gemini", err_msg)
            return ModelResponse(text=err_msg)
