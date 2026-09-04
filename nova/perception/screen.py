"""
Screen Perception Engine.

Captures explicit desktop screen observations, cursor coordinates, and foreground window titles
using Pillow and native Windows Win32 APIs.
"""

from pathlib import Path
import datetime
import uuid
import os
import time
import ctypes
from ctypes import wintypes
from typing import Tuple, Optional
from PIL import ImageGrab, Image

from nova.perception.models import DisplayInfo, ScreenObservation
from nova.config import Settings


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class ScreenPerception:
    """Perception engine capturing structured desktop screen observations."""

    def __init__(self, screenshot_dir: Optional[Path] = None):
        self.screenshot_dir = screenshot_dir or Settings.SCREENSHOT_DIR

    def get_display_info(self) -> DisplayInfo:
        """Get primary screen dimensions."""
        try:
            user32 = ctypes.windll.user32
            width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            height = user32.GetSystemMetrics(1) # SM_CYSCREEN
            if width > 0 and height > 0:
                return DisplayInfo(width=width, height=height)
        except Exception:
            pass

        # Fallback using Pillow
        try:
            img = ImageGrab.grab()
            return DisplayInfo(width=img.width, height=img.height)
        except Exception:
            return DisplayInfo(width=1920, height=1080)

    def get_cursor_position(self) -> Tuple[int, int]:
        """Get current cursor (x, y) coordinates using Win32 API."""
        try:
            pt = POINT()
            if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                return (int(pt.x), int(pt.y))
        except Exception:
            pass
        return (0, 0)

    def get_active_window_title(self) -> str:
        """Get title of current foreground window using Win32 API."""
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    return buff.value
        except Exception:
            pass
        return "Desktop"

    def capture_observation(self, reason: str = "observation") -> ScreenObservation:
        """
        Capture a single explicit screen observation.
        Saves an ephemeral screenshot artifact and records display metrics.
        """
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        file_name = f"obs_{uuid.uuid4().hex[:8]}.png"
        file_path = self.screenshot_dir / file_name

        # Capture screenshot using Pillow with headless fallback
        try:
            img = ImageGrab.grab()
            width, height = img.size
        except Exception:
            width, height = 1920, 1080
            img = Image.new("RGB", (width, height), color=(30, 30, 30))

        img.save(file_path, format="PNG")

        cursor_x, cursor_y = self.get_cursor_position()
        active_title = self.get_active_window_title()

        return ScreenObservation(
            timestamp=timestamp_str,
            width=width,
            height=height,
            cursor_x=cursor_x,
            cursor_y=cursor_y,
            active_window_title=active_title,
            image_path=str(file_path.resolve()),
            metadata={"reason": reason}
        )

    def cleanup_ephemeral_screenshots(self, max_age_seconds: int = 300):
        """Clean up ephemeral observation screenshots older than max_age_seconds."""
        now = time.time()
        try:
            for file_path in self.screenshot_dir.glob("obs_*.png"):
                if file_path.is_file():
                    age = now - file_path.stat().st_mtime
                    if age > max_age_seconds:
                        try:
                            file_path.unlink()
                        except Exception:
                            pass
        except Exception:
            pass
