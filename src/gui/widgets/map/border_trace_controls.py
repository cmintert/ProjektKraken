"""Controls for copying an existing region border during drawing."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.standard_buttons import StandardButton

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView


class BorderTraceControls(QWidget):
    """Show Trace only in region drawing mode and expose both preview routes."""

    def __init__(self, view: "MapGraphicsView", parent: QWidget) -> None:
        """Build a small control strip for region drawing."""
        super().__init__(parent)
        self._tool = view._drawing_tool
        self._view = view
        layout = QVBoxLayout(self)
        StyleHelper.apply_panel_spacing(layout)
        row = ActionFlowLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.start = StandardButton("Trace border", self)
        self.switch = StandardButton("Switch route", self)
        self.accept = StandardButton("Use border", self)
        self.cancel = StandardButton("Cancel trace", self)
        self.message = QLabel(self)
        self.message.setWordWrap(True)
        for button in (self.start, self.switch, self.accept, self.cancel):
            row.addWidget(button)
        self.restyle()
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(self.message)
        self.start.clicked.connect(self._start)
        self.switch.clicked.connect(self._switch)
        self.accept.clicked.connect(self._tool.accept_trace)
        self.cancel.clicked.connect(self._tool.trace.cancel)
        view.border_trace_changed.connect(self.refresh)
        self.refresh()
        view.border_trace_changed.connect(view._refresh_mode_indicator)

    def _start(self) -> None:
        self._tool.trace.start()
        self._view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _switch(self) -> None:
        self._tool.trace.switch_route(self._tool.draft_points())

    def restyle(self) -> None:
        """Refresh styles and any visible overlay after a theme switch."""
        style = StyleHelper.get_action_role_style("secondary")
        for button in (self.start, self.switch, self.accept, self.cancel):
            button.setStyleSheet(style)
        self._tool.trace.restyle()

    def refresh(self) -> None:
        """Refresh control visibility, status, and confirm availability."""
        trace = self._tool.trace
        self.setVisible(self._tool.drawing_mode == "region" and not self._tool.paused)
        self.start.setVisible(not trace.active)
        self.cancel.setVisible(trace.active)
        self.switch.setVisible(trace.has_routes)
        self.accept.setVisible(trace.has_routes)
        self.accept.setEnabled(trace.can_use)
        self.message.setText(trace.message)
        self.message.setVisible(bool(trace.message))
