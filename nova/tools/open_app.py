"""
Open Application Tool.

Launches standard Windows desktop applications via AppResolver allowlist.
"""

import subprocess
import os
from pydantic import BaseModel, Field

from nova.tools.base import BaseTool, ToolResult
from nova.tools.app_resolver import AppResolver
from nova.permissions.level import PermissionLevel, ActionContext


class OpenAppInput(BaseModel):
    """Input parameters for open_application tool."""
    app_name: str = Field(
        ...,
        description="Name of application to launch (e.g. 'notepad', 'calculator', 'file explorer', 'paint')"
    )


class OpenAppTool(BaseTool):
    """Tool for opening validated Windows applications."""

    name: str = "open_application"
    description: str = "Safely launches a recognized Windows desktop application by name (e.g. notepad, calc, explorer)."
    args_model = OpenAppInput
    default_permission = PermissionLevel.SAFE

    def evaluate_permission(self, args: OpenAppInput, context: ActionContext) -> PermissionLevel:
        resolved = AppResolver.resolve(args.app_name)
        if not resolved.is_allowed:
            return PermissionLevel.DANGEROUS
        return PermissionLevel.SAFE

    def execute(self, args: OpenAppInput, context: ActionContext) -> ToolResult:
        resolved = AppResolver.resolve(args.app_name)
        
        if not resolved.is_allowed:
            return ToolResult(
                success=False,
                output=None,
                error=resolved.reason or f"Application '{args.app_name}' is not permitted."
            )

        try:
            # Safe Windows launch using resolved executable via os.startfile (or subprocess.Popen fallback)
            if hasattr(os, "startfile"):
                os.startfile(resolved.executable)
            else:
                subprocess.Popen([resolved.executable], shell=False)

            return ToolResult(
                success=True,
                output=f"Successfully launched '{resolved.name}' ({resolved.executable}).",
                metadata={
                    "app_name": args.app_name,
                    "executable": resolved.executable
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Unable to open application '{args.app_name}': {str(e)}"
            )
