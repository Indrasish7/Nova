"""
Tool Registry.

Central registry for registering, retrieving, and discovering tools.
"""

from typing import Dict, List, Optional
from nova.tools.base import BaseTool, ToolDefinition


class ToolRegistry:
    """Registry managing available tools in Nova."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieve tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """List registered tools."""
        return list(self._tools.values())

    def get_definitions(self) -> List[ToolDefinition]:
        """Return LLM-compatible definitions for all registered tools."""
        return [tool.get_definition() for tool in self._tools.values()]


def create_default_registry() -> ToolRegistry:
    """Create and populate registry with initial Nova tools."""
    from nova.tools.open_app import OpenAppTool
    from nova.tools.create_folder import CreateFolderTool
    from nova.tools.find_file import FindFileTool
    from nova.tools.screenshot import TakeScreenshotTool
    from nova.tools.screen_observe import ScreenObserveTool
    from nova.tools.mouse import (
        MouseMoveTool, MouseClickTool, MouseDoubleClickTool, MouseScrollTool
    )
    from nova.tools.semantic_click import SemanticClickTool

    registry = ToolRegistry()
    registry.register(OpenAppTool())
    registry.register(CreateFolderTool())
    registry.register(FindFileTool())
    registry.register(TakeScreenshotTool())
    registry.register(ScreenObserveTool())
    
    # Phase B Mouse Tools
    registry.register(MouseMoveTool())
    registry.register(MouseClickTool())
    registry.register(MouseDoubleClickTool())
    registry.register(MouseScrollTool())

    # Phase B.5 Semantic Interaction Tool
    registry.register(SemanticClickTool())

    return registry
