"""
Main PySide6 Application Window for Nova.

Spotlight/Raycast-style floating command launcher for Windows.
Handles Ctrl + Space global toggle, prompt submission, background agent execution,
and thread-safe interactive security confirmation modals.
"""

import sys
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLineEdit
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont, QKeySequence, QShortcut

from nova.config import Settings
from nova.runtime.agent import Agent, AgentStepResult
from nova.providers.mock import MockModelProvider
from nova.providers.openai_provider import OpenAICompatibleProvider
from nova.providers.gemini_provider import GeminiProvider
from nova.permissions.level import PermissionLevel
from nova.ui.hotkey import GlobalHotkeyThread
from nova.ui.widgets import ConfirmationDialog, LogFeedWidget


class AgentWorker(QThread):
    """Background worker thread to run Agent execution without freezing UI."""

    finished_signal = Signal(object)

    def __init__(self, agent: Agent, prompt: str, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.prompt = prompt

    def run(self):
        try:
            result = self.agent.run(self.prompt)
            self.finished_signal.emit(result)
        except Exception as e:
            error_result = AgentStepResult(
                success=False,
                final_text=f"Nova encountered an error processing request: {str(e)}",
                tool_calls_executed=[],
                permission_denied=False
            )
            self.finished_signal.emit(error_result)


class NovaWindow(QMainWindow):
    """Nova Launcher Overlay Window."""

    # Thread-safe confirmation request signal (tool_name, arguments, perm_level_str, event, result_dict)
    request_confirmation_signal = Signal(str, dict, str, object, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nova AI Launcher")
        self.setMinimumSize(650, 420)
        self.resize(700, 450)

        # Set window flags for floating overlay launcher
        self.setWindowFlags(
            Qt.Window | Qt.WindowStaysOnTopHint
        )

        self._setup_ui()
        self._setup_agent()
        self._setup_hotkey()

        # Connect thread-safe confirmation request signal to GUI thread slot
        self.request_confirmation_signal.connect(self._on_request_confirmation_slot)

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Input line
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(
            f"Ask Nova... (Default hotkey: {'+'.join(Settings.HOTKEY_MODIFIERS).title()} + {Settings.HOTKEY_KEY.title()})"
        )
        self.input_field.setFont(QFont("Segoe UI", 11))
        self.input_field.setStyleSheet(
            "QLineEdit { padding: 10px; background-color: #252526; color: #FFFFFF; border: 1px solid #0078D4; border-radius: 6px; }"
        )
        self.input_field.returnPressed.connect(self._on_submit)
        layout.addWidget(self.input_field)

        # Log feed
        self.log_feed = LogFeedWidget()
        layout.addWidget(self.log_feed)

        self.log_feed.append_system(
            f"Nova V{Settings.VERSION} ready. Press <b>{' + '.join(Settings.HOTKEY_MODIFIERS).title()} + {Settings.HOTKEY_KEY.title()}</b> anywhere on Windows to show/hide."
        )

        # Escape key shortcut to hide window
        self.esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.esc_shortcut.activated.connect(self.hide)

        # Position window in top-center of primary screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = int(screen.height() * 0.15)
        self.move(x, y)

    def _setup_agent(self):
        """Initialize Model Provider and Agent Runtime based on explicit configuration."""
        provider_name = Settings.NOVA_MODEL_PROVIDER

        if provider_name == "gemini":
            provider = GeminiProvider()
            if not Settings.GEMINI_API_KEY:
                self.log_feed.append_system(
                    "<b>[Configuration Warning]</b> NOVA_MODEL_PROVIDER is set to 'gemini', but no API key was found. "
                    "Set NOVA_GEMINI_API_KEY in your environment, or set NOVA_MODEL_PROVIDER=mock for offline testing."
                )
            else:
                self.log_feed.append_system(f"Active Provider: <b>Gemini ({Settings.MODEL_NAME})</b>")

        elif provider_name == "openai_compatible":
            provider = OpenAICompatibleProvider()
            self.log_feed.append_system(f"Active Provider: <b>OpenAI Compatible ({Settings.MODEL_NAME})</b>")

        else:
            provider = MockModelProvider()
            self.log_feed.append_system("Active Provider: <b>Mock Mode</b> (Deterministic Testing)")

        self.agent = Agent(
            provider=provider,
            confirmation_callback=self._handle_confirmation_callback
        )

    def _setup_hotkey(self):
        """Initialize global hotkey thread."""
        self.hotkey_thread = GlobalHotkeyThread(self)
        self.hotkey_thread.hotkey_triggered.connect(self.toggle_visibility)
        self.hotkey_thread.start()

    def toggle_visibility(self):
        """Toggle window visibility and activate focus."""
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()
            self.input_field.setFocus()

    def _handle_confirmation_callback(self, tool_name: str, arguments: dict, perm_level: PermissionLevel) -> bool:
        """
        Thread-safe confirmation callback invoked by Agent runtime.
        Delegates modal creation to the main Qt GUI thread.
        """
        app_instance = QApplication.instance()
        perm_str = perm_level.value if isinstance(perm_level, PermissionLevel) else str(perm_level)

        # If already running on GUI thread (e.g. single-threaded test context)
        if app_instance and QThread.currentThread() == app_instance.thread():
            dialog = ConfirmationDialog(tool_name, arguments, PermissionLevel(perm_str), parent=self)
            res = dialog.exec_()
            return res == ConfirmationDialog.Accepted

        # Running on background AgentWorker thread
        event = threading.Event()
        result_container = {"approved": False}

        self.request_confirmation_signal.emit(tool_name, arguments, perm_str, event, result_container)
        
        # Safely pause background worker until GUI thread resolves confirmation modal
        event.wait()
        return result_container["approved"]

    @Slot(str, dict, str, object, object)
    def _on_request_confirmation_slot(self, tool_name: str, arguments: dict, perm_level_str: str, event, result_container):
        """Slot executed strictly on the main GUI thread to display ConfirmationDialog."""
        try:
            perm_level = PermissionLevel(perm_level_str)
            dialog = ConfirmationDialog(tool_name, arguments, perm_level, parent=self)
            res = dialog.exec_()
            result_container["approved"] = (res == ConfirmationDialog.Accepted)
        except Exception as e:
            print(f"[Nova UI Warning] Confirmation dialog error: {e}")
            result_container["approved"] = False
        finally:
            event.set()

    def _on_submit(self):
        prompt = self.input_field.text().strip()
        if not prompt:
            return

        self.input_field.clear()
        self.log_feed.append_user(prompt)
        self.input_field.setEnabled(False)

        # Launch agent worker in background thread
        self.worker = AgentWorker(self.agent, prompt, self)
        self.worker.finished_signal.connect(self._on_agent_finished)
        self.worker.start()

    @Slot(object)
    def _on_agent_finished(self, result: AgentStepResult):
        self.input_field.setEnabled(True)
        self.input_field.setFocus()

        for item in result.tool_calls_executed:
            self.log_feed.append_tool(
                tool_name=item["tool"],
                output=str(item["output"]) if item["success"] else str(item.get("error")),
                success=item["success"]
            )

        if result.permission_denied:
            self.log_feed.append_system("Execution stopped due to user permission denial.")
        elif not result.success:
            self.log_feed.append_system(f"Request failed: {result.final_text}")
        else:
            self.log_feed.append_agent(result.final_text)

    def closeEvent(self, event):
        """Clean shutdown of hotkey thread on exit."""
        if hasattr(self, "hotkey_thread") and self.hotkey_thread.isRunning():
            self.hotkey_thread.stop()
        event.accept()


def run_app():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = NovaWindow()
    window.show()
    sys.exit(app.exec())
