"""Native dialog actions that stack instead of shrinking their complete labels."""

from typing import Any

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import QDialogButtonBox, QSizePolicy

from src.gui.utils.action_label_metrics import intrinsic_action_size


class ResponsiveDialogButtonBox(QDialogButtonBox):
    """Retain native roles/defaults/signals with content-first action-row sizing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Accept native constructors and own a lifecycle-safe reflow timer."""
        super().__init__(*args, **kwargs)
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.timeout.connect(self._reflow)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self._reflow_timer.start(0)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Allow a vertical action group instead of forcing the dialog wider."""
        sizes = [intrinsic_action_size(button) for button in self.buttons()]
        return QSize(
            max((size.width() for size in sizes), default=0),
            max((size.height() for size in sizes), default=0),
        )

    def _reflow(self) -> None:
        sizes = [intrinsic_action_size(button) for button in self.buttons()]
        layout = self.layout()
        spacing = max(0, layout.spacing()) if layout is not None else 0
        required = sum(size.width() for size in sizes) + spacing * max(
            0, len(sizes) - 1
        )
        orientation = (
            Qt.Orientation.Vertical
            if required > self.contentsRect().width()
            else Qt.Orientation.Horizontal
        )
        for button, size in zip(self.buttons(), sizes, strict=True):
            button.setMinimumSize(size)
        if self.orientation() != orientation:
            self.setOrientation(orientation)
        height = (
            sum(size.height() for size in sizes) + spacing * max(0, len(sizes) - 1)
            if orientation == Qt.Orientation.Vertical
            else max((size.height() for size in sizes), default=0)
        )
        self.setMinimumHeight(height)
        self.updateGeometry()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Defer orientation changes until Qt finishes geometry delivery."""
        super().resizeEvent(event)
        self._reflow_timer.start(0)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Measure with the final polished style and font."""
        super().showEvent(event)
        self._reflow_timer.start(0)

    def event(self, event: QEvent) -> bool:
        """Recheck long/localized wording after style and layout changes."""
        result = super().event(event)
        if hasattr(self, "_reflow_timer") and event.type() in (
            QEvent.Type.LayoutRequest,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
        ):
            self._reflow_timer.start(0)
        return result
