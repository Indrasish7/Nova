"""
Custom PySide6 UI Widgets for Nova.

Provides LogFeedWidget for visual request tracking and ConfirmationDialog for interactive
thread-safe security confirmation modals.
"""

from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from nova.permissions.level import PermissionLevel
from nova.permissions.engine import get_foreground_process_name


class ConfirmationDialog(QDialog):
    """Interactive Modal Dialog for User Security Confirmations."""

    def __init__(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        permission_level: PermissionLevel,
        parent=None
    ):
        super().__init__(parent)
        self.tool_name = tool_name
        self.arguments = arguments
        self.permission_level = permission_level

        self.setWindowTitle(f"Nova Security Confirmation [{permission_level.value.upper()}]")
        self.setMinimumWidth(480)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header warning banner
        header_text = f"<b>Action Requires Confirmation ({self.permission_level.value.upper()})</b>"
        if self.permission_level == PermissionLevel.DANGEROUS:
            header_text = "<font color='#FF4D4D'><b>WARNING: DANGEROUS SYSTEM ACTION DETECTED</b></font>"

        header_label = QLabel(header_text)
        header_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(header_label)

        # Foreground window / process identity
        proc_name = get_foreground_process_name()
        proc_label = QLabel(f"Target Active Window: <b>{proc_name}</b>")
        proc_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(proc_label)

        # Action Details Frame
        details_frame = QFrame()
        details_frame.setStyleSheet(
            "QFrame { background-color: #252526; border: 1px solid #3E3E42; border-radius: 6px; padding: 8px; }"
        )
        details_layout = QVBoxLayout(details_frame)
        details_layout.setSpacing(6)

        tool_label = QLabel(f"Action: <b>{self.tool_name}</b>")
        tool_label.setFont(QFont("Segoe UI", 10))
        details_layout.addWidget(tool_label)

        # Mouse specific coordinate & target description details
        if "x" in self.arguments and "y" in self.arguments:
            coords_label = QLabel(f"Coordinates: <b>(X: {self.arguments['x']}, Y: {self.arguments['y']})</b>")
            coords_label.setFont(QFont("Segoe UI", 10))
            details_layout.addWidget(coords_label)

        if "button" in self.arguments:
            btn_label = QLabel(f"Mouse Button: <b>{self.arguments['button']}</b>")
            btn_label.setFont(QFont("Segoe UI", 10))
            details_layout.addWidget(btn_label)

        if "target_description" in self.arguments and self.arguments["target_description"]:
            desc_text = f"Target Description: <i>{self.arguments['target_description']}</i> <font color='#888888'>(Informational / Untrusted)</font>"
            desc_label = QLabel(desc_text)
            desc_label.setFont(QFont("Segoe UI", 9))
            details_layout.addWidget(desc_label)

        # Raw arguments display
        args_str = "\n".join(f"• {k}: {v}" for k, v in self.arguments.items() if k not in ["target_description"])
        args_text = QLabel(f"Arguments:\n{args_str}")
        args_text.setFont(QFont("Consolas", 9))
        args_text.setStyleSheet("color: #CCCCCC;")
        details_layout.addWidget(args_text)

        layout.addWidget(details_frame)

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.deny_btn = QPushButton("Deny Action")
        self.deny_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.deny_btn.setStyleSheet(
            "QPushButton { background-color: #3E3E42; color: #FFFFFF; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #505054; }"
        )
        self.deny_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.deny_btn)

        self.approve_btn = QPushButton("Approve & Execute")
        self.approve_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.approve_btn.setStyleSheet(
            "QPushButton { background-color: #0078D4; color: #FFFFFF; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #106EBE; }"
        )
        self.approve_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.approve_btn)

        layout.addLayout(button_layout)


class LogFeedWidget(QTextEdit):
    """Read-only visual feed for displaying agent steps, logs, and responses."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet(
            "QTextEdit { background-color: #1E1E1E; color: #D4D4D4; border: 1px solid #333333; border-radius: 6px; padding: 8px; }"
        )

    def append_user(self, text: str):
        self.append(f"<font color='#569CD6'><b>[User]</b></font> {text}")

    def append_agent(self, text: str):
        self.append(f"<font color='#4EC9B0'><b>[Nova]</b></font> {text}")

    def append_system(self, text: str):
        self.append(f"<font color='#CE9178'><b>[System]</b></font> {text}")

    def append_tool(self, tool_name: str, output: str, success: bool):
        color = "#4FC1FF" if success else "#F44747"
        status = "SUCCESS" if success else "FAILED"
        self.append(f"<font color='{color}'><b>[Tool: {tool_name} ({status})]</b></font> {output}")
