"""
Screen Observe Tool.

Captures an explicit visual observation of the desktop display.
Returns structured metadata (dimensions, cursor coordinates, active window title, image path).
"""

from pydantic import BaseModel, Field
from nova.tools.base import BaseTool, ToolResult
from nova.permissions.level import PermissionLevel, ActionContext
from nova.perception.screen import ScreenPerception


class ScreenObserveInput(BaseModel):
    """Input parameters for screen_observe tool."""
    reason: str = Field(
        ...,
        description="Reason visual perception is requested (e.g. 'checking open application', 'inspecting error dialog')"
    )
    include_active_window: bool = Field(
        True,
        description="Whether to include current active window title in perception metadata"
    )


class ScreenObserveTool(BaseTool):
    """Tool for capturing an explicit visual desktop screen observation."""

    name: str = "screen_observe"
    description: str = "Captures an explicit visual desktop observation including screenshot artifact, screen bounds, cursor position, and active window title."
    args_model = ScreenObserveInput
    default_permission = PermissionLevel.SAFE

    def execute(self, args: ScreenObserveInput, context: ActionContext) -> ToolResult:
        try:
            perception = ScreenPerception()
            observation = perception.capture_observation(reason=args.reason)

            # Cleanup older ephemeral artifacts
            perception.cleanup_ephemeral_screenshots()

            output_dict = observation.model_dump()
            if not args.include_active_window:
                output_dict.pop("active_window_title", None)

            return ToolResult(
                success=True,
                output=output_dict,
                metadata={
                    "image_path": observation.image_path,
                    "dimensions": f"{observation.width}x{observation.height}"
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Failed to capture screen observation: {str(e)}"
            )
