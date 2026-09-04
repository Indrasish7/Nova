"""
Abstract ModelProvider Base Class & Data Models.

Provides a completely provider-agnostic abstraction for LLMs, including ModelCapabilities.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from nova.tools.base import ToolDefinition


class ModelCapability(str, Enum):
    """Capabilities supported by a ModelProvider."""
    TEXT = "text"
    TOOL_CALLING = "tool_calling"
    VISION = "vision"


class ToolCallRequest(BaseModel):
    """LLM request to invoke a specific tool with arguments."""
    id: str
    name: str
    arguments: Dict[str, Any]


class ChatMessage(BaseModel):
    """Generic chat message format."""
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCallRequest]] = None
    image_path: Optional[str] = None  # Optional image artifact reference for vision tasks


class ModelResponse(BaseModel):
    """Response returned by ModelProvider."""
    text: Optional[str] = None
    tool_calls: List[ToolCallRequest] = Field(default_factory=list)


class ModelProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    The Agent Runtime depends exclusively on this abstraction.
    """

    # Supported provider capabilities
    capabilities: Set[ModelCapability] = {ModelCapability.TEXT, ModelCapability.TOOL_CALLING}

    def supports_capability(self, capability: ModelCapability) -> bool:
        """Check whether this provider supports a specific capability."""
        return capability in self.capabilities

    @abstractmethod
    def generate(
        self,
        messages: List[ChatMessage],
        tools: List[ToolDefinition]
    ) -> ModelResponse:
        """
        Generate completion or tool call request given chat history and tools.
        """
        pass
