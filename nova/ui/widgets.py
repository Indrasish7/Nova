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
            "QFrame { background-color: #252526; border: 1px solid #3E3E42; border-radius: 6px; padding: 10px; }"
        )
        details_layout = QVBoxLayout(details_frame)
        details_layout.setSpacing(6)

        is_uia = (self.tool_name == "semantic_click" or self.arguments.get("execution_type") == "uia")
        is_physical = (
            self.tool_name in ["mouse_click", "mouse_double_click", "mouse_scroll"] or
            self.arguments.get("execution_type") == "physical_fallback"
        )

        if is_uia:
            # Semantic UIA Confirmation
            action = self.arguments.get("action", "INVOKE").upper()
            target = self.arguments.get("target_name") or self.arguments.get("target") or "Unknown"
            c_type = self.arguments.get("control_type") or "Unknown"
            app_ctx = self.arguments.get("application_context") or proc_name
            p_name = self.arguments.get("process_name") or proc_name
            pattern = self.arguments.get("pattern") or (
                "SelectionItemPattern.Select()" if c_type == "TabItem" else "InvokePattern.Invoke()"
            )

            details_layout.addWidget(QLabel(f"Action: <b>{action}</b>"))
            details_layout.addWidget(QLabel(f"Target: <b>{target}</b>"))
            details_layout.addWidget(QLabel(f"Control Type: <b>{c_type}</b>"))
            details_layout.addWidget(QLabel(f"Application: <b>{app_ctx}</b>"))
            details_layout.addWidget(QLabel(f"Process: <b>{p_name}</b>"))
            
            exec_lbl = QLabel("Execution:<br><b>Windows UI Automation</b>")
            exec_lbl.setStyleSheet("color: #4EC9B0;")
            details_layout.addWidget(exec_lbl)

            pat_lbl = QLabel(f"Pattern:<br><b>{pattern}</b>")
            pat_lbl.setStyleSheet("color: #CE9178;")
            details_layout.addWidget(pat_lbl)

            mouse_lbl = QLabel("Physical Mouse: <b>NOT USED</b>")
            mouse_lbl.setStyleSheet("color: #569CD6;")
            details_layout.addWidget(mouse_lbl)

        elif is_physical:
            # Physical Fallback Confirmation
            action = "PHYSICAL_CLICK"
            target = self.arguments.get("target_description") or self.arguments.get("target") or "Custom Target"
            app_ctx = self.arguments.get("application_context") or proc_name
            coords_x = self.arguments.get("x", "Unknown")
            coords_y = self.arguments.get("y", "Unknown")

            details_layout.addWidget(QLabel(f"Action: <b>{action}</b>"))
            details_layout.addWidget(QLabel(f"Target: <b>{target}</b>"))
            details_layout.addWidget(QLabel(f"Application: <b>{app_ctx}</b>"))

            exec_lbl = QLabel("Execution:<br><b>Physical fallback via SendInput</b>")
            exec_lbl.setStyleSheet("color: #FF8C00;")
            details_layout.addWidget(exec_lbl)

            coords_lbl = QLabel(f"Coordinates:<br><b>X: {coords_x}<br>Y: {coords_y}</b>")
            details_layout.addWidget(coords_lbl)

            cursor_lbl = QLabel("Cursor Verification:<br><b>Required (±2 px)</b>")
            details_layout.addWidget(cursor_lbl)

            mouse_lbl = QLabel("Physical Mouse: <b>USED</b>")
            mouse_lbl.setStyleSheet("color: #FF4D4D;")
            details_layout.addWidget(mouse_lbl)

        else:
            # Generic Tool Confirmation
            details_layout.addWidget(QLabel(f"Action: <b>{self.tool_name}</b>"))
            args_str = "\n".join(
                f"• {k}: {v}" for k, v in self.arguments.items()
                if not k.startswith("_") and k != "target_description"
            )
            args_text = QLabel(f"Arguments:\n{args_str}")
            args_text.setFont(QFont("Consolas", 9))
            args_text.setStyleSheet("color: #CCCCCC;")
            details_layout.addWidget(args_text)

        perm_lbl = QLabel(f"Permission:<br><b>{self.permission_level.value.upper()}</b>")
        details_layout.addWidget(perm_lbl)

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
