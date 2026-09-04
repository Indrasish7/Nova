"""
Find File Tool.

Searches for files matching glob patterns within allowed filesystem locations.
Returns rich structured metadata including size, path, extension, and timestamps.
"""

from pathlib import Path
import os
import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from nova.tools.base import BaseTool, ToolResult
from nova.permissions.level import PermissionLevel, ActionContext
from nova.config import Settings


class FindFileInput(BaseModel):
    """Input parameters for find_file tool."""
    pattern: str = Field(
        ...,
        description="File pattern or filename to search for (e.g. '*.txt', 'report.pdf', 'data*')"
    )
    search_root: Optional[str] = Field(
        None,
        description="Optional directory path to search within. Must be within allowed roots."
    )
    max_results: int = Field(
        50,
        description="Maximum number of file search results to return (default 50)."
    )


class FileInfo(BaseModel):
    """Structured file metadata item."""
    filename: str
    absolute_path: str
    extension: str
    size_bytes: int
    created_at: str
    modified_at: str


class FindFileTool(BaseTool):
    """Tool for locating files within allowed roots."""

    name: str = "find_file"
    description: str = "Searches for files matching a pattern within allowed directories and returns detailed file metadata."
    args_model = FindFileInput
    default_permission = PermissionLevel.SAFE

    def evaluate_permission(self, args: FindFileInput, context: ActionContext) -> PermissionLevel:
        if args.search_root:
            root_path = Path(args.search_root)
            if not Settings.is_path_allowed(root_path):
                return PermissionLevel.REQUIRES_CONFIRMATION
        return PermissionLevel.SAFE

    def execute(self, args: FindFileInput, context: ActionContext) -> ToolResult:
        try:
            # Determine search root
            if args.search_root:
                root_path = Path(args.search_root).resolve()
                if not Settings.is_path_allowed(root_path):
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"Search path '{root_path}' is outside permitted directory roots."
                    )
                search_roots = [root_path]
            else:
                search_roots = Settings.ALLOWED_ROOTS

            matches: List[FileInfo] = []
            
            for root in search_roots:
                if not root.exists() or not root.is_dir():
                    continue

                try:
                    # Glob search up to max depth / count
                    for item in root.rglob(args.pattern):
                        if item.is_file():
                            stat = item.stat()
                            created_time = datetime.datetime.fromtimestamp(stat.st_ctime, tz=datetime.timezone.utc).isoformat()
                            modified_time = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).isoformat()

                            file_info = FileInfo(
                                filename=item.name,
                                absolute_path=str(item.resolve()),
                                extension=item.suffix.lower(),
                                size_bytes=stat.st_size,
                                created_at=created_time,
                                modified_at=modified_time,
                            )
                            matches.append(file_info)

                            if len(matches) >= args.max_results:
                                break
                except Exception:
                    # Skip unreadable subdirectories smoothly
                    continue

                if len(matches) >= args.max_results:
                    break

            results_data = [info.model_dump() for info in matches]

            return ToolResult(
                success=True,
                output=results_data,
                metadata={
                    "pattern": args.pattern,
                    "count": len(matches),
                    "max_results": args.max_results
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Error executing find_file search: {str(e)}"
            )
