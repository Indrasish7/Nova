"""
Nova Configuration Module.

Stores system defaults, paths, security parameters, logging options, and hotkey settings.
Automatically loads local .env configuration if present.
"""

from pathlib import Path
import os
import tempfile
from typing import List

# Automatically load local .env configuration if present
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k:
                        os.environ[_k] = _v
    except Exception:
        pass


class Settings:
    """Application settings for Nova V0.3."""
    
    APP_NAME: str = "Nova"
    VERSION: str = "0.3.0"
    
    # Global Launcher Hotkey (Default: Ctrl + Space)
    HOTKEY_MODIFIERS: List[str] = ["ctrl"]
    HOTKEY_KEY: str = "space"
    
    # Storage & Paths
    SCREENSHOT_DIR: Path = Path(tempfile.gettempdir()) / "nova_screenshots"
    DEFAULT_WORKSPACE: Path = Path(os.getcwd())
    USER_DESKTOP: Path = Path.home() / "Desktop"
    USER_DOCUMENTS: Path = Path.home() / "Documents"
    
    # Allowed search/creation roots for safety
    ALLOWED_ROOTS: List[Path] = [
        Path.home(),
        Path(tempfile.gettempdir()),
        DEFAULT_WORKSPACE,
    ]
    
    # Model & Provider Settings
    NOVA_MODEL_PROVIDER: str = os.getenv("NOVA_MODEL_PROVIDER", "gemini").lower()
    
    # Gemini API Credentials & Options
    GEMINI_API_KEY: str = os.getenv("NOVA_GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    GEMINI_BASE_URL: str = os.getenv(
        "NOVA_GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai"
    ).rstrip("/")
    
    # Default model for V0.3: gemini-2.5-flash
    MODEL_NAME: str = os.getenv("NOVA_MODEL_NAME", "gemini-2.5-flash")
    
    # Maximum reasoning/tool loop iterations per request
    NOVA_MAX_AGENT_STEPS: int = int(os.getenv("NOVA_MAX_AGENT_STEPS", "5"))
    
    # User-Configurable Interaction Policy Mode ('BALANCED' or 'STRICT')
    INTERACTION_MODE: str = os.getenv("NOVA_INTERACTION_MODE", "BALANCED").upper()

    # Ephemeral artifact retention policy (seconds)
    OBSERVATION_RETENTION_SECONDS: int = int(os.getenv("NOVA_OBSERVATION_RETENTION", "300"))

    # Generic OpenAI-compatible settings (fallback/other endpoints)
    OPENAI_API_KEY: str = os.getenv("NOVA_OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    OPENAI_BASE_URL: str = os.getenv("NOVA_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    
    # Observability & Logging Level
    LOG_LEVEL: str = os.getenv("NOVA_LOG_LEVEL", "INFO").upper()

    # System Instruction / Nova Identity
    SYSTEM_PROMPT: str = (
        "You are Nova, an AI-native Windows desktop control layer assistant.\n"
        "You help the user interact with their Windows PC safely through natural language.\n"
        "IMPORTANT RULES:\n"
        "1. You can ONLY perform real-world Windows actions through explicitly registered tools.\n"
        "2. SEMANTIC UI INTERACTION IS YOUR PRIMARY ACTION: When a user asks to click, select, or interact with a UI element, button, tab, menu, or control in an application, ALWAYS invoke `semantic_click` first with `target_name`, `application_context` (e.g. 'Calculator', 'Task Manager', 'Notepad'), and optional `control_type` (e.g. 'Button', 'TabItem').\n"
        "3. DO NOT invoke `screen_observe` or coordinate `mouse_click` when the user request refers to a named UI element. Only use `screen_observe` and physical `mouse_click` as a last-resort fallback when `semantic_click` returns NOT_FOUND or UNAVAILABLE.\n"
        "4. MOUSE COORDINATE RULE: When physical mouse tools are required as a fallback, specify coordinates in exact physical screen pixels matching the screenshot resolution (0 <= X <= width-1, 0 <= Y <= height-1).\n"
        "5. Never invent non-existent tool capabilities or claim an action succeeded unless confirmed by a successful tool result.\n"
        "6. ELEVATION BOUNDARY: If an application runs with elevated Administrator privileges and Nova reports ELEVATION_REQUIRED, do NOT attempt physical fallback clicks because Windows UIPI blocks them. Inform the user clearly that Nova must be run as Administrator to interact with that application.\n"
        "7. Do not attempt to bypass security policies or perform unauthorized operations.\n"
        "8. Respond concisely, professionally, and accurately after completing tool executions."
    )

    @classmethod
    def is_path_allowed(cls, target_path: Path) -> bool:
        """Check whether target_path resides within allowed root directories."""
        try:
            resolved = target_path.resolve()
            for root in cls.ALLOWED_ROOTS:
                try:
                    resolved_root = root.resolve()
                    if resolved == resolved_root or resolved_root in resolved.parents:
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    @classmethod
    def resolve_user_path(cls, path_str: str) -> Path:
        """
        Resolve user path alias (e.g. 'Desktop', 'Documents', '~') to explicit system path.
        """
        if not path_str:
            return cls.DEFAULT_WORKSPACE.resolve()

        clean_lower = path_str.strip().lower()

        # Check for Desktop keyword or subfolder
        if "desktop" in clean_lower:
            parts = [p for p in path_str.replace("\\", "/").split("/") if p.lower() not in ["desktop", "my desktop", "the desktop", "on my desktop", "in my desktop", "on desktop", ""]]
            folder_name = parts[-1] if parts else ""
            if folder_name:
                return (cls.USER_DESKTOP / folder_name).resolve()
            return cls.USER_DESKTOP.resolve()

        # Check for Documents keyword or subfolder
        if "documents" in clean_lower:
            parts = [p for p in path_str.replace("\\", "/").split("/") if p.lower() not in ["documents", "my documents", "in documents", ""]]
            folder_name = parts[-1] if parts else ""
            if folder_name:
                return (cls.USER_DOCUMENTS / folder_name).resolve()
            return cls.USER_DOCUMENTS.resolve()

        # Standard path expansion
        return Path(path_str).expanduser().resolve()


# Ensure screenshot directory exists
Settings.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
