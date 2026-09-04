"""
Permission Levels & Security Context.

Defines permission categories: SAFE, REQUIRES_CONFIRMATION, DANGEROUS, BLOCKED.
"""

from enum import Enum
from pydantic import BaseModel, Field


class PermissionLevel(str, Enum):
    """Security permission categories."""
    SAFE = "safe"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"


class ActionContext(BaseModel):
    """Contextual metadata passed to PermissionEngine for evaluation."""
    user_id: str = "default_user"
    workspace_path: str = ""
    is_interactive: bool = True
