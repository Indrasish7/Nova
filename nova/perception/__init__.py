"""
Nova Perception Package.

Provides screen observation, display information, cursor tracking,
and active window title detection.
"""

from nova.perception.models import DisplayInfo, ScreenObservation
from nova.perception.screen import ScreenPerception

__all__ = ["DisplayInfo", "ScreenObservation", "ScreenPerception"]
