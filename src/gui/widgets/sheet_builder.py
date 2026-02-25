"""Sheet Builder Widget Module.

Provides a visual "Stat Block" builder for entity/event attributes. The sheet
presents attributes as draggable key-value boxes arranged in a flex-row grid,
and supports serialization of the spatial layout to a 2D list for persistence.
"""

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import shiboken6
from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCursor,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager

logger = logging.getLogger(__name__)

# Internal MIME type for drag-and-drop within the sheet builder
_SHEET_DRAG_MIME = "application/x-kraken-sheet-key"


@dataclass
class _FocusState:
    """Snapshot of focus/scroll state for preservation across reloads.

    Attributes:
        focused_key: The attribute key that had focus, or None.
        focused_text_block_index: Index of the focused TextBlockWidget, or -1.
        cursor_position: Cursor position within the focused line-edit.
        scroll_value: Vertical scroll bar value.
        had_focus: Whether any widget inside the sheet had focus.
    """

    focused_key: Optional[str] = None
    focused_text_block_index: int = -1
    cursor_position: int = 0
    scroll_value: int = 0
    had_focus: bool = False


class AttributePairWidget(QFrame):
    """A single key-value attribute box for the Sheet Builder.

    Displays a bold key label on top and an editable value line-edit below,
    with an optional type toggle (String / Number / Boolean).

    Signals:
        value_changed: Emitted when the value or type is modified.
        drag_started: Emitted with the attribute key when the user initiates a drag.
    """

    value_changed = Signal()
    drag_started = Signal(str)
    drag_finished = Signal()

    def __init__(
        self,
        key: str,
        value: str = "",
        value_type: str = "String",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the AttributePairWidget.

        Args:
            key: The attribute key displayed as a bold label.
            value: The initial string value.
            value_type: One of "String", "Number", "Boolean".
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._key = key
        self.weight = 1  # Default stretch factor
        self._drag_start_pos: Optional[QPoint] = None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("AttributePairWidget")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Bold key label
        self.key_label = QLabel(f"<b>{key}:</b>")
        self.key_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.key_label)

        # Value line-edit
        self.value_edit = QLineEdit(value)
        self.value_edit.setPlaceholderText("Value…")
        self.value_edit.textChanged.connect(self._on_value_changed)
        layout.addWidget(self.value_edit)

        # Type toggle (compact combo) - Hidden by default
        self.type_combo = QComboBox()
        self.type_combo.addItems(["String", "Number", "Boolean"])
        self.type_combo.setCurrentText(value_type)
        self.type_combo.currentTextChanged.connect(self._on_value_changed)
        self.type_combo.setMaximumWidth(90)
        self.type_combo.setVisible(False)
        layout.addWidget(self.type_combo)

        # Ensure value edit expands
        self.value_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        # Apply initial theme and connect to changes
        self._theme_mgr = ThemeManager()
        self._apply_theme()
        self._theme_mgr.theme_changed.connect(self._apply_theme)
        self.destroyed.connect(self._on_destroyed)

    def _apply_theme(self) -> None:
        """Apply current theme colors to the widget."""
        theme = self._theme_mgr.get_theme()
        surface_alt = theme.get("surface_alt", "#2A2A2A")
        border = theme.get("border", "#333333")
        text = theme.get("text", "#E0E0E0")

        self.setStyleSheet(
            f"""
            AttributePairWidget {{
                background-color: {surface_alt};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            QLabel {{
                color: {text};
            }}
            QLineEdit, QComboBox {{
                background-color: transparent;
                border: 1px solid {border};
                border-radius: 2px;
                color: {text};
                padding: 2px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {theme.get('primary', '#5C82FF')};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
        """
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def key(self) -> str:
        """Return the attribute key."""
        return self._key

    def get_value(self) -> str:
        """Return the raw string value."""
        return self.value_edit.text()

    def set_value(self, value: str) -> None:
        """Set the value without emitting value_changed."""
        self.value_edit.blockSignals(True)
        self.value_edit.setText(value)
        self.value_edit.blockSignals(False)

    def get_type(self) -> str:
        """Return the selected type string."""
        return self.type_combo.currentText()

    def set_type(self, value_type: str) -> None:
        """Set the type combo without emitting value_changed."""
        self.type_combo.blockSignals(True)
        self.type_combo.setCurrentText(value_type)
        self.type_combo.blockSignals(False)

    def get_parsed_value(self) -> Union[str, int, float, bool]:
        """Return the value parsed according to the selected type."""
        raw = self.value_edit.text()
        vtype = self.type_combo.currentText()
        if vtype == "Number":
            try:
                return float(raw) if "." in raw else int(raw)
            except ValueError:
                return 0
        if vtype == "Boolean":
            return raw.lower() in {"true", "1", "yes", "on"}
        return raw

    # ------------------------------------------------------------------
    # Drag support
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Record the drag start position on left-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Initiate a drag if the mouse moves far enough from the press point."""
        if (
            self._drag_start_pos is not None
            and (event.pos() - self._drag_start_pos).manhattanLength() > 10
        ):
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(_SHEET_DRAG_MIME, self._key.encode("utf-8"))
            drag.setMimeData(mime)
            self.drag_started.emit(self._key)
            drag.exec(Qt.DropAction.MoveAction)
            self._drag_start_pos = None
            self.drag_finished.emit()
        super().mouseMoveEvent(event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_value_changed(self) -> None:
        """Emit value_changed signal."""
        self.value_changed.emit()

    def _on_destroyed(self) -> None:
        """Disconnect theme signal when destroyed."""
        try:
            self._theme_mgr.theme_changed.disconnect(self._apply_theme)
        except (RuntimeError, TypeError):
            pass


class TextBlockWidget(QFrame):
    """A full-width editable text block for flavour text in the sheet.

    Signals:
        text_changed: Emitted when the text content is modified.
    """

    text_changed = Signal()

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the TextBlockWidget.

        Args:
            text: Initial text content.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.weight = 1

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName("TextBlockWidget")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        self.text_edit = QLineEdit(text)
        self.text_edit.setPlaceholderText("Enter flavour text…")
        self.text_edit.textChanged.connect(lambda: self.text_changed.emit())
        self.text_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.text_edit)

        self._theme_mgr = ThemeManager()
        self._apply_theme()
        self._theme_mgr.theme_changed.connect(self._apply_theme)
        self.destroyed.connect(self._on_text_destroyed)

    def get_text(self) -> str:
        """Return the current text."""
        return self.text_edit.text()

    def set_text(self, text: str) -> None:
        """Set text without emitting."""
        self.text_edit.blockSignals(True)
        self.text_edit.setText(text)
        self.text_edit.blockSignals(False)

    def _apply_theme(self) -> None:
        """Apply current theme colors."""
        theme = self._theme_mgr.get_theme()
        text_dim = theme.get("text_dim", "#808080")
        text = theme.get("text", "#E0E0E0")
        self.setStyleSheet(
            f"""
            TextBlockWidget QLineEdit {{
                background-color: transparent;
                border: none;
                color: {text_dim};
                font-style: italic;
                padding: 4px;
            }}
            TextBlockWidget QLineEdit:focus {{
                color: {text};
            }}
        """
        )

    def _on_text_destroyed(self) -> None:
        """Disconnect theme signal when destroyed."""
        try:
            self._theme_mgr.theme_changed.disconnect(self._apply_theme)
        except (RuntimeError, TypeError):
            pass


class DividerWidget(QFrame):
    """A horizontal divider / separator line for the sheet."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the DividerWidget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.weight = 1
        self.setObjectName("DividerWidget")
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(2)

        self._theme_mgr = ThemeManager()
        self._apply_theme()
        self._theme_mgr.theme_changed.connect(self._apply_theme)
        self.destroyed.connect(self._on_divider_destroyed)

    def _apply_theme(self) -> None:
        """Apply current theme colors."""
        theme = self._theme_mgr.get_theme()
        border = theme.get("border", "#333333")
        self.setStyleSheet(
            f"DividerWidget {{ color: {border}; background-color: {border}; }}"
        )

    def _on_divider_destroyed(self) -> None:
        """Disconnect theme signal when destroyed."""
        try:
            self._theme_mgr.theme_changed.disconnect(self._apply_theme)
        except (RuntimeError, TypeError):
            pass


class SpacerWidget(QFrame):
    """A visual spacer widget to represent empty flexible space."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the SpacerWidget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.weight = 1
        self.setObjectName("SpacerWidget")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(20)

        self._theme_mgr = ThemeManager()
        self._apply_theme()
        self._theme_mgr.theme_changed.connect(self._apply_theme)
        self.destroyed.connect(self._on_spacer_destroyed)

    def _apply_theme(self) -> None:
        """Apply current theme colors."""
        theme = self._theme_mgr.get_theme()
        border = theme.get("border", "#333333")
        # Faint dashed border to give it a placeholder look
        self.setStyleSheet(
            f"""
            SpacerWidget {{
                background-color: transparent;
                border: 1px dashed {border};
                border-radius: 4px;
            }}
        """
        )

    def _on_spacer_destroyed(self) -> None:
        """Disconnect theme signal when destroyed."""
        try:
            self._theme_mgr.theme_changed.disconnect(self._apply_theme)
        except (RuntimeError, TypeError):
            pass


class _GhostWidget(QWidget):
    """Semi-transparent drag preview that follows the cursor during DnD.

    Displays the attribute key in a styled label to give WYSIWYG feedback
    about which attribute is being moved.
    """

    def __init__(self, key: str, parent: Optional[QWidget] = None) -> None:
        """Initialize the ghost widget.

        Args:
            key: The attribute key to display.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.7)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._label = QLabel(key)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._theme_mgr = ThemeManager()
        self._apply_theme()
        self.adjustSize()

    def _apply_theme(self) -> None:
        """Apply current theme colors."""
        theme = self._theme_mgr.get_theme()
        primary = theme.get("primary", "#5C82FF")
        text = theme.get("text", "#E0E0E0")
        self._label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {primary};
                color: {text};
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
            }}
        """
        )

    def move_to(self, global_pos: QPoint) -> None:
        """Position the ghost near the given global cursor position.

        Args:
            global_pos: The global cursor position.
        """
        self.move(global_pos.x() + 10, global_pos.y() + 10)


class _InsertionLine(QFrame):
    """A thin colored line indicating where a dragged item will land.

    Shown between rows or between items within a row during drag-move.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the insertion line.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(3)
        self.hide()

        self._theme_mgr = ThemeManager()
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply current theme colors."""
        theme = self._theme_mgr.get_theme()
        primary = theme.get("primary", "#5C82FF")
        self.setStyleSheet(
            f"""
            _InsertionLine {{
                background-color: {primary};
                border: none;
                border-radius: 1px;
            }}
        """
        )


class _ResizeHandle(QWidget):
    """Invisible drag handle between adjacent items in a row.

    Allows mouse-drag to redistribute stretch weights between the item
    to the left and the item to the right.
    """

    resize_done = Signal()

    def __init__(
        self,
        hlayout: QHBoxLayout,
        left_idx: int,
        right_idx: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the resize handle.

        Args:
            hlayout: The row layout containing the items.
            left_idx: Index of the left item.
            right_idx: Index of the right item.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._hlayout = hlayout
        self._left_idx = left_idx
        self._right_idx = right_idx
        self._dragging = False
        self._drag_start_x = 0
        self._weight_overlay: Optional[QLabel] = None

        self.setFixedWidth(6)
        self.setCursor(QCursor(Qt.CursorShape.SplitHCursor))
        self.setToolTip("Drag to resize")

        self._theme_mgr = ThemeManager()
        self._apply_theme()
        self._theme_mgr.theme_changed.connect(self._apply_theme)
        self.destroyed.connect(self._on_destroyed)

    def _apply_theme(self) -> None:
        """Apply current theme colors."""
        theme = self._theme_mgr.get_theme()
        border = theme.get("border", "#333333")
        self.setStyleSheet(
            f"""
            _ResizeHandle {{
                background-color: transparent;
            }}
            _ResizeHandle:hover {{
                background-color: {border};
                border-radius: 2px;
            }}
        """
        )

    def _on_destroyed(self) -> None:
        """Disconnect theme signal when destroyed."""
        try:
            self._theme_mgr.theme_changed.disconnect(self._apply_theme)
        except (RuntimeError, TypeError):
            pass

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Begin resize tracking."""
        if not shiboken6.isValid(self._hlayout):
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_x = event.globalPosition().toPoint().x()

            try:
                # Record initial state with high granularity multiplier
                multiplier = 100
                self._initial_left_stretch = (
                    max(1, self._hlayout.stretch(self._left_idx)) * multiplier
                )
                self._initial_right_stretch = (
                    max(1, self._hlayout.stretch(self._right_idx)) * multiplier
                )

                left_widget = self._hlayout.itemAt(self._left_idx).widget()
                right_widget = self._hlayout.itemAt(self._right_idx).widget()

                # Fallback to 100px for headless unit tests where width() == 0
                self._initial_left_width = (
                    left_widget.width()
                    if left_widget and left_widget.width() > 0
                    else 100
                )
                self._initial_right_width = (
                    right_widget.width()
                    if right_widget and right_widget.width() > 0
                    else 100
                )
            except RuntimeError:
                self._dragging = False
                return

            # Show weight overlay
            self._show_weight_overlay()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Adjust weights proportionally during drag."""
        if not self._dragging:
            return

        if not shiboken6.isValid(self._hlayout):
            self._dragging = False
            return

        try:
            # Abort if layout has been structurally changed (e.g. by autosave reload)
            if (
                self._left_idx >= self._hlayout.count()
                or self._right_idx >= self._hlayout.count()
            ):
                self._dragging = False
                return
        except RuntimeError:
            self._dragging = False
            return

        dx = event.globalPosition().toPoint().x() - self._drag_start_x

        total_width = self._initial_left_width + self._initial_right_width
        if total_width <= 0:
            return

        total_stretch = self._initial_left_stretch + self._initial_right_stretch

        # Calculate new proportional width for the widgets
        new_left_width = self._initial_left_width + dx

        # Enforce minimums to prevent collapsing
        new_left_width = max(10, min(new_left_width, total_width - 10))

        # Calculate new stretch values based on the ratio of new widths to total width
        left_stretch = int((new_left_width / total_width) * total_stretch + 0.5)

        # Ensure minimum stretch of 1 (this allows for large granularity like 190:10)
        left_stretch = max(1, left_stretch)
        right_stretch = max(1, total_stretch - left_stretch)

        try:
            current_left_stretch = self._hlayout.stretch(self._left_idx)
            current_right_stretch = self._hlayout.stretch(self._right_idx)

            if (
                left_stretch != current_left_stretch
                or right_stretch != current_right_stretch
            ):
                self._hlayout.setStretch(self._left_idx, left_stretch)
                self._hlayout.setStretch(self._right_idx, right_stretch)
                self._update_weight_overlay()
        except RuntimeError:
            self._dragging = False
            return

        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """End resize tracking and emit completion."""
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._hide_weight_overlay()

            if not shiboken6.isValid(self._hlayout):
                return

            try:
                # Update final weight on the widgets and trigger save
                if (
                    self._left_idx >= self._hlayout.count()
                    or self._right_idx >= self._hlayout.count()
                ):
                    return

                left_stretch = self._hlayout.stretch(self._left_idx)
                right_stretch = self._hlayout.stretch(self._right_idx)

                # Normalize to clean numbers (max scale of 20) for saved JSON output
                total = left_stretch + right_stretch
                if total > 0:
                    left_pct = left_stretch / total
                    norm_left = int(left_pct * 20 + 0.5)
                    norm_left = max(1, min(norm_left, 19))
                    norm_right = 20 - norm_left

                    gcd = math.gcd(norm_left, norm_right)
                    final_left = norm_left // gcd
                    final_right = norm_right // gcd

                    self._hlayout.setStretch(self._left_idx, final_left)
                    self._hlayout.setStretch(self._right_idx, final_right)

                left_item = self._hlayout.itemAt(self._left_idx)
                right_item = self._hlayout.itemAt(self._right_idx)

                # Use final_left/final_right (normalized), not pre-normalization values
                if (
                    left_item
                    and left_item.widget()
                    and hasattr(left_item.widget(), "weight")
                ):
                    left_item.widget().weight = final_left
                if (
                    right_item
                    and right_item.widget()
                    and hasattr(right_item.widget(), "weight")
                ):
                    right_item.widget().weight = final_right
            except RuntimeError:
                return

            # Only emit the signal when the user stops dragging
            self.resize_done.emit()
            event.accept()

    # ------------------------------------------------------------------
    # Weight overlay helpers
    # ------------------------------------------------------------------

    def _show_weight_overlay(self) -> None:
        """Create and show the weight percentage overlay above the handle."""
        if self._weight_overlay is None:
            self._weight_overlay = QLabel(self.parentWidget() or self)
            self._weight_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            theme = self._theme_mgr.get_theme()
            primary = theme.get("primary", "#5C82FF")
            self._weight_overlay.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {primary};
                    color: white;
                    border-radius: 3px;
                    padding: 2px 6px;
                    font-size: 10px;
                    font-weight: bold;
                }}
            """
            )
        self._update_weight_overlay()
        self._weight_overlay.show()
        self._weight_overlay.raise_()

    def _update_weight_overlay(self) -> None:
        """Update the overlay text and position to reflect current stretches."""
        if self._weight_overlay is None:
            return

        try:
            left_s = max(1, self._hlayout.stretch(self._left_idx))
            right_s = max(1, self._hlayout.stretch(self._right_idx))
        except RuntimeError:
            return

        total = left_s + right_s
        left_pct = round(left_s / total * 100)
        right_pct = 100 - left_pct
        self._weight_overlay.setText(f"{left_pct}% | {right_pct}%")
        self._weight_overlay.adjustSize()

        # Position the overlay above the handle
        handle_pos = self.mapToParent(self.rect().center())
        overlay_w = self._weight_overlay.width()
        overlay_h = self._weight_overlay.height()
        self._weight_overlay.move(
            handle_pos.x() - overlay_w // 2,
            handle_pos.y() - overlay_h - 4,
        )

    def _hide_weight_overlay(self) -> None:
        """Hide and clean up the weight overlay."""
        if self._weight_overlay is not None:
            self._weight_overlay.hide()
            self._weight_overlay.deleteLater()
            self._weight_overlay = None


class SheetBuilderWidget(QWidget):
    """Visual grid builder for entity/event "stat blocks".

    Arranges ``AttributePairWidget`` instances in a flex-row grid
    (QVBoxLayout of QHBoxLayout rows). The layout is serialised as a 2D
    list of key strings and stored in the ``_sheet_layout`` metadata field.

    Signals:
        attributes_changed: Emitted when any attribute value or the layout
            structure changes.
    """

    attributes_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the SheetBuilderWidget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setAcceptDrops(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────────────────
        self._toolbar = QToolBar()
        self._toolbar.setIconSize(QSize(16, 16))
        self._toolbar.setMovable(False)
        self._toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        self._act_add_row = QAction("＋ Attribute", self)
        self._act_add_row.setToolTip("Add a new attribute row")
        self._act_add_row.triggered.connect(self._on_toolbar_add_attribute)
        self._toolbar.addAction(self._act_add_row)

        self._act_add_spacer = QAction("⬜ Spacer", self)
        self._act_add_spacer.setToolTip("Add a spacer to the last row")
        self._act_add_spacer.triggered.connect(self._on_toolbar_add_spacer)
        self._toolbar.addAction(self._act_add_spacer)

        self._act_add_divider = QAction("── Divider", self)
        self._act_add_divider.setToolTip("Add a horizontal divider row")
        self._act_add_divider.triggered.connect(self._on_toolbar_add_divider)
        self._toolbar.addAction(self._act_add_divider)

        self._act_add_text = QAction("𝐓 Text", self)
        self._act_add_text.setToolTip("Add a flavour text row")
        self._act_add_text.triggered.connect(self._on_toolbar_add_text)
        self._toolbar.addAction(self._act_add_text)

        outer.addWidget(self._toolbar)

        # ── Scroll area ─────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self._scroll)

        # Inner container
        self._container = QWidget()
        self._container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._container.customContextMenuRequested.connect(self._show_context_menu)
        self._grid_layout = QVBoxLayout(self._container)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._grid_layout.setSpacing(4)
        self._grid_layout.setContentsMargins(4, 4, 4, 4)
        self._scroll.setWidget(self._container)

        # Pair widget lookup: key -> AttributePairWidget
        self._pairs: Dict[str, AttributePairWidget] = {}

        # WYSIWYG drag-and-drop feedback widgets
        self._ghost: Optional[_GhostWidget] = None
        self._insertion_line: _InsertionLine = _InsertionLine(self._container)

        # Reentrance-safe signal suppression counter (> 0 means suppressed)
        self._block_depth: int = 0

        # Drag safety: defer destructive reloads while a QDrag.exec() is active
        self._drag_active: bool = False
        self._deferred_reload: Optional[tuple] = None

        # Apply initial theme and connect to changes
        self._theme_mgr = ThemeManager()
        self._apply_theme()
        self._theme_mgr.theme_changed.connect(self._apply_theme)
        self.destroyed.connect(self._on_builder_destroyed)
        logger.debug("SheetBuilderWidget initialized.")

    def _apply_theme(self) -> None:
        """Apply current theme colors to the widget."""
        theme = self._theme_mgr.get_theme()
        surface = theme.get("surface", "#1A1A1A")
        surface_alt = theme.get("surface_alt", "#2A2A2A")
        border = theme.get("border", "#333333")
        text = theme.get("text", "#E0E0E0")
        text_dim = theme.get("text_dim", "#808080")
        primary = theme.get("primary", "#5C82FF")

        # Style the scroll area and container to match the app's surface
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {surface}; border: none; }}"
        )
        self._container.setStyleSheet(f"QWidget {{ background-color: {surface}; }}")

        # Style the toolbar
        self._toolbar.setStyleSheet(
            f"""
            QToolBar {{
                background-color: {surface_alt};
                border-bottom: 1px solid {border};
                spacing: 2px;
                padding: 2px;
            }}
            QToolButton {{
                color: {text_dim};
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 11px;
            }}
            QToolButton:hover {{
                color: {text};
                background-color: {border};
                border: 1px solid {border};
            }}
            QToolButton:pressed {{
                background-color: {primary};
                color: white;
            }}
        """
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _defer_if_dragging(
        self,
        attributes: Dict[str, Any],
        layout: Optional[List[List[Any]]] = None,
    ) -> bool:
        """Store the reload args if a child drag is active.

        Returns:
            True if the reload was deferred, False otherwise.
        """
        if self._drag_active:
            logger.debug("Deferring load_attributes – drag is active.")
            self._deferred_reload = (attributes, layout)
            return True
        return False

    def load_attributes(  # noqa: C901
        self,
        attributes: Dict[str, Any],
        layout: Optional[List[List[Any]]] = None,
    ) -> None:
        """Populate the sheet from an attributes dict and optional layout.

        Focus, cursor position, and scroll position are preserved across
        reloads so that auto-save does not disrupt the user's editing flow.

        Args:
            attributes: Key-value attribute pairs (user-visible, no ``_`` prefix).
            layout: Optional 2D list describing the row arrangement. Items can be
                string keys, dicts like ``{"key": "str", "weight": 2}``,
                ``{"type": "spacer", "weight": 1}``,
                ``{"type": "text", "text": "…"}``, or
                ``{"type": "divider"}``.
                If ``None``, each attribute gets its own row.
        """
        logger.debug(
            f"Loading {len(attributes)} attributes with layout={layout is not None}"
        )

        # Defer reload if a child drag is active to avoid destroying the
        # widget that owns the running QDrag (causes C++ access violation).
        if self._defer_if_dragging(attributes, layout):
            return

        # Save focus/scroll state before clearing
        focus_state = self._save_focus_state()

        self._block_depth += 1
        try:
            self._clear()

            if layout is not None:
                # Build rows according to layout, skipping keys not in attributes
                placed_keys: set[str] = set()
                for row_items in layout:
                    row_configs = []
                    for item in row_items:
                        if isinstance(item, str):
                            if item in attributes:
                                row_configs.append(
                                    {
                                        "key": item,
                                        "value": attributes[item],
                                        "weight": 1,
                                    }
                                )
                                placed_keys.add(item)
                            else:
                                logger.debug(
                                    f"Key '{item}' in layout but not in attributes."
                                )
                        elif isinstance(item, dict):
                            item_type = item.get("type", "")
                            is_spacer = (
                                item_type == "spacer" or item.get("spacer") is True
                            )
                            weight = int(item.get("weight", 1))
                            if item_type == "text":
                                row_configs.append(
                                    {"type": "text", "text": item.get("text", "")}
                                )
                            elif item_type == "divider":
                                row_configs.append({"type": "divider"})
                            elif is_spacer:
                                row_configs.append({"spacer": True, "weight": weight})
                            else:
                                key = item.get("key")
                                if key and key in attributes:
                                    row_configs.append(
                                        {
                                            "key": key,
                                            "value": attributes[key],
                                            "weight": weight,
                                        }
                                    )
                                    placed_keys.add(key)
                    if row_configs:
                        self._add_row(row_configs)

                # Append any remaining attributes not referenced by the layout
                for key, value in attributes.items():
                    if key not in placed_keys:
                        self._add_row([{"key": key, "value": value, "weight": 1}])
            else:
                # No layout – one attribute per row
                for key, value in attributes.items():
                    self._add_row([{"key": key, "value": value, "weight": 1}])
        finally:
            self._block_depth -= 1

        # Restore focus/scroll state after rebuild
        self._restore_focus_state(focus_state)
        logger.debug("Attributes loaded successfully.")

    def get_attributes(self) -> Dict[str, Any]:
        """Return the current attribute values as a dict.

        Returns:
            Dict mapping attribute keys to their parsed values.
        """
        return {key: pair.get_parsed_value() for key, pair in self._pairs.items()}

    def get_layout(self) -> List[List[Any]]:
        """Serialize the current row arrangement as a 2D list.

        Returns:
            List of rows, where each row is a list of attribute key strings,
            or dicts describing items with custom weights, spacers, text, or dividers.
        """
        rows: List[List[Any]] = []
        for row_idx in range(self._grid_layout.count()):
            row_layout = self._grid_layout.itemAt(row_idx)
            if row_layout is None or row_layout.layout() is None:
                continue
            hlayout = row_layout.layout()
            row_items: List[Any] = []
            for col_idx in range(hlayout.count()):
                item = hlayout.itemAt(col_idx)
                if item is None:
                    continue
                widget = item.widget()
                if isinstance(widget, AttributePairWidget):
                    # Explicit > 0 check: stretch() returns 0 for unset, not None
                    raw = hlayout.stretch(col_idx)
                    stretch = raw if raw > 0 else widget.weight
                    if stretch == 1:
                        row_items.append(widget.key)
                    else:
                        row_items.append({"key": widget.key, "weight": stretch})
                elif isinstance(widget, TextBlockWidget):
                    row_items.append({"type": "text", "text": widget.get_text()})
                elif isinstance(widget, DividerWidget):
                    row_items.append({"type": "divider"})
                elif isinstance(widget, SpacerWidget):
                    raw = hlayout.stretch(col_idx)
                    stretch = raw if raw > 0 else widget.weight
                    row_items.append({"type": "spacer", "weight": stretch})
                elif isinstance(widget, _ResizeHandle):
                    continue  # Skip resize handles in serialization
            if row_items:
                rows.append(row_items)
        return rows

    def add_attribute(self, key: str, value: Any = "") -> None:
        """Create a new attribute with Universal String default and add it as a new row.

        Args:
            key: The attribute key.
            value: Initial value (defaults to empty string).
        """
        if key in self._pairs:
            return
        self._add_row([{"key": key, "value": value, "weight": 1}])
        if self._block_depth == 0:
            self.attributes_changed.emit()

    def update_attribute_value(self, key: str, value: Any) -> None:
        """Update the value of an existing attribute in the sheet.

        Args:
            key (str): The attribute key to update.
            value (Any): The new value.
        """
        if key in self._pairs:
            self._block_depth += 1
            try:
                pair = self._pairs[key]
                str_val = str(value) if value is not None else ""
                pair.set_value(str_val)
            finally:
                self._block_depth -= 1

    def remove_attribute(self, key: str) -> None:
        """Remove an attribute from the sheet.

        Args:
            key: The attribute key to remove.
        """
        pair = self._pairs.pop(key, None)
        if pair is None:
            return
        # Find the row layout containing this pair and remove it
        for row_idx in range(self._grid_layout.count()):
            row_item = self._grid_layout.itemAt(row_idx)
            if row_item is None or row_item.layout() is None:
                continue
            hlayout = row_item.layout()
            for col_idx in range(hlayout.count()):
                item = hlayout.itemAt(col_idx)
                if item is not None and item.widget() is pair:
                    hlayout.removeWidget(pair)
                    pair.setParent(None)
                    pair.deleteLater()
                    # Remove stale adjacent _ResizeHandles whose indices are now invalid
                    self._strip_resize_handles(hlayout)
                    # If the row is now empty, remove it
                    if hlayout.count() == 0:
                        self._grid_layout.removeItem(row_item)
                        hlayout.setParent(None)
                        hlayout.deleteLater()
                    else:
                        # Re-inject handles at correct positions
                        self._rebuild_resize_handles(hlayout)
                    if self._block_depth == 0:
                        self.attributes_changed.emit()
                    return

    # ------------------------------------------------------------------
    # Drag-and-drop (Phase 3: Snap Engine)
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drags carrying the sheet MIME type and show ghost preview."""
        if event.mimeData().hasFormat(_SHEET_DRAG_MIME):
            event.acceptProposedAction()
            # Create ghost widget showing the dragged attribute key
            key = bytes(event.mimeData().data(_SHEET_DRAG_MIME)).decode("utf-8")
            self._ghost = _GhostWidget(key)
            self._ghost.show()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Show insertion line and move ghost during drag."""
        if not event.mimeData().hasFormat(_SHEET_DRAG_MIME):
            event.ignore()
            return

        event.acceptProposedAction()

        # Move ghost to follow cursor
        if self._ghost is not None:
            self._ghost.move_to(QCursor.pos())

        # Calculate drop position and show insertion line
        drop_row, insert_col = self._calc_drop_position(event.position().toPoint())
        self._show_insertion_indicator(drop_row, insert_col)

    def dragLeaveEvent(self, event: Any) -> None:
        """Hide ghost and insertion line when drag leaves the widget."""
        self._cleanup_drag_feedback()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle attribute pill drop – move the attribute into the target row."""
        # Clean up drag feedback
        self._cleanup_drag_feedback()

        mime = event.mimeData()
        if not mime.hasFormat(_SHEET_DRAG_MIME):
            event.ignore()
            return

        key = bytes(mime.data(_SHEET_DRAG_MIME)).decode("utf-8")
        pair = self._pairs.get(key)
        if pair is None:
            event.ignore()
            return

        # Remove from current row
        self._detach_pair(pair)

        # Calculate target position
        drop_row, insert_col = self._calc_drop_position(event.position().toPoint())

        if drop_row < self._grid_layout.count():
            # Insert into existing row
            row_item = self._grid_layout.itemAt(drop_row)
            if row_item and row_item.layout():
                hlayout = row_item.layout()
                idx = min(insert_col, hlayout.count())
                hlayout.insertWidget(idx, pair, stretch=pair.weight)
            else:
                self._append_new_row(pair)
        else:
            # Append new row
            self._append_new_row(pair)

        event.acceptProposedAction()
        if self._block_depth == 0:
            self.attributes_changed.emit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_focus_state(self) -> _FocusState:
        """Capture the current focus, cursor, and scroll state.

        Returns:
            A ``_FocusState`` snapshot that can later be passed to
            :meth:`_restore_focus_state`.
        """
        from PySide6.QtWidgets import QApplication

        state = _FocusState()
        state.scroll_value = self._scroll.verticalScrollBar().value()

        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return state

        # Check if focus is inside one of our AttributePairWidgets
        for key, pair in self._pairs.items():
            if pair.value_edit is focus_widget:
                state.had_focus = True
                state.focused_key = key
                state.cursor_position = pair.value_edit.cursorPosition()
                return state

        # Check if focus is inside a TextBlockWidget
        text_block_idx = 0
        for row_idx in range(self._grid_layout.count()):
            row_item = self._grid_layout.itemAt(row_idx)
            if row_item is None or row_item.layout() is None:
                continue
            hlayout = row_item.layout()
            for col_idx in range(hlayout.count()):
                item = hlayout.itemAt(col_idx)
                if item is None:
                    continue
                widget = item.widget()
                if isinstance(widget, TextBlockWidget):
                    if widget.text_edit is focus_widget:
                        state.had_focus = True
                        state.focused_text_block_index = text_block_idx
                        state.cursor_position = widget.text_edit.cursorPosition()
                        return state
                    text_block_idx += 1

        return state

    def _restore_focus_state(self, state: _FocusState) -> None:
        """Restore focus, cursor position, and scroll position from a snapshot.

        Args:
            state: The ``_FocusState`` to restore.
        """
        # Restore scroll position
        self._scroll.verticalScrollBar().setValue(state.scroll_value)

        if not state.had_focus:
            return

        # Restore focus to an AttributePairWidget
        if state.focused_key is not None and state.focused_key in self._pairs:
            pair = self._pairs[state.focused_key]
            pair.value_edit.setFocus()
            cursor_pos = min(state.cursor_position, len(pair.value_edit.text()))
            pair.value_edit.setCursorPosition(cursor_pos)
            return

        # Restore focus to a TextBlockWidget by index
        if state.focused_text_block_index >= 0:
            text_block_idx = 0
            for row_idx in range(self._grid_layout.count()):
                row_item = self._grid_layout.itemAt(row_idx)
                if row_item is None or row_item.layout() is None:
                    continue
                hlayout = row_item.layout()
                for col_idx in range(hlayout.count()):
                    item = hlayout.itemAt(col_idx)
                    if item is None:
                        continue
                    widget = item.widget()
                    if isinstance(widget, TextBlockWidget):
                        if text_block_idx == state.focused_text_block_index:
                            widget.text_edit.setFocus()
                            cursor_pos = min(
                                state.cursor_position,
                                len(widget.text_edit.text()),
                            )
                            widget.text_edit.setCursorPosition(cursor_pos)
                            return
                        text_block_idx += 1

    def _clear(self) -> None:
        """Remove all rows and pair widgets."""
        logger.debug(f"Clearing sheet builder. Currently has {len(self._pairs)} pairs.")
        for key, pair in list(self._pairs.items()):
            logger.debug(f"Deleting pair widget for key: {key}")
            pair.setParent(None)
            pair.deleteLater()
        self._pairs.clear()

        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        w = child.widget()
                        logger.debug(f"Removing widget from layout: {type(w).__name__}")
                        w.setParent(None)
                        w.deleteLater()

                # Delete the QHBoxLayout to prevent memory leaks
                h_layout = item.layout()
                h_layout.setParent(None)
                h_layout.deleteLater()

    def _add_row(self, items_config: List[Dict[str, Any]]) -> None:
        """Add a new horizontal row of AttributePairWidgets, spacers, text, dividers.

        Args:
            items_config: List of dicts representing each item.
        """
        hlayout = QHBoxLayout()
        hlayout.setSpacing(0)
        hlayout.setContentsMargins(0, 0, 0, 0)

        widget_indices: List[int] = []  # track non-handle indices for resize handles

        for config in items_config:
            item_type = config.get("type", "")
            weight = int(config.get("weight", 1))

            if item_type == "text":
                tb = TextBlockWidget(config.get("text", ""))
                tb.text_changed.connect(self._on_pair_changed)
                idx = hlayout.count()
                hlayout.addWidget(tb, stretch=1)
                widget_indices.append(idx)
                continue

            if item_type == "divider":
                dw = DividerWidget()
                idx = hlayout.count()
                hlayout.addWidget(dw, stretch=1)
                widget_indices.append(idx)
                continue

            if config.get("spacer"):
                sw = SpacerWidget()
                sw.weight = weight
                idx = hlayout.count()
                hlayout.addWidget(sw, stretch=weight)
                widget_indices.append(idx)
                continue

            key = config.get("key")
            value = config.get("value")

            if not key or key in self._pairs:
                if key and key in self._pairs:
                    logger.warning(
                        f"Duplicate attribute key '{key}' ignored in sheet builder."
                    )
                continue

            vtype = "String"
            if isinstance(value, bool):
                vtype = "Boolean"
                str_val = str(value)
            elif isinstance(value, (int, float)):
                vtype = "Number"
                str_val = str(value)
            else:
                str_val = str(value) if value is not None else ""

            pair = AttributePairWidget(key, str_val, vtype)
            pair.weight = weight
            pair.value_changed.connect(self._on_pair_changed)
            pair.drag_started.connect(self._on_child_drag_started)
            pair.drag_finished.connect(self._on_child_drag_finished)
            idx = hlayout.count()
            hlayout.addWidget(pair, stretch=weight)
            self._pairs[key] = pair
            widget_indices.append(idx)

        # Insert resize handles between adjacent real items
        if len(widget_indices) >= 2:
            self._insert_resize_handles(hlayout, widget_indices)

        self._grid_layout.addLayout(hlayout)

    def _insert_resize_handles(
        self, hlayout: QHBoxLayout, widget_indices: List[int]
    ) -> None:
        """Insert resize handles between adjacent items in a row layout.

        Each inserted handle shifts all following item indices by +1, so we
        accumulate an ``offset`` as we iterate left-to-right.

        Args:
            hlayout: The horizontal layout to add handles to.
            widget_indices: Original indices of real items (before handles inserted).
        """
        if len(widget_indices) < 2:
            return

        pairs_for_handles = [
            (widget_indices[i], widget_indices[i + 1])
            for i in range(len(widget_indices) - 1)
        ]

        # offset accumulates because each inserted handle shifts subsequent indices by 1
        offset = 0
        for left_orig, right_orig in pairs_for_handles:
            left_actual = left_orig + offset
            right_actual = right_orig + offset
            insert_at = left_actual + 1
            handle = _ResizeHandle(hlayout, left_actual, right_actual + 1)
            handle.resize_done.connect(self._on_pair_changed)
            hlayout.insertWidget(insert_at, handle, stretch=0)
            offset += 1

    def _append_new_row(self, pair: AttributePairWidget) -> None:
        """Append a pair as the sole widget in a new row at the bottom."""
        hlayout = QHBoxLayout()
        hlayout.setSpacing(0)
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.addWidget(pair, stretch=pair.weight)
        self._grid_layout.addLayout(hlayout)

    def _detach_pair(self, pair: AttributePairWidget) -> None:
        """Remove pair from its current row layout, cleaning up empty rows."""
        for row_idx in range(self._grid_layout.count()):
            row_item = self._grid_layout.itemAt(row_idx)
            if row_item is None or row_item.layout() is None:
                continue
            hlayout = row_item.layout()
            for col_idx in range(hlayout.count()):
                item = hlayout.itemAt(col_idx)
                if item is not None and item.widget() is pair:
                    hlayout.removeWidget(pair)
                    if hlayout.count() == 0:
                        self._grid_layout.removeItem(row_item)
                        hlayout.setParent(None)
                        hlayout.deleteLater()
                    return

    def _row_at_pos(self, pos: QPoint) -> Optional[tuple]:
        """Return (row_idx, hlayout) for the row whose geometry contains *pos*.

        Args:
            pos: Position in container coordinates.

        Returns:
            ``(row_idx, hlayout)`` tuple, or ``None`` if no row matched.
        """
        for row_idx in range(self._grid_layout.count()):
            row_item = self._grid_layout.itemAt(row_idx)
            if row_item is None or row_item.layout() is None:
                continue
            if row_item.layout().geometry().contains(pos):
                return row_idx, row_item.layout()
        return None

    def _calc_drop_position(self, pos: QPoint) -> tuple:
        """Determine the target row index and column index for a drop.

        Args:
            pos: Position in container coordinates.

        Returns:
            Tuple of (row_index, col_index).
        """
        container_pos = self._container.mapFrom(self, pos)
        result = self._row_at_pos(container_pos)
        if result is None:
            return self._grid_layout.count(), 0

        target_row, hlayout = result
        for col_idx in range(hlayout.count()):
            if widget_item := hlayout.itemAt(col_idx):
                if container_pos.x() < widget_item.geometry().center().x():
                    return target_row, col_idx
        return target_row, hlayout.count()

    def _on_pair_changed(self) -> None:
        """Forward pair value changes as attributes_changed."""
        if self._block_depth == 0 and not self._drag_active:
            self.attributes_changed.emit()

    # ------------------------------------------------------------------
    # Child drag lifecycle
    # ------------------------------------------------------------------

    def _on_child_drag_started(self, key: str) -> None:
        """Called when a child AttributePairWidget begins a QDrag.

        Suppresses reloads until the drag completes to prevent the
        dragged widget from being destroyed mid-drag (access violation).

        Args:
            key: The attribute key of the widget being dragged.
        """
        logger.debug(f"Child drag started for key '{key}' – suppressing reloads.")
        self._drag_active = True

    def _on_child_drag_finished(self) -> None:
        """Called when a child QDrag completes.

        Re-enables reloads and replays a deferred load if one arrived
        during the drag.
        """
        logger.debug("Child drag finished – re-enabling reloads.")
        self._drag_active = False

        if self._deferred_reload is not None:
            attrs, layout = self._deferred_reload
            self._deferred_reload = None
            logger.debug("Replaying deferred load_attributes.")
            self.load_attributes(attrs, layout)

    def _on_builder_destroyed(self) -> None:
        """Disconnect theme signal when destroyed."""
        logger.debug("SheetBuilderWidget being destroyed.")
        try:
            self._theme_mgr.theme_changed.disconnect(self._apply_theme)
        except (RuntimeError, TypeError):
            pass
        # Clean up ghost if still alive
        if self._ghost is not None:
            self._ghost.close()
            self._ghost = None

    # ------------------------------------------------------------------
    # Drag feedback helpers
    # ------------------------------------------------------------------

    def _show_insertion_indicator(self, drop_row: int, insert_col: int) -> None:
        """Position and show the insertion line at the given drop location.

        Args:
            drop_row: The target row index.
            insert_col: The target column index within the row.
        """
        if self._insertion_line is None:
            self._insertion_line = _InsertionLine(self._container)

        if drop_row < self._grid_layout.count():
            row_item = self._grid_layout.itemAt(drop_row)
            if row_item and row_item.layout():
                geom = row_item.layout().geometry()
                # Show a thin line at the top of the target row
                self._insertion_line.setGeometry(
                    geom.x(), geom.y() - 2, geom.width(), 3
                )
                self._insertion_line.show()
                self._insertion_line.raise_()
                return

        # Indicate new row at the bottom
        y = self._container.height() - 4
        self._insertion_line.setGeometry(4, y, self._container.width() - 8, 3)
        self._insertion_line.show()
        self._insertion_line.raise_()

    def _cleanup_drag_feedback(self) -> None:
        """Clean up all drag feedback widgets (ghost + insertion line)."""
        if self._ghost is not None:
            self._ghost.close()
            self._ghost.deleteLater()
            self._ghost = None
        if self._insertion_line is not None:
            self._insertion_line.hide()

    # ------------------------------------------------------------------
    # Toolbar action handlers
    # ------------------------------------------------------------------

    def _on_toolbar_add_attribute(self) -> None:
        """Prompt for a new attribute key and add it as a new row."""
        key, ok = QInputDialog.getText(self, "New Attribute", "Attribute key:")
        if ok and key and key.strip():
            key = key.strip()
            if key in self._pairs:
                return
            self.add_attribute(key, "")

    def _on_toolbar_add_spacer(self) -> None:
        """Add a spacer to the last row, or create a new row with a spacer."""
        if self._grid_layout.count() > 0:
            last_item = self._grid_layout.itemAt(self._grid_layout.count() - 1)
            if last_item and last_item.layout():
                hlayout = last_item.layout()
                sw = SpacerWidget()
                sw.weight = 1
                hlayout.addWidget(sw, stretch=1)
                # Re-inject resize handles so the new spacer is resizable
                self._rebuild_resize_handles(hlayout)
                if self._block_depth == 0:
                    self.attributes_changed.emit()
                return
        # No rows yet – create a row containing only a spacer
        self._add_row([{"spacer": True, "weight": 1}])
        if self._block_depth == 0:
            self.attributes_changed.emit()

    def _on_toolbar_add_divider(self) -> None:
        """Add a full-width divider row."""
        self._add_row([{"type": "divider"}])
        if self._block_depth == 0:
            self.attributes_changed.emit()

    def _on_toolbar_add_text(self) -> None:
        """Add a full-width text block row."""
        self._add_row([{"type": "text", "text": ""}])
        if self._block_depth == 0:
            self.attributes_changed.emit()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos: QPoint) -> None:
        """Show a context menu for the clicked row/item."""
        clicked_row, clicked_col, clicked_widget = self._find_clicked_item(pos)

        menu = QMenu(self)

        if clicked_row >= 0:
            self._build_row_context_menu(menu, clicked_row, clicked_col, clicked_widget)
        else:
            self._build_empty_context_menu(menu)

        menu.exec(self._container.mapToGlobal(pos))

    def _find_clicked_item(self, pos: QPoint) -> tuple:
        """Find the row, column, and widget at a given position.

        Returns:
            Tuple of (row_idx, col_idx, widget_or_None).
        """
        clicked_row = -1
        clicked_col = -1
        clicked_widget: Optional[QWidget] = None

        for row_idx in range(self._grid_layout.count()):
            row_item = self._grid_layout.itemAt(row_idx)
            if row_item is None or row_item.layout() is None:
                continue
            hlayout = row_item.layout()
            if hlayout.geometry().contains(pos):
                clicked_row = row_idx
                for col_idx in range(hlayout.count()):
                    item = hlayout.itemAt(col_idx)
                    if (
                        item
                        and item.widget()
                        and item.widget().geometry().contains(pos)
                    ):
                        clicked_widget = item.widget()
                        clicked_col = col_idx
                        break
                break

        return clicked_row, clicked_col, clicked_widget

    def _build_row_context_menu(
        self,
        menu: QMenu,
        row_idx: int,
        col_idx: int,
        widget: Optional[QWidget],
    ) -> None:
        """Build context menu actions for a clicked row."""
        row_item = self._grid_layout.itemAt(row_idx)
        hlayout = row_item.layout() if row_item else None

        act = menu.addAction("⬆ Insert Row Above")
        act.triggered.connect(lambda: self._ctx_insert_row(row_idx))

        act = menu.addAction("⬇ Insert Row Below")
        act.triggered.connect(lambda: self._ctx_insert_row(row_idx + 1))

        menu.addSeparator()

        act = menu.addAction("\u2b1c Add Spacer to Row")
        act.triggered.connect(lambda: self._ctx_add_spacer_to_row(row_idx))

        act = menu.addAction("\u2715 Remove Spacers from Row")
        act.triggered.connect(lambda: self._ctx_remove_spacers_from_row(row_idx))

        menu.addSeparator()

        if widget and isinstance(widget, AttributePairWidget):
            act = menu.addAction(f"⚖ Set Weight ({widget.weight})…")
            act.triggered.connect(
                lambda: self._ctx_set_weight(widget, hlayout, col_idx)
            )

            act = menu.addAction(f"🔄 Type: {widget.get_type()}")
            act.triggered.connect(lambda: self._ctx_toggle_type(widget))

            menu.addSeparator()

        act = menu.addAction("🗑 Delete Row")
        act.triggered.connect(lambda: self._ctx_delete_row(row_idx))

    def _build_empty_context_menu(self, menu: QMenu) -> None:
        """Build context menu for clicks on empty space."""
        act = menu.addAction("＋ Add Attribute")
        act.triggered.connect(self._on_toolbar_add_attribute)

        act = menu.addAction("── Add Divider")
        act.triggered.connect(self._on_toolbar_add_divider)

        act = menu.addAction("𝐓 Add Text")
        act.triggered.connect(self._on_toolbar_add_text)

    # ------------------------------------------------------------------
    # Context menu action helpers
    # ------------------------------------------------------------------

    def _ctx_insert_row(self, at_index: int) -> None:
        """Insert an empty attribute row at the given index via a prompt."""
        key, ok = QInputDialog.getText(self, "New Attribute", "Attribute key:")
        if ok and key and key.strip():
            key = key.strip()
            if key in self._pairs:
                return
            hlayout = QHBoxLayout()
            hlayout.setSpacing(0)
            hlayout.setContentsMargins(0, 0, 0, 0)
            pair = AttributePairWidget(key, "", "String")
            pair.value_changed.connect(self._on_pair_changed)
            pair.drag_started.connect(self._on_child_drag_started)
            pair.drag_finished.connect(self._on_child_drag_finished)
            hlayout.addWidget(pair, stretch=1)
            self._pairs[key] = pair
            self._grid_layout.insertLayout(at_index, hlayout)
            if self._block_depth == 0:
                self.attributes_changed.emit()

    def _ctx_add_spacer_to_row(self, row_idx: int) -> None:
        """Append a spacer to the given row."""
        row_item = self._grid_layout.itemAt(row_idx)
        if row_item and row_item.layout():
            hlayout = row_item.layout()
            sw = SpacerWidget()
            sw.weight = 1
            hlayout.addWidget(sw, stretch=1)
            # Re-inject resize handles so the new spacer is resizable
            self._rebuild_resize_handles(hlayout)
            if self._block_depth == 0:
                self.attributes_changed.emit()

    def _ctx_remove_spacers_from_row(self, row_idx: int) -> None:
        """Remove all spacer items from the given row."""
        row_item = self._grid_layout.itemAt(row_idx)
        if not row_item or not row_item.layout():
            return
        hlayout = row_item.layout()
        # Iterate backwards to safely remove
        for i in range(hlayout.count() - 1, -1, -1):
            item = hlayout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), SpacerWidget):
                widget = item.widget()
                hlayout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()
        # Clean up any now-stale resize handles and rebuild
        self._strip_resize_handles(hlayout)
        self._rebuild_resize_handles(hlayout)
        if self._block_depth == 0:
            self.attributes_changed.emit()

    def _ctx_delete_row(self, row_idx: int) -> None:
        """Delete the row at the given index, removing all its widgets."""
        row_item = self._grid_layout.itemAt(row_idx)
        if not row_item or not row_item.layout():
            return
        hlayout = row_item.layout()
        # Remove widgets and their pair entries
        while hlayout.count():
            child = hlayout.takeAt(0)
            widget = child.widget() if child else None
            if isinstance(widget, AttributePairWidget):
                self._pairs.pop(widget.key, None)
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        self._grid_layout.removeItem(row_item)
        if self._block_depth == 0:
            self.attributes_changed.emit()

    def _ctx_set_weight(
        self,
        widget: AttributePairWidget,
        hlayout: Optional[QHBoxLayout],
        col_idx: int,
    ) -> None:
        """Prompt to change an item's stretch weight."""
        current = widget.weight
        new_weight, ok = QInputDialog.getInt(
            self, "Set Weight", "Stretch weight:", current, 1, 10
        )
        if ok and new_weight != current:
            widget.weight = new_weight
            if hlayout:
                hlayout.setStretch(col_idx, new_weight)
            if self._block_depth == 0:
                self.attributes_changed.emit()

    def _ctx_toggle_type(self, widget: AttributePairWidget) -> None:
        """Cycle the attribute type: String → Number → Boolean → String.

        The type combo is shown when the type is non-default (Number / Boolean)
        and hidden again when cycling back to String.
        """
        cycle = {"String": "Number", "Number": "Boolean", "Boolean": "String"}
        new_type = cycle.get(widget.get_type(), "String")
        widget.set_type(new_type)
        # Hide the combo when back to the default String type
        widget.type_combo.setVisible(new_type != "String")
        if self._block_depth == 0:
            self.attributes_changed.emit()

    # ------------------------------------------------------------------
    # Internal resize-handle helpers
    # ------------------------------------------------------------------

    def _strip_resize_handles(self, hlayout: QHBoxLayout) -> None:
        """Remove all _ResizeHandle widgets from *hlayout* in-place.

        Args:
            hlayout: The row layout to strip handles from.
        """
        for i in range(hlayout.count() - 1, -1, -1):
            item = hlayout.itemAt(i)
            if item and isinstance(item.widget(), _ResizeHandle):
                w = item.widget()
                hlayout.removeWidget(w)
                w.setParent(None)
                w.deleteLater()

    def _rebuild_resize_handles(self, hlayout: QHBoxLayout) -> None:
        """Strip all existing handles from *hlayout* then re-insert them correctly.

        Use this after any in-place structural change to a row (append spacer,
        remove attribute, etc.) to keep handles in sync with real item indices.

        Args:
            hlayout: The row layout to rebuild handles for.
        """
        self._strip_resize_handles(hlayout)
        # Collect indices of non-handle items
        widget_indices: List[int] = [
            i
            for i in range(hlayout.count())
            if not isinstance(hlayout.itemAt(i).widget(), _ResizeHandle)
        ]
        self._insert_resize_handles(hlayout, widget_indices)
