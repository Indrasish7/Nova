"""
Global Hotkey Listener for Windows.

Uses Win32 RegisterHotKey via ctypes in a background QThread.
Reads hotkey configuration from Settings (default Ctrl + Space).
"""

import sys
import ctypes
from ctypes import wintypes
from PySide6.QtCore import QThread, Signal
from nova.config import Settings

# Win32 Constants
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x02
MOD_SHIFT = 0x04
MOD_WIN = 0x08
VK_SPACE = 0x20


class GlobalHotkeyThread(QThread):
    """Background thread listening for global Windows hotkey events."""
    
    hotkey_triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self.hotkey_id = 101

    def run(self):
        user32 = ctypes.windll.user32

        # Map configured modifiers
        mods = 0
        for mod in Settings.HOTKEY_MODIFIERS:
            mod_lower = mod.lower()
            if "ctrl" in mod_lower or "control" in mod_lower:
                mods |= MOD_CONTROL
            elif "alt" in mod_lower:
                mods |= MOD_ALT
            elif "shift" in mod_lower:
                mods |= MOD_SHIFT
            elif "win" in mod_lower:
                mods |= MOD_WIN

        # Map configured key
        key_code = VK_SPACE
        key_name = Settings.HOTKEY_KEY.lower()
        if key_name != "space" and len(key_name) == 1:
            key_code = ord(key_name.upper())

        # Register hotkey with Windows OS
        if not user32.RegisterHotKey(None, self.hotkey_id, mods, key_code):
            print(f"[Nova Hotkey Warning] Could not register global hotkey ({Settings.HOTKEY_MODIFIERS} + {Settings.HOTKEY_KEY}).")
            return

        msg = wintypes.MSG()
        while self._running:
            # Non-blocking or blocking message loop for Win32 MSG
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                    self.hotkey_triggered.emit()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                break

        user32.UnregisterHotKey(None, self.hotkey_id)

    def stop(self):
        self._running = False
        user32 = ctypes.windll.user32
        user32.PostQuitMessage(0)
        self.wait(1000)
