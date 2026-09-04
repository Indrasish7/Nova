"""
Nova Diagnostic Logger.

Provides structured observability for agent steps, tool executions, permission decisions,
and mouse coordinate mapping telemetry.
Never logs API keys, credentials, binary screenshot data, or sensitive user data.
"""

import logging
import sys
from typing import Optional, Dict, Any, Tuple
from nova.config import Settings


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("nova")
    logger.setLevel(getattr(logging, Settings.LOG_LEVEL, logging.INFO))
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[Nova %(levelname)s %(asctime)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger


logger = _setup_logger()


def log_agent_step(turn: int, provider: str, model: str, prompt_summary: str):
    """Log beginning of an agent reasoning step."""
    logger.info(f"Step {turn} | Provider: {provider} | Model: {model} | Prompt: '{prompt_summary[:60]}...'")


def log_tool_decision(tool_name: str, permission_level: str, approved: bool):
    """Log permission engine evaluation and confirmation status."""
    logger.info(f"Tool Selection: '{tool_name}' | Permission: {permission_level} | Approved: {approved}")


def log_tool_execution(tool_name: str, success: bool, latency_ms: float, error: Optional[str] = None):
    """Log tool execution result and latency."""
    status = "SUCCESS" if success else "FAILED"
    err_str = f" | Error: {error}" if error else ""
    logger.info(f"Tool Executed: '{tool_name}' | Status: {status} | Latency: {latency_ms:.1f}ms{err_str}")


def log_mouse_coordinate_transform(
    screenshot_w: int,
    screenshot_h: int,
    screen_w: int,
    screen_h: int,
    model_x: int,
    model_y: int,
    trans_x: int,
    trans_y: int,
    norm_x: int,
    norm_y: int,
    actual_cursor: Tuple[int, int]
):
    """Log observable mouse coordinate translation telemetry without logging binary image bytes."""
    logger.info(
        f"Mouse Mapping | Screenshot: {screenshot_w}x{screenshot_h} | Display: {screen_w}x{screen_h} | "
        f"Model Input: ({model_x}, {model_y}) | Physical Target: ({trans_x}, {trans_y}) | "
        f"SendInput Norm: ({norm_x}, {norm_y}) | Cursor After: {actual_cursor}"
    )


def log_provider_error(provider: str, error_msg: str):
    """Log provider connection or response errors safely."""
    logger.error(f"Provider Error [{provider}]: {error_msg}")
