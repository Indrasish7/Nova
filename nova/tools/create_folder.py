"""
Create Folder Tool.

Creates directories safely within permitted file system locations.
"""

from pathlib import Path
from pydantic import BaseModel, Field

from nova.tools.base import BaseTool, ToolResult
from nova.permissions.level import PermissionLevel, ActionContext
from nova.config import Settings


class CreateFolderInput(BaseModel):
    """Input parameters for create_folder tool."""
    folder_path: str = Field(
        ...,
        description="Directory path to create (e.g. 'C:\\Users\\<user>\\Desktop\\NewFolder' or relative path/alias)"
    )


class CreateFolderTool(BaseTool):
    """Tool for creating local directory folders."""

    name: str = "create_folder"
    description: str = "Creates a new folder at the specified filesystem directory path or user directory alias."
    args_model = CreateFolderInput
    default_permission = PermissionLevel.REQUIRES_CONFIRMATION

    def evaluate_permission(self, args: CreateFolderInput, context: ActionContext) -> PermissionLevel:
        target = Settings.resolve_user_path(args.folder_path)
        
        # Check system folders
        path_str = str(target).lower()
        if any(sys_dir in path_str for sys_dir in ["system32", "windows\\system", "program files"]):
            return PermissionLevel.DANGEROUS

        # Check allowed roots
        if not Settings.is_path_allowed(target):
            return PermissionLevel.REQUIRES_CONFIRMATION

        return PermissionLevel.REQUIRES_CONFIRMATION

    def execute(self, args: CreateFolderInput, context: ActionContext) -> ToolResult:
        try:
            target_path = Settings.resolve_user_path(args.folder_path)
            
            # Map Public\Desktop to actual personal Desktop directory to avoid WinError 5 Access Denied
            if "public\\desktop" in str(target_path).lower():
                target_path = (Settings.USER_DESKTOP / target_path.name).resolve()

            if target_path.exists() and target_path.is_dir():
                return ToolResult(
                    success=True,
                    output=f"Folder already exists at '{target_path}'.",
                    metadata={"path": str(target_path), "created": False}
                )

            target_path.mkdir(parents=True, exist_ok=True)
            return ToolResult(
                success=True,
                output=f"Successfully created folder at '{target_path}'.",
                metadata={"path": str(target_path), "created": True}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Failed to create folder at '{args.folder_path}': {str(e)}"
            )
