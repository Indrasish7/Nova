"""
Semantic UI Click Tool.

Implements semantic element interaction using Windows UI Automation COM APIs as the primary execution mechanism
(SelectionItemPattern.Select(), InvokePattern.Invoke(), TogglePattern.Toggle(), ExpandCollapsePattern.Expand()),
with physical BoundingRectangle SendInput as a secondary fallback if UIA COM patterns are unavailable.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field

from nova.tools.base import BaseTool, ToolResult
from nova.permissions.level import PermissionLevel, ActionContext
from nova.perception.resolver import TargetResolver
from nova.perception.uia import UIAutomationResolver
from nova.perception.verifier import ActionVerifier, VerificationOutcome
from nova.tools.mouse import MouseClickTool, MouseClickInput


class SemanticClickInput(BaseModel):
    """Input parameters for semantic_click tool."""
    target_name: str = Field(..., description="Name or label of the target UI element to interact with (e.g. 'Performance', '1', 'Submit')")
    control_type: Optional[str] = Field(None, description="Optional UIA Control Type filter (e.g. 'TabItem', 'Button', 'CheckBox')")
    application_context: Optional[str] = Field(None, description="Optional target application context (e.g. 'Calculator', 'Task Manager', 'Notepad')")
    action: Literal["invoke", "select", "toggle", "expand", "collapse"] = Field("invoke", description="Semantic interaction action type")
    target_description: Optional[str] = Field(None, description="Informational description of target (untrusted)")


class SemanticClickTool(BaseTool):
    """Tool for semantic UI element resolution and pattern invocation."""

    name: str = "semantic_click"
    description: str = "Interacts with a Windows UI element by semantic name and control type using direct UI Automation COM patterns."
    args_model = SemanticClickInput
    default_permission = PermissionLevel.REQUIRES_CONFIRMATION

    def execute(self, args: SemanticClickInput, context: ActionContext) -> ToolResult:
        resolver = TargetResolver()

        # Step 1: Resolve semantic target via multi-tier TargetResolver
        res = resolver.resolve(
            target_name=args.target_name,
            control_type=args.control_type,
            application_context=args.application_context
        )

        if not res.success or not res.target:
            return ToolResult(
                success=False,
                output=None,
                error=res.error or f"Target element '{args.target_name}' could not be resolved by UI Automation.",
                metadata={"fallback_required": True}
            )

        target = res.target

        # Step 2: Check enabled state
        if not target.enabled:
            return ToolResult(
                success=False,
                output=None,
                error=f"Target UI element '{target.target_name}' ({target.control_type}) is disabled and cannot be invoked.",
                metadata={"target": target.model_dump()}
            )

        # Step 3: Primary Execution Mechanism — Direct UIA COM Pattern Invocation
        uia_resolver = UIAutomationResolver()
        pattern_success, pattern_msg, updated_meta = uia_resolver.invoke_element_pattern(
            target_name=target.target_name,
            control_type=target.control_type,
            application_context=target.process_name or args.application_context
        )

        if pattern_success:
            # Post-action verification
            ver_res = ActionVerifier.verify_semantic_click(
                target_name=target.target_name,
                via_uia_pattern=True,
                pre_obs=None,
                post_obs=None
            )
            if ver_res and (not ver_res.verified or ver_res.outcome == VerificationOutcome.VERIFICATION_FAILURE):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"VERIFICATION_FAILED: {ver_res.reason}",
                    metadata={
                        "via_uia_pattern": True,
                        "hardware_mouse_event": False,
                        "target": target.model_dump(),
                        "verification": ver_res.model_dump()
                    }
                )

            return ToolResult(
                success=True,
                output=pattern_msg,
                metadata={
                    "via_uia_pattern": True,
                    "hardware_mouse_event": False,
                    "target": target.model_dump()
                }
            )

        # Step 4: Secondary Fallback — BoundingRectangle Physical SendInput with Cursor Round-Trip Verification
        center_x, center_y = target.center_point
        mouse_tool = MouseClickTool()
        click_res = mouse_tool.execute(
            MouseClickInput(x=center_x, y=center_y, target_description=target.target_name, verify_cursor=True),
            context
        )

        if click_res.success:
            return ToolResult(
                success=True,
                output=f"Executed physical click fallback at bounding box center ({center_x}, {center_y}) for '{target.target_name}'.",
                metadata={
                    "via_uia_pattern": False,
                    "via_bounding_box_sendinput": True,
                    "hardware_mouse_event": True,
                    "target": target.model_dump()
                }
            )

        return ToolResult(
            success=False,
            output=None,
            error=f"Both UIA pattern invocation and physical fallback failed for '{target.target_name}': {click_res.error}",
            metadata={"target": target.model_dump()}
        )
