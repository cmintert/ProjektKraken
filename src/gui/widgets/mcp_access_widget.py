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
from src.gui.widgets.wrapping_choices import WrappingCheckBox as QCheckBox


class McpAccessWidget(QWidget):
    """Emit session intent separately from Settings Apply/Cancel drafts."""

    enable_requested = Signal()
    stop_requested = Signal()
    scopes_requested = Signal(list)
    prepare_requested = Signal()

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
            "Saved Entity/Event facts, calendar rules and relationship inventory "
            "are shared. Time reads also expose world Now and the live playhead. "
            "Optional scopes below add saved content. Unsaved drafts and credentials are excluded; "
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
        self.scope_boxes: dict[str, QCheckBox] = {}
        self._sharing_was_on = False
        self.scope_details = DisclosureButton("Additional sharing options", self)
        declare_inspection(
            self.scope_details, "mcp.enable|integrations.mcp|help-mcp-enable"
        )
        self.scope_choices = QWidget(self)
        choice_layout = QVBoxLayout(self.scope_choices)
        StyleHelper.apply_standard_list_spacing(choice_layout)
        self.scope_choices.hide()
        self.scope_details.toggled.connect(self.scope_choices.setVisible)
        layout.addWidget(self.scope_details)
        layout.addWidget(self.scope_choices)
        for key, text in (
            ("longform", "Share saved Longform structure"),
            ("maps", "Share saved map facts"),
            ("attachments", "Share attachment captions and metadata"),
            ("images", "Share map and attachment image previews"),
            ("semantic", "Enable local semantic search"),
        ):
            checkbox = declare_inspection(
                QCheckBox(text, self.scope_choices),
                "mcp.enable|integrations.mcp|help-mcp-enable",
            )
            checkbox.setAccessibleName(text)
            self.scope_boxes[key] = checkbox
            choice_layout.addWidget(checkbox)
        self.prepare_button = WrappingPushButton("Retry semantic preparation")
        self.prepare_button.setToolTip(
            "Use an already-installed local model for this session. No downloads."
        )
        declare_inspection(
            self.prepare_button, "mcp.enable|integrations.mcp|help-mcp-enable"
        )
        self.prepare_button.clicked.connect(self.prepare_requested.emit)
        choice_layout.addWidget(self.prepare_button)
        self.enable_button.clicked.connect(self._enable)
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

    def _enable(self) -> None:
        self.scopes_requested.emit(
            [key for key, box in self.scope_boxes.items() if box.isChecked()]
        )
        self.enable_requested.emit()

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
        if state["state"] == "Off" and self._sharing_was_on:
            for box in self.scope_boxes.values():
                box.setChecked(False)
        self._sharing_was_on = state["state"] != "Off"
        for key, box in self.scope_boxes.items():
            if state["state"] in {"Starting", "Active"}:
                box.setChecked(key in state.get("scopes", []))
            box.setEnabled(state["state"] == "Off")
            box.setToolTip(
                "Applies only to this session"
                if state["state"] == "Off"
                else "Stop sharing before changing content scopes"
            )
        self.scope_boxes["images"].setToolTip(
            "Also requires map facts or attachment metadata sharing"
        )
        self.scope_boxes["semantic"].setToolTip(
            "Automatically prepares the installed local model when sharing starts. "
            "Saved changes refresh it automatically. No downloads."
        )
        retry = (
            state["state"] == "Active"
            and "semantic" in state.get("scopes", [])
            and state.get("semantic_state") == "unavailable"
        )
        self.prepare_button.setVisible(retry)
        self.prepare_button.setEnabled(retry)
        self.prepare_button.setToolTip(
            "Use an already-installed local model. No downloads; Stop sharing cancels preparation."
            if state["state"] == "Active" and "semantic" in state.get("scopes", [])
            else "Enable local semantic search for this session first"
        )
        if "semantic" in state.get("scopes", []):
            self.status.setText(
                self.status.text()
                + "\nSemantic search: "
                + state.get("semantic_state", "unprepared")
            )
        self.activity.setPlainText(json.dumps(state["activity"], indent=2))
