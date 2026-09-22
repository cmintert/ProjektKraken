"""Responsive presentation shared by the Event and Entity inspectors."""

from __future__ import annotations

from typing import Any

import shiboken6
from PySide6.QtCore import QEvent, QObject, QPointF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.overflow_toolbar import OverflowToolBar

COMPACT_EDITOR_WIDTH = 560
EDITOR_CONTROL_HEIGHT = 32
GENERATION_GRID_WIDTH = 960


class DisclosureButton(QToolButton):
    """Named, keyboard accessible disclosure with a full-row hit target."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """Create a disclosure using the standard editor control height."""
        super().__init__(parent)
        self.setText(title)
        self.setAccessibleName(title)
        self.setCheckable(True)
        self.setMinimumHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggled.connect(self._update_arrow)
        self._update_arrow(False)
        self._apply_theme()
        ThemeManager().theme_changed.connect(self._apply_theme)

    def _update_arrow(self, expanded: bool) -> None:
        theme = ThemeManager().get_theme()
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(round(16 * ratio), round(16 * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(theme["text_dim"]), 1.25)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        points = (
            [QPointF(4, 6), QPointF(8, 10), QPointF(12, 6)]
            if expanded
            else [QPointF(6, 4), QPointF(10, 8), QPointF(6, 12)]
        )
        painter.drawPolyline(points)
        painter.end()
        self.setArrowType(Qt.ArrowType.NoArrow)
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(16, 16))

    def _apply_theme(self, _theme: dict | None = None) -> None:
        self.setStyleSheet(
            StyleHelper.get_tool_button_style()
            + StyleHelper.get_inspector_focus_style()
        )
        self._update_arrow(self.isChecked())


class EditorPresentation(QObject):
    """Reflow an editor without recreating its fields or changing its data."""

    def __init__(self, editor: Any) -> None:
        """Bind presentation to the existing editor field instances."""
        super().__init__(editor)
        self.editor = editor
        self._compact: bool | None = None
        self._name_layout = editor.header_form.itemAt(
            0, QFormLayout.ItemRole.FieldRole
        ).layout()
        self._inject_row = QWidget(editor.header_widget)
        inject_layout = QHBoxLayout(self._inject_row)
        self._inject_layout = inject_layout
        inject_layout.setContentsMargins(0, 0, 0, 0)
        inject_layout.addStretch()
        editor.header_widget.layout().addWidget(self._inject_row)
        self._inject_row.hide()
        editor.desc_edit.set_adaptive_width(True)
        self._install_focus_button()
        editor.summary_widget.text_display.set_adaptive_width(True)
        editor.summary_widget.metadata_label.setWordWrap(True)
        editor.summary_widget.stale_label.setWordWrap(True)
        self._generation_grid = editor.llm_generator.layout().itemAt(1).layout()
        editor.llm_generator.layout().setContentsMargins(0, 0, 0, 0)
        assert isinstance(self._generation_grid, QGridLayout)
        self._generation_items = []
        for i in range(self._generation_grid.count()):
            item = self._generation_grid.itemAt(i)
            assert item is not None
            widget = item.widget()
            assert widget is not None
            self._generation_items.append(
                (widget, self._generation_grid.getItemPosition(i))
            )
        self._generation_compact: bool | None = None
        for combo in editor.llm_generator.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setMinimumContentsLength(8)
        for label in editor.llm_generator.findChildren(QLabel):
            label.setWordWrap(True)
        self._install_action_rows()
        if hasattr(editor, "timeline_display"):
            editor.desc_edit.minimum_width_changed.disconnect(
                editor.timeline_display.setMinimumWidth
            )
            editor.timeline_display.setMinimumWidth(0)
        for button in editor.findChildren(QAbstractButton):
            if (
                button.minimumHeight() < EDITOR_CONTROL_HEIGHT
                and button.maximumHeight() >= EDITOR_CONTROL_HEIGHT
            ):
                button.setMinimumHeight(32)
            if not button.accessibleName():
                button.setAccessibleName(button.text() or button.toolTip())
        for field in editor.findChildren(QWidget):
            if isinstance(field, (QLineEdit, QComboBox, QAbstractSpinBox)):
                if field.maximumHeight() >= EDITOR_CONTROL_HEIGHT:
                    field.setMinimumHeight(EDITOR_CONTROL_HEIGHT)
        editor.name_edit.setAccessibleName("Name")
        editor.installEventFilter(self)
        self._focus_suffix = ""
        ThemeManager().theme_changed.connect(self._style_controls)
        self._style_controls()
        self.reflow()

    def _install_focus_button(self) -> None:
        """Put focus writing first in the description formatting toolbar."""
        self.focus_button = QToolButton(self.editor.desc_edit.toolbar)
        self.focus_button.setText("Focus writing")
        self.focus_button.setAccessibleName("Focus writing")
        self.focus_button.setToolTip("Focus writing (F11)")
        self.focus_button.setCheckable(True)
        self.focus_button.setMinimumHeight(32)
        self.focus_button.clicked.connect(self.editor.focus_writing_requested.emit)
        self._focus_toolbar_action = self.editor.desc_edit.toolbar.insertWidget(
            self.editor.desc_edit.editor.action_bold,
            self.focus_button,
        )

    def _style_controls(self, _theme: dict | None = None) -> None:
        """Keep inspector focus and control boundaries visible in both themes."""
        suffix = StyleHelper.get_inspector_focus_style()
        for widget in self.editor.findChildren(QWidget):
            if isinstance(
                widget, (QAbstractButton, QLineEdit, QComboBox, QAbstractSpinBox)
            ):
                style = widget.styleSheet()
                if self._focus_suffix:
                    style = style.replace(self._focus_suffix, "")
                if suffix not in style:
                    widget.setStyleSheet(style + suffix)
        self._focus_suffix = suffix

    @staticmethod
    def _overflow_row(
        owner: QWidget,
        buttons: list[QAbstractButton],
        row_index: int = 0,
        *,
        pin_primary: bool = False,
    ) -> OverflowToolBar:
        """Replace a plain action row while retaining its button instances."""
        layout = owner.layout()
        assert isinstance(layout, QVBoxLayout)
        row = layout.takeAt(row_index)
        assert row is not None
        old_layout = row.layout()
        assert old_layout is not None
        toolbar = OverflowToolBar(owner)
        for index, button in enumerate(buttons):
            old_layout.removeWidget(button)
            button.setMinimumHeight(32)
            toolbar.add_button(
                button,
                priority=10 if index == 0 else 0,
                pinned=pin_primary and index == 0,
            )
        while old_layout.count():
            item = old_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
        old_layout.deleteLater()
        layout.insertWidget(row_index, toolbar)
        return toolbar

    def _install_action_rows(self) -> None:
        editor = self.editor
        generator = editor.llm_generator
        for index in range(generator.layout().count()):
            row = generator.layout().itemAt(index).layout()
            if row is not None and row.indexOf(generator.generate_btn) >= 0:
                self._overflow_row(
                    generator,
                    [
                        generator.generate_btn,
                        generator.preview_btn,
                        generator.cancel_btn,
                    ],
                    index,
                )
                break
        self._overflow_row(
            editor.gallery,
            [
                editor.gallery.btn_add,
                editor.gallery.btn_edit,
                editor.gallery.btn_remove,
            ],
        )
        self._overflow_row(
            editor.attribute_editor,
            [editor.attribute_editor.btn_add, editor.attribute_editor.btn_remove],
            pin_primary=True,
        )
        if not hasattr(editor, "grp_participants"):
            self._overflow_row(
                editor.tab_relations,
                [editor.btn_add_rel, editor.btn_edit_rel, editor.btn_remove_rel],
            )
            return
        groups = [
            (
                "Participants",
                editor.grp_participants,
                editor.participant_list,
                editor.btn_add_participant,
                editor.btn_edit_participant,
                editor.btn_remove_participant,
            ),
            (
                "Locations",
                editor.grp_locations,
                editor.location_list,
                editor.btn_add_location,
                editor.btn_edit_location,
                editor.btn_remove_location,
            ),
            (
                "Custom relations",
                editor.grp_relations,
                editor.rel_list,
                editor.btn_add_rel,
                editor.btn_edit_rel,
                editor.btn_remove_rel,
            ),
        ]
        layout = editor.tab_relations.layout()
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        for title, group, items, add, edit, remove in groups:
            layout.removeWidget(group)
            add.setText(
                {"Participants": "Add participant", "Locations": "Add location"}.get(
                    title, "Add relation"
                )
            )
            add.setMinimumSize(0, 32)
            add.setMaximumSize(16777215, 16777215)
            toolbar = self._overflow_row(group, [add, edit, remove])
            disclosure = DisclosureButton(title)
            group.layout().insertWidget(0, disclosure)
            empty = QLabel(items.property("placeholderText"))
            empty.setWordWrap(True)
            group.layout().insertWidget(2, empty)
            items.setMinimumHeight(80)

            def refresh(
                *_args: object,
                button: DisclosureButton = disclosure,
                label: QLabel = empty,
                view: Any = items,
                actions: QWidget = toolbar,
                name: str = title,
            ) -> None:
                if not all(
                    shiboken6.isValid(w) for w in (button, label, view, actions)
                ):
                    return
                button.setText(f"{name} ({view.count()})")
                actions.setVisible(button.isChecked())
                label.setVisible(button.isChecked() and not view.count())
                view.setVisible(button.isChecked() and bool(view.count()))

            disclosure.toggled.connect(refresh)
            items.model().rowsInserted.connect(refresh)
            items.model().rowsRemoved.connect(refresh)
            items.model().modelReset.connect(refresh)
            disclosure.setChecked(True)
            content_layout.addWidget(group)
        content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        # QScrollArea enables an opaque platform-palette background by default.
        # Let the enclosing, theme-styled inspector supply the background.
        content.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        layout.addWidget(scroll)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Reflow only when the host geometry or visibility changes."""
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.reflow()
        return super().eventFilter(watched, event)

    def reflow(self) -> None:
        """Switch labels and header actions at the editor width breakpoint."""
        compact = self.editor.width() < COMPACT_EDITOR_WIDTH
        generation_compact = self.editor.width() < GENERATION_GRID_WIDTH
        if generation_compact != self._generation_compact:
            self._generation_compact = generation_compact
            for index, (widget, position) in enumerate(self._generation_items):
                self._generation_grid.removeWidget(widget)
                if generation_compact:
                    self._generation_grid.addWidget(widget, index, 0)
                else:
                    self._generation_grid.addWidget(widget, *position)
        if compact == self._compact:
            return
        self._compact = compact
        policy = (
            QFormLayout.RowWrapPolicy.WrapAllRows
            if compact
            else QFormLayout.RowWrapPolicy.DontWrapRows
        )
        for form in (self.editor.form_layout, self.editor.header_form):
            form.setRowWrapPolicy(policy)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            form.setVerticalSpacing(12)
        if compact:
            self._name_layout.removeWidget(self.editor.btn_inject)
            self._inject_layout.addWidget(self.editor.btn_inject)
        else:
            self._inject_layout.removeWidget(self.editor.btn_inject)
            self._name_layout.addWidget(self.editor.btn_inject)
        self._inject_row.setVisible(compact)
        self.editor.btn_inject.show()
