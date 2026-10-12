"""Responsive presentation shared by the Event and Entity inspectors."""

from __future__ import annotations

from typing import Any

import shiboken6
from PySide6.QtCore import QEvent, QObject, QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from src.core.theme_manager import ThemeManager
from src.gui.constants import EDITOR_FORM_VERTICAL_SPACING
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.editor_inspector_composition import (
    EditorInspectorComposition,
    InspectorContent,
)
from src.gui.widgets.menu_caret import PhosphorToolMenuButton
from src.gui.widgets.overflow_toolbar import OverflowToolBar
from src.gui.widgets.wrapping_buttons import WrappingToolButton

COMPACT_EDITOR_WIDTH = 560
EDITOR_CONTROL_HEIGHT = 32
WRITING_COLUMN_MAX_WIDTH = 760


class DisclosureButton(WrappingToolButton):
    """Named, keyboard accessible disclosure with a full-row hit target."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """Create a disclosure using the standard editor control height."""
        super().__init__(parent)
        self.setText(title.replace("&", "&&"))
        self.setAccessibleName(title)
        self.setCheckable(True)
        self.setMinimumHeight(32)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggled.connect(self._update_arrow)
        self._update_arrow(False)
        self._apply_theme()
        ThemeManager().theme_changed.connect(self._apply_theme)

    def _update_arrow(self, expanded: bool) -> None:
        writing_action = self.objectName() == "InspectorWritingAction"
        if writing_action:
            state = "Expanded" if expanded else "Collapsed"
            self.setAccessibleDescription(f"{state}. {self.toolTip()}")
        theme = ThemeManager().get_theme()
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(round(16 * ratio), round(16 * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        arrow_role = "text_dim"
        if writing_action:
            arrow_role = "action_quiet_checked_text" if expanded else "supporting_text"
        pen = QPen(QColor(theme[arrow_role]), 1.25)
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
        if self.objectName() == "InspectorWritingAction":
            self.setStyleSheet(StyleHelper.get_inspector_support_style())
            self._update_arrow(self.isChecked())
            return
        self.setStyleSheet(
            StyleHelper.get_tool_button_style()
            + StyleHelper.get_inspector_focus_style()
        )
        self._update_arrow(self.isChecked())


class SupportingSectionHeader(DisclosureButton):
    """Quiet, keyboard-accessible heading for supporting information."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """Create a quiet heading without changing ordinary disclosures."""
        super().__init__(title, parent)
        self.setObjectName("InspectorSupportingHeader")
        self._apply_theme()

    def _apply_theme(self, _theme: dict | None = None) -> None:
        self.setStyleSheet(StyleHelper.get_inspector_support_style())
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
        editor.llm_generator.layout().setContentsMargins(0, 0, 0, 0)
        for combo in editor.llm_generator.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setMinimumContentsLength(8)
        for label in editor.llm_generator.findChildren(QLabel):
            label.setWordWrap(True)
        self._toolbar_more_buttons: list[QToolButton] = []
        self._install_toolbar_menus()
        self._install_action_rows()
        self._install_writing_support()
        self._install_writing_column()
        self.context_disclosure = SupportingSectionHeader("History & context")
        self.history_disclosure = self.context_disclosure
        self.composition = EditorInspectorComposition(
            editor.inspector,
            InspectorContent(
                overview=editor.tab_details,
                overview_form=editor.form_layout,
                context=editor.tab_context,
                context_renderer=editor.authoring_context,
                context_disclosure=self.context_disclosure,
                linked_events=getattr(editor, "timeline_display", None),
                map_links=editor.raster_appearances_label,
                tags=editor.tab_tags,
                connections=editor.tab_relations,
                fields=editor.tab_attributes,
                sheet=editor.tab_sheet,
                media=editor.tab_gallery,
            ),
        )
        if hasattr(editor, "temporal_snapshot_label"):
            editor.temporal_snapshot_label.setWordWrap(True)
            editor.description_source_label.setWordWrap(True)
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
            if isinstance(field, QLineEdit) and isinstance(
                field.parentWidget(), QComboBox
            ):
                continue
            if isinstance(field, (QLineEdit, QComboBox, QAbstractSpinBox)):
                if field.maximumHeight() >= EDITOR_CONTROL_HEIGHT:
                    field.setMinimumHeight(EDITOR_CONTROL_HEIGHT)
        editor.name_edit.setAccessibleName("Name")
        self._install_header_scroll()
        editor.installEventFilter(self)
        editor.details_container.installEventFilter(self)
        editor.llm_generator.installEventFilter(self)
        self.writing_actions.installEventFilter(self)
        self._focus_suffix = ""
        ThemeManager().theme_changed.connect(self._style_controls)
        self._style_controls()
        self.reflow()

    def _install_focus_button(self) -> None:
        """Keep focus writing directly available in the secondary command strip."""
        row = self.editor.desc_edit.link_toolbar
        self.focus_button = WrappingToolButton(row)
        self.focus_button.setText("Focus writing")
        self.focus_button.setAccessibleName("Focus writing")
        self.focus_button.setToolTip("Focus writing (F11)")
        self.focus_button.setCheckable(True)
        self.focus_button.setMinimumHeight(32)
        self.focus_button.clicked.connect(self.editor.focus_writing_requested.emit)
        row.add_button(self.focus_button, priority=5, pinned=True)

    def _style_controls(self, _theme: dict | None = None) -> None:
        """Keep inspector focus and control boundaries visible in both themes."""
        self.focus_button.setStyleSheet(StyleHelper.get_writing_editor_control_style())
        suffix = StyleHelper.get_inspector_focus_style()
        for widget in self.editor.findChildren(QWidget):
            if isinstance(widget, QLineEdit) and isinstance(
                widget.parentWidget(), QComboBox
            ):
                continue
            if isinstance(
                widget, (QAbstractButton, QLineEdit, QComboBox, QAbstractSpinBox)
            ):
                style = widget.styleSheet()
                if self._focus_suffix:
                    style = style.replace(self._focus_suffix, "")
                if suffix not in style:
                    if style.strip() and "{" not in style:
                        # Inline declarations need a selector before appending
                        # shared focus rules; otherwise Qt rejects the sheet.
                        raw_name = widget.metaObject().className()
                        selector = (
                            raw_name
                            if isinstance(raw_name, str)
                            else bytes(raw_name).decode("utf-8")
                        )
                        style = f"{selector} {{ {style} }} "
                    widget.setStyleSheet(style + suffix)
        self._focus_suffix = suffix
        for button in self._toolbar_more_buttons:
            button.setStyleSheet(
                StyleHelper.get_overflow_button_style()
                + StyleHelper.get_menu_caret_style()
                + suffix
            )
        for button in (self.editor.summary_checkbox, self.editor.llm_checkbox):
            button._apply_theme()
        self.context_disclosure._apply_theme()
        support_style = StyleHelper.get_inspector_support_style()
        self.writing_actions.setStyleSheet(support_style)
        self.editor.summary_container.setStyleSheet(support_style)
        self.editor.llm_container.setStyleSheet(support_style)
        self.composition.history_container.setStyleSheet(support_style)

    def _install_header_scroll(self) -> None:
        """Retain live object fields while reserving readable inspector space."""
        layout = self.editor._content_widget.layout()
        index = layout.indexOf(self.editor.header_widget)
        layout.removeWidget(self.editor.header_widget)
        self.header_scroll = QScrollArea()
        self.header_scroll.setWidgetResizable(True)
        self.header_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.header_scroll.setAccessibleName("Object details")
        self.header_scroll.setWidget(self.editor.header_widget)
        self.header_scroll.viewport().setAutoFillBackground(False)
        self.header_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.insertWidget(index, self.header_scroll)
        layout.setStretch(layout.indexOf(self.editor.inspector), 1)
        self._header_fit_timer = QTimer(self)
        self._header_fit_timer.setSingleShot(True)
        self._header_fit_timer.timeout.connect(self._fit_header)
        self.editor.header_widget.installEventFilter(self)

    def _fit_header(self) -> None:
        """Give the longest visible action enough height before capping fields."""
        editor = self.editor
        layout = editor._content_widget.layout()
        width = max(1, editor.details_container.width())
        required = max(
            (
                button.heightForWidth(min(width, button.width()))
                for button in editor.findChildren(QAbstractButton)
                if button.isVisibleTo(editor)
                and not editor.header_widget.isAncestorOf(button)
                and callable(getattr(button, "label_geometry", None))
            ),
            default=EDITOR_CONTROL_HEIGHT,
        )
        margins = layout.contentsMargins()
        details = editor.details_container.layout().contentsMargins()
        footer_widget = editor.btn_save.parentWidget()
        footer = max(
            footer_widget.minimumHeight(),
            footer_widget.heightForWidth(footer_widget.width()),
            footer_widget.sizeHint().height(),
        )
        corner = editor.inspector.main_tabs.tabBar().sizeHint().height()
        if editor.scroll_area.isVisibleTo(editor):
            corner = max(
                corner,
                editor.inspector.height() - editor.scroll_area.viewport().height(),
            )
        chrome = (
            margins.top()
            + margins.bottom()
            + details.top()
            + details.bottom()
            + layout.spacing() * max(0, layout.count() - 1)
        )
        budget = editor._content_widget.height() - footer - corner - required - chrome
        header = editor.header_widget.layout()
        natural = header.totalHeightForWidth(self.header_scroll.viewport().width())
        if natural < 0:
            natural = header.sizeHint().height()
        height = min(natural, max(editor.btn_inject.sizeHint().height(), budget))
        if (
            self.header_scroll.minimumHeight() != height
            or self.header_scroll.maximumHeight() != height
        ):
            self.header_scroll.setFixedHeight(height)

    def _install_writing_support(self) -> None:
        """Move live writing tools beside the description and retire old bars."""
        editor = self.editor
        form = editor.form_layout
        for name in (
            "summary_container",
            "llm_container",
            "raster_appearances_container",
            "timeline_container",
        ):
            container = getattr(editor, name, None)
            if container is not None:
                form.takeRow(container)
                container.hide()

        self.writing_actions = QWidget()
        from src.gui.widgets.action_flow_layout import ActionFlowLayout

        self._writing_grid = ActionFlowLayout(self.writing_actions)
        self._writing_grid.setContentsMargins(0, 0, 0, 0)
        self._writing_grid.setSpacing(4)
        self._summary_action_group = QWidget()
        from src.gui.widgets.action_flow_layout import ActionFlowLayout

        summary_row = ActionFlowLayout(self._summary_action_group)
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(4)
        self.summary_availability = QLabel("Available")
        self.summary_availability.setObjectName("InspectorSupportCaption")
        self.summary_availability.setAccessibleName("Summary available")
        self.summary_availability.hide()
        for button, container, title, explanation in (
            (
                editor.summary_checkbox,
                editor.summary_container,
                "Summary…",
                "A short version of this description.",
            ),
            (
                editor.llm_checkbox,
                editor.llm_container,
                "Draft with AI…",
                "Generate a draft, then review it before applying.",
            ),
        ):
            container.layout().removeWidget(button)
            button.setObjectName("InspectorWritingAction")
            button.setText(title)
            button.setAccessibleName(title)
            button.setToolTip(explanation)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button._apply_theme()
            caption = QLabel(explanation)
            caption.setObjectName("InspectorSupportCaption")
            caption.setWordWrap(True)
            container.layout().insertWidget(0, caption)
            button.toggled.connect(container.setVisible)
        summary_row.addWidget(editor.summary_checkbox)
        summary_row.addWidget(self.summary_availability)
        self._writing_grid.addWidget(self._summary_action_group)
        self._writing_grid.addWidget(editor.llm_checkbox)
        self._writing_compact: bool | None = None
        row, _role = form.getWidgetPosition(editor.description_field)
        # Keep the actions aligned with the writing field in a wide form.
        # A hidden label contributes no extra line in the compact form.
        action_label = QLabel()
        action_label.hide()
        form.insertRow(row + 1, action_label, self.writing_actions)
        form.insertRow(row + 2, editor.summary_container)
        form.insertRow(row + 3, editor.llm_container)
        editor.summary_widget.presence_changed.connect(self._summary_presence_changed)

    def _install_writing_column(self) -> None:
        """Center the live writing controls as one responsive Overview block."""
        editor = self.editor
        form = editor.form_layout
        row, _role = form.getWidgetPosition(editor.description_field)

        self.writing_column = QWidget(editor.details_container)
        column_layout = QVBoxLayout(self.writing_column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(EDITOR_FORM_VERTICAL_SPACING)

        description_row = form.takeRow(editor.description_field)
        assert description_row.labelItem is not None
        description_label = description_row.labelItem.widget()
        assert isinstance(description_label, QLabel)
        description_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        column_layout.addWidget(description_label)
        column_layout.addWidget(editor.description_field)

        if hasattr(editor, "description_source_label"):
            source_row = form.takeRow(editor.description_source_label)
            assert source_row.labelItem is not None
            source_label = source_row.labelItem.widget()
            assert isinstance(source_label, QLabel)
            source_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self._source_label = source_label
            source_label.setHidden(editor.description_source_label.isHidden())
            editor.description_source_label.installEventFilter(self)
            column_layout.addWidget(source_label)
            column_layout.addWidget(editor.description_source_label)
            form.takeRow(editor.new_description_actions)
            column_layout.addWidget(editor.new_description_actions)

        for widget in (
            self.writing_actions,
            editor.summary_container,
            editor.llm_container,
        ):
            form.takeRow(widget)
            column_layout.addWidget(widget)

        # The bounded column replaces the splitter's empty width-absorbing pane.
        # Keep the splitter and its editor child for Focus writing's state restore.
        editor.description_field.set_fill_width(True)
        self.writing_column.setMaximumWidth(WRITING_COLUMN_MAX_WIDTH)
        self.writing_column.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        centered = QWidget(editor.details_container)
        centered_layout = QHBoxLayout(centered)
        centered_layout.setContentsMargins(0, 0, 0, 0)
        centered_layout.setSpacing(0)
        # Give the column almost all compact width; equal side stretches take
        # the remaining space once it reaches its maximum readable width.
        centered_layout.addStretch(1)
        centered_layout.addWidget(self.writing_column, 100)
        centered_layout.addStretch(1)
        form.insertRow(row, centered)

    def _summary_presence_changed(self, present: bool) -> None:
        """Indicate available content without promising persistence."""
        self.summary_availability.setVisible(present)
        self._reflow_writing_actions()
        self._fit_header()

    def _reflow_writing_actions(self) -> None:
        """Wrap the two live actions only when their actual row cannot fit."""
        self._writing_grid.invalidate()
        height = max(
            self._writing_grid.minimumSize().height(),
            self._writing_grid.heightForWidth(self.writing_actions.width()),
        )
        if self.writing_actions.minimumHeight() != height:
            self.writing_actions.setMinimumHeight(height)
            self.writing_actions.updateGeometry()

    def _install_toolbar_menus(self) -> None:
        """Expose existing toolbar actions when native extensions are cramped."""
        for toolbar, title in (
            (self.editor.sheet_builder._toolbar, "More Sheet actions"),
        ):
            actions = toolbar.actions()
            button = PhosphorToolMenuButton(toolbar.parentWidget())
            button.setObjectName("OverflowToolBarMenuButton")
            button.setProperty("actionLabelOverflowRoute", True)
            button.setText(title)
            button.setAccessibleName(title)
            button.setToolTip(title)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            menu = QMenu(button)
            menu.setToolTipsVisible(True)
            for action in actions:
                if not isinstance(action, QWidgetAction):
                    menu.addAction(action)
            button.setMenu(menu)
            from src.gui.widgets.action_flow_layout import ActionFlowLayout

            row = QWidget(toolbar.parentWidget())
            row_layout = ActionFlowLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(button)
            toolbar.parentWidget().layout().insertWidget(0, row)
            self._toolbar_more_buttons.append(button)

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
        self._overflow_row(
            editor.gallery,
            [
                editor.gallery.btn_add,
                editor.gallery.btn_edit,
                editor.gallery.btn_remove,
            ],
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
                "Other connections",
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
                {"Participants": "Add participant…", "Locations": "Add location…"}.get(
                    title, "Connected to…"
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
        if not all(
            widget is not None and shiboken6.isValid(widget)
            for widget in (
                self.editor.details_container,
                getattr(self, "header_scroll", None),
            )
        ):
            return False
        if watched is getattr(self.editor, "description_source_label", None):
            if event.type() in (
                QEvent.Type.Show,
                QEvent.Type.Hide,
            ) and shiboken6.isValid(self._source_label):
                self._source_label.setVisible(event.type() == QEvent.Type.Show)
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.reflow()
        if event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
        ):
            self._header_fit_timer.start(0)
        return super().eventFilter(watched, event)

    def reflow(self) -> None:
        """Switch labels and header actions at the editor width breakpoint."""
        self._reflow_writing_actions()
        compact = (
            min(self.editor.width(), self.editor.details_container.width())
            < COMPACT_EDITOR_WIDTH
        )
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
