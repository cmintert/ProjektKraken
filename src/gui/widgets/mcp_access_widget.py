"""Presentation-only controls for explicitly sharing saved world facts."""

import json
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from src.core.mcp_access import DISCLOSURE
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.editor_presentation import DisclosureButton
from src.gui.widgets.wrapping_buttons import WrappingPushButton


class McpAccessWidget(QWidget):
    """Emit session intent separately from Settings Apply/Cancel drafts."""

    enable_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a compact, keyboard-accessible integration form."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(layout)
        heading = QLabel("Local AI access (MCP)")
        layout.addWidget(heading)
        self.status = QLabel("Off")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        for text in (
            DISCLOSURE,
            "Only saved Entity/Event content is shared. Unsaved drafts, files and "
            "credentials are excluded. Sharing includes the current saved world; "
            "Kraken cannot identify secrets you have written into its prose.",
            "Access is local to this computer and available to configured clients "
            "under your user account. Restarting Kraken requires enabling again. "
            "These actions take effect immediately, independently of Apply/Cancel.",
        ):
            label = QLabel(text)
            label.setWordWrap(True)
            layout.addWidget(label)
        self.enable_button = WrappingPushButton("Enable for this session")
        self.stop_button = WrappingPushButton("Stop sharing")
        declare_inspection(
            self.enable_button,
            "mcp.enable|integrations.mcp|help-mcp-enable",
        )
        declare_inspection(
            self.stop_button,
            "mcp.stop|integrations.mcp|help-mcp-stop",
        )
        self.enable_button.clicked.connect(self.enable_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        layout.addWidget(self.enable_button)
        layout.addWidget(self.stop_button)
        setup = QLabel(
            "Configure your client once to launch KrakenMCP.exe from the Kraken "
            "installation folder. Source checkouts use Python with "
            "-m src.integrations.mcp.connector. No credential belongs in the "
            "client configuration. See Help for client examples and limitations."
        )
        setup.setWordWrap(True)
        layout.addWidget(setup)
        self.details = DisclosureButton("Activity details", self)
        declare_inspection(
            self.details, "mcp.activity|integrations.mcp|help-mcp-activity"
        )
        self.activity = declare_inspection(
            QPlainTextEdit(), "mcp.activity|integrations.mcp|help-mcp-activity"
        )
        self.activity.setReadOnly(True)
        self.activity.setAccessibleName("Local MCP activity")
        self.activity.hide()
        self.details.toggled.connect(self.activity.setVisible)
        layout.addWidget(self.details)
        layout.addWidget(self.activity)
        layout.addStretch()

    def render_state(self, state: dict[str, Any]) -> None:
        """Render detached state without persisting preferences or reading data."""
        self.status.setText(
            f"{state['state']} — {state['world_name']}\n{state['message']}"
        )
        self.enable_button.setEnabled(state["state"] == "Off" and state["available"])
        self.enable_button.setToolTip(
            "Share saved facts for this session"
            if state["available"]
            else "Open a world before enabling local AI access"
        )
        self.stop_button.setEnabled(state["state"] in {"Starting", "Active"})
        self.activity.setPlainText(json.dumps(state["activity"], indent=2))
