"""Presentation state for one saved graph action."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QWidget

from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.standard_buttons import StandardButton


class GraphFeedback(QWidget):
    """Keep a saved or failed outcome visible with its applicable actions."""

    dismissed = Signal()
    inspect_requested = Signal()
    timing_requested = Signal()
    membership_requested = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Build a nonmodal status row that wraps in narrow panels."""
        super().__init__(parent)
        layout = ActionFlowLayout(self)
        self.caption = QLabel()
        self.caption.setTextFormat(Qt.TextFormat.PlainText)
        self.caption.setWordWrap(True)
        self.caption.setAccessibleName("Graph authoring result")
        self.inspect = StandardButton("Inspect")
        self.timing = StandardButton("Inspect Timing")
        self.membership = declare_inspection(
            StandardButton("Add to Tag Scope"),
            "graph-add-to-adventure|graph.exploring|help-inspect-graph-add-to-adventure",
        )
        self.dismiss = StandardButton("Dismiss")
        for widget in (
            self.caption,
            self.inspect,
            self.timing,
            self.membership,
            self.dismiss,
        ):
            layout.addWidget(widget)
        self.inspect.clicked.connect(self.inspect_requested)
        self.timing.clicked.connect(self.timing_requested)
        self.membership.clicked.connect(self.membership_requested)
        self.dismiss.clicked.connect(self.dismissed)
        connect_theme(self, self._apply_style)
        self._apply_style()
        self.hide()

    def _apply_style(self, *_args: object) -> None:
        self.caption.setStyleSheet(StyleHelper.get_supporting_caption_style())

    def present(
        self,
        message: str,
        *,
        inspect: bool = False,
        timing: bool = False,
        membership: bool = False,
    ) -> None:
        """Present the outcome and only its usable actions."""
        self.caption.setText(message)
        self.inspect.setVisible(inspect)
        self.timing.setVisible(timing)
        self.membership.setVisible(membership)
        self.show()
