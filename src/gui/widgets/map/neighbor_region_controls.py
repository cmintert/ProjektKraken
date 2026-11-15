"""Presentation and local-step intents for neighboring-region drawing."""

from typing import Literal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.wrapping_buttons import WrappingPushButton

NeighborStage = Literal["closed", "drawing", "preview", "accepted", "pending"]


class NeighborRegionControls(QFrame):
    """Render coordinator-owned state without computing or saving geometry."""

    preview_requested = Signal()
    accept_requested = Signal()
    back_requested = Signal()
    save_requested = Signal()
    cancel_requested = Signal()
    changed = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Create persistent, keyboard-accessible actions in a wrapping row."""
        super().__init__(parent)
        self.setObjectName("TemporalSnapshotBanner")
        self.stage: NeighborStage = "closed"
        self.ready = False
        layout = QVBoxLayout(self)
        StyleHelper.apply_panel_spacing(layout)
        self.context = QLabel(self)
        self.context.setObjectName("TemporalSnapshotLabel")
        self.context.setWordWrap(True)
        layout.addWidget(self.context)
        self.message = QLabel(self)
        self.message.setObjectName("TemporalSnapshotLabel")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        row = ActionFlowLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.preview = self._button("Preview new region", row)
        self.use = self._button("Use result", row)
        self.back = self._button("Back to drawing", row)
        self.save = self._button("Confirm", row)
        self.cancel = self._button("Cancel neighbor", row)
        layout.addLayout(row)
        self.preview.clicked.connect(self.preview_requested)
        self.use.clicked.connect(self.accept_requested)
        self.back.clicked.connect(self.back_requested)
        self.save.clicked.connect(self.save_requested)
        self.cancel.clicked.connect(self.cancel_requested)
        connect_theme(self, self.restyle)
        self.restyle()
        self.present("closed", "", "")

    def _button(self, text: str, row: ActionFlowLayout) -> WrappingPushButton:
        button = declare_inspection(
            WrappingPushButton(text, self),
            "neighbor-region-step|map.features|help-inspect-neighbor-region",
        )
        row.addWidget(button)
        return button

    @property
    def active(self) -> bool:
        """Whether this strip owns a map drawing session."""
        return self.stage != "closed"

    def present(
        self, stage: NeighborStage, context: str, message: str, *, ready: bool = False
    ) -> None:
        """Render a supplied stage, leaving draft ownership in the coordinator."""
        self.stage, self.ready = stage, ready
        self.context.setText(context)
        self.message.setText(message)
        self.preview.setVisible(stage == "drawing")
        self.use.setVisible(stage == "preview")
        self.use.setEnabled(ready)
        self.use.setToolTip("" if ready else message)
        self.back.setVisible(stage in {"preview", "accepted"})
        self.save.setVisible(stage == "accepted")
        self.cancel.setEnabled(stage != "pending")
        self.setVisible(self.active)
        self.changed.emit()

    def confirm_step(self) -> None:
        """Dispatch Enter to the current local operation."""
        if self.stage == "drawing":
            self.preview_requested.emit()
        elif self.stage == "preview" and self.ready:
            self.accept_requested.emit()
        elif self.stage == "accepted":
            self.save_requested.emit()

    def restyle(self, _theme: dict | None = None) -> None:
        """Refresh shared action and mode roles without replacing controls."""
        self.setStyleSheet(StyleHelper.get_temporal_snapshot_banner_style())
        for button in (self.preview, self.use, self.back, self.save, self.cancel):
            button.setStyleSheet(StyleHelper.get_action_role_style("secondary"))
