"""
Semantic UI Click Tool.

Implements semantic element interaction using Windows UI Automation COM APIs as the primary execution mechanism
(SelectionItemPattern.Select(), InvokePattern.Invoke(), TogglePattern.Toggle(), ExpandCollapsePattern.Expand()),
with physical BoundingRectangle SendInput as a secondary fallback if UIA COM patterns are unavailable.
Enforces post-action state verification and prevents false success reports.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field

from nova.tools.base import BaseTool, ToolResult
from nova.permissions.level import PermissionLevel, ActionContext
from nova.perception.resolver import TargetResolver
from nova.perception.uia import UIAutomationResolver
from nova.perception.verifier import ActionVerifier
from nova.tools.mouse import MouseClickTool, MouseClickInput


class SemanticClickInput(BaseModel):
    """Input parameters for semantic_click tool."""
    target_name: str = Field(..., description="Name or label of the target UI element to interact with (e.g. 'Performance', '1', 'Submit')")
    control_type: Optional[str] = Field(None, description="Optional UIA Control Type filter (e.g. 'TabItem', 'Button', 'CheckBox')")
    application_context: Optional[str] = Field(None, description="Optional target application context (e.g. 'Calculator', 'Task Manager', 'Notepad')")
    action: Literal["invoke", "select", "toggle", "expand", "collapse"] = Field("invoke", description="Semantic interaction action type")
    target_description: Optional[str] = Field(None, description="Informational description of target (untrusted)")


class SemanticClickTool(BaseTool):
    """Tool for semantic UI element resolution, pattern invocation, and state verification."""

    name: str = "semantic_click"
    description: str = "Interacts with a Windows UI element by semantic name and control type using direct UI Automation COM patterns."
    args_model = SemanticClickInput
    default_permission = PermissionLevel.REQUIRES_CONFIRMATION

    def _get_calculator_display_text(self) -> Optional[str]:
        """Helper to extract current CalculatorResults display text for verification."""
        try:
            resolver = UIAutomationResolver()
            res = resolver.resolve_element("CalculatorResults", application_context="Calculator")
            if res.success and res.element:
                return res.element.name
        except Exception:
            pass
        return None

    def execute(self, args: SemanticClickInput, context: ActionContext) -> ToolResult:
        resolver = TargetResolver()
        app_ctx = args.application_context or ""

        # Capture pre-action Calculator display state if applicable
        pre_display = self._get_calculator_display_text()

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
                error=f"RESOLUTION_FAILED: Target element '{args.target_name}' could not be resolved by UI Automation for application_context='{app_ctx}'. {res.error or ''}",
                metadata={"status": "RESOLUTION_FAILED", "fallback_required": True}
            )

        target = res.target

        # Step 2: Check enabled state
        if not target.enabled:
            return ToolResult(
                success=False,
                output=None,
                error=f"PERMISSION_DENIED: Target UI element '{target.target_name}' ({target.control_type}) is disabled and cannot be invoked.",
                metadata={"status": "PERMISSION_DENIED", "target": target.model_dump()}
            )

        # Step 3: Primary Execution Mechanism — Direct UIA COM Pattern Invocation
        uia_resolver = UIAutomationResolver()
        pattern_success, pattern_msg, updated_meta = uia_resolver.invoke_element_pattern(
            target_name=target.target_name,
            control_type=target.control_type,
            application_context=target.process_name or args.application_context
        )

        if pattern_success:
            # Capture post-action Calculator display state for verification
            post_display = self._get_calculator_display_text()

            # Post-action verification
            ver_res = ActionVerifier.verify_semantic_click(
                target_name=target.target_name,
                via_uia_pattern=True,
                pre_obs=None,
                post_obs=None,
                pre_meta=target.model_dump(),
                post_meta=updated_meta.model_dump() if updated_meta else None,
                pre_display=pre_display,
                post_display=post_display
            )

            if not ver_res.verified:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"VERIFICATION_FAILED: {ver_res.reason}",
                    metadata={"status": "VERIFICATION_FAILED", "verification": ver_res.model_dump(), "target": target.model_dump()}
                )

            return ToolResult(
                success=True,
                output=f"{pattern_msg} Verification: {ver_res.reason}",
                metadata={
                    "status": "SUCCESS",
                    "via_uia_pattern": True,
                    "hardware_mouse_event": False,
                    "target": target.model_dump(),
                    "verification": ver_res.model_dump()
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
                    "status": "SUCCESS",
                    "via_uia_pattern": False,
                    "via_bounding_box_sendinput": True,
                    "hardware_mouse_event": True,
                    "target": target.model_dump()
                }
            )

        return ToolResult(
            success=False,
            output=None,
            error=f"INVOCATION_FAILED: Both UIA pattern invocation and physical fallback failed for '{target.target_name}': {click_res.error}",
            metadata={"status": "INVOCATION_FAILED", "target": target.model_dump()}
        )
