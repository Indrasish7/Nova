"""
Base Tool Definition & Result Models.
"""

from abc import ABC, abstractmethod
from typing import Type, Dict, Any, Optional
from pydantic import BaseModel, Field

from nova.permissions.level import PermissionLevel, ActionContext


class ToolResult(BaseModel):
    """Structured output returned by any tool execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    """JSON Schema definition passed to LLM for tool choice."""
    name: str
    description: str
    parameters: Dict[str, Any]


class BaseTool(ABC):
    """
    Abstract base class for all Nova tools.
    
    ARCHITECTURAL INVARIANT:
    Tools must never call the LLM or ModelProvider directly.
    Tools must remain pure deterministic operations that receive validated
    Pydantic arguments and return structured ToolResults.
    """

    name: str
    description: str
    args_model: Type[BaseModel]
    default_permission: PermissionLevel = PermissionLevel.SAFE

    def get_definition(self) -> ToolDefinition:
        """Generate LLM-compatible tool definition schema."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.args_model.model_json_schema()
        )

    def evaluate_permission(self, args: BaseModel, context: ActionContext) -> PermissionLevel:
        """
        Evaluate permission required for these specific arguments and context.
        Subclasses can override for argument-specific checks.
        """
        return self.default_permission

    @abstractmethod
    def execute(self, args: BaseModel, context: ActionContext) -> ToolResult:
        """Execute the tool deterministically and return structured ToolResult."""
        pass
