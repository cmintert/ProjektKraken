"""Temporary writing presentation for Event and Entity descriptions."""

from __future__ import annotations

from typing import Any

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QKeySequence, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.editor_presentation import COMPACT_EDITOR_WIDTH


class _PaneTint(QWidget):
    """A purely visual tint that lets pointer events reach the pane below."""

    def __init__(self, pane: QWidget) -> None:
        super().__init__(pane)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        pane.installEventFilter(self)
        self.apply_theme()
        self.setGeometry(pane.rect())
        self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            parent = self.parentWidget()
            if parent is not None:
                self.setGeometry(parent.rect())
        return False

    def apply_theme(self) -> None:
        """Darken the pane enough to make the inactive area visible."""
        color = QColor(ThemeManager().get_theme()["app_bg"]).darker(150)
        self.setStyleSheet(
            "background-color: rgba("
            f"{color.red()}, {color.green()}, {color.blue()}, 60);"
        )


class _FocusSurface(QWidget):
    """Named controls kept in the temporary writing view."""

    title_label: QLabel
    status_label: QLabel
    toolbar_button: QToolButton
    toc_button: QToolButton
    exit_button: QPushButton
    writing_view: Any

    def reflow(self) -> None:
        """Fill compact panes and cap wide panes at the preferred reading width."""
        view = self.writing_view
        available = max(1, self.contentsRect().width() - 24)
        document = view.editor.document()
        preferred = round(
            QFontMetricsF(document.defaultFont()).averageCharWidth()
            * view.editor._typography.line_length
            + document.documentMargin() * 2
            + view.editor.verticalScrollBar().sizeHint().width()
            + 6
        )
        if not view.toc_widget.isHidden() and available >= COMPACT_EDITOR_WIDTH:
            preferred += 200
        view.setFixedWidth(min(available, preferred))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Recompute width from available space, never from a stale size hint."""
        super().resizeEvent(event)
        self.reflow()


class FocusWritingController(QObject):
    """Own the shared focus view and workspace navigation behavior."""

    def __init__(self, window: Any, view_menu: QMenu) -> None:
        """Bind the two description editors to the live workspace."""
        super().__init__(window)
        self.window = window
        self.workspace = window.workspace
        self.editors = {"event": window.event_editor, "entity": window.entity_editor}
        self._active_panel_id = self.workspace.active_panel("center")
        self.active: Any | None = None
        self._restoring = False
        self._tints = {
            zone: _PaneTint(self.workspace.panes[zone])
            for zone in ("left", "center", "right", "bottom")
        }
        self.action = view_menu.addAction("Focus writing")
        self.action.setCheckable(True)
        self.action.setShortcut(QKeySequence("F11"))
        self.action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.action.triggered.connect(self.toggle)
        for editor in self.editors.values():
            editor._focus_controller = self
            editor.focus_writing_requested.connect(
                lambda selected=editor: self.toggle_for(selected)
            )
            editor.name_edit.textChanged.connect(
                lambda text, selected=editor: self._update_title(selected, text)
            )
            editor.dirty_changed.connect(
                lambda _dirty, selected=editor: self._update_status(selected)
            )
        self.workspace.panel_activated.connect(self._on_panel_activated)
        self.workspace.layout_changed.connect(self._sync_tints)
        ThemeManager().theme_changed.connect(self._apply_theme)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.installEventFilter(self)
            app.focusChanged.connect(self._on_focus_changed)
            window.destroyed.connect(lambda: app.removeEventFilter(self))
        self._update_action()

    def _current_editor(self) -> Any | None:
        panel = self._active_panel_id
        editor = self.editors.get(panel)
        return (
            editor
            if editor is not None
            and editor._get_current_item_id()
            and not editor.desc_edit.editor.isReadOnly()
            else None
        )

    def _update_action(self) -> None:
        self.action.setEnabled(
            self.active is not None or self._current_editor() is not None
        )
        self.action.setChecked(self.active is not None)
        self.action.setText("Exit focus" if self.active else "Focus writing")
        for editor in self.editors.values():
            editor._presentation.focus_button.setChecked(self.active is editor)
            editor._presentation.focus_button.setEnabled(
                self.active is editor
                or bool(editor._get_current_item_id())
                and not editor.desc_edit.editor.isReadOnly()
            )

    def toggle(self, _checked: bool = False) -> None:
        """Toggle for the active Event or Entity editor."""
        if self.active is not None:
            self.exit()
        else:
            editor = self._current_editor()
            if editor is not None:
                self.enter(editor)

    def toggle_for(self, editor: Any) -> None:
        """Enter from the local control; only exit actions close focus mode."""
        if self.active is editor:
            editor._presentation.focus_button.setChecked(True)
        elif editor._get_current_item_id() and not editor.desc_edit.editor.isReadOnly():
            if self.active is not None:
                self.exit()
            self.enter(editor)

    def _make_surface(self, editor: Any) -> _FocusSurface:
        surface = _FocusSurface(editor._content_widget)
        surface.writing_view = editor.desc_edit
        surface.setObjectName("FocusWritingSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        header = QVBoxLayout()
        header.setSpacing(4)
        title_row = QHBoxLayout()
        title = QLabel(editor.name_edit.text())
        title.setObjectName("FocusWritingTitle")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        title.setWordWrap(True)
        status = QLabel()
        status.setAccessibleName("Save status")
        toolbar_button = QToolButton()
        toolbar_button.setText("Formatting")
        toolbar_button.setCheckable(True)
        toolbar_button.setAccessibleName("Show formatting toolbar")
        toolbar_button.setMinimumHeight(32)
        toolbar_button.toggled.connect(editor.desc_edit.toolbar.setVisible)
        toc_button = QToolButton()
        toc_button.setText("Contents")
        toc_button.setCheckable(True)
        toc_button.setAccessibleName("Show table of contents")
        toc_button.setMinimumHeight(32)
        toc_button.toggled.connect(
            lambda checked: editor.desc_edit._toggle_toc()
            if checked != editor.desc_edit.toc_widget.isVisible()
            else None
        )
        toc_button.toggled.connect(surface.reflow)
        exit_button = QPushButton("Exit focus")
        exit_button.setMinimumHeight(32)
        exit_button.clicked.connect(self.exit)
        title_row.addWidget(title, 1)
        title_row.addWidget(status)
        header.addLayout(title_row)
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addStretch()
        for widget in (toolbar_button, toc_button, exit_button):
            controls.addWidget(widget)
        header.addLayout(controls)
        layout.addLayout(header)
        writing_row = QHBoxLayout()
        writing_row.setContentsMargins(0, 0, 0, 0)
        writing_row.addStretch(1)
        writing_row.addWidget(editor.desc_edit)
        writing_row.addStretch(1)
        layout.addLayout(writing_row, 1)
        surface.title_label = title
        surface.status_label = status
        surface.toolbar_button = toolbar_button
        surface.toc_button = toc_button
        surface.exit_button = exit_button
        return surface

    def enter(self, editor: Any) -> None:
        """Show the original live editor in a centered writing surface."""
        if (
            self.active is not None
            or not editor._get_current_item_id()
            or editor.desc_edit.editor.isReadOnly()
        ):
            return
        self._restoring = True
        try:
            self._enter_view(editor)
        finally:
            self._restoring = False

    def _enter_view(self, editor: Any) -> None:
        """Move the view while ignoring intermediate Qt focus transitions."""
        self.active = editor
        view = editor.desc_edit
        editor._focus_return_state = {
            "splitter_sizes": editor.description_field.sizes(),
            "toolbar": not view.toolbar.isHidden(),
            "toc": not view.toc_widget.isHidden(),
            "focus": view.editor.hasFocus(),
            "scroll": view.editor.verticalScrollBar().value(),
            "details_scroll": editor.scroll_area.verticalScrollBar().value(),
            "maximum_width": view.maximumWidth(),
            "minimum_width": view.minimumWidth(),
        }
        view.minimum_width_changed.disconnect(
            editor.description_field._reset_to_minimum_width
        )
        surface = self._make_surface(editor)
        editor._focus_surface = surface
        content_layout = editor._content_widget.layout()
        content_layout.insertWidget(
            content_layout.indexOf(editor.inspector), surface, 1
        )
        view.toolbar.hide()
        view.toc_widget.hide()
        editor.header_widget.hide()
        editor.inspector.hide()
        view.editor.verticalScrollBar().setValue(editor._focus_return_state["scroll"])
        surface.show()
        content_layout.activate()
        surface.reflow()
        self._apply_theme(ThemeManager().get_theme())
        self._update_status(editor)
        editor._presentation.focus_button.setChecked(True)
        self._sync_tints()
        self._update_action()
        view.editor.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def exit(self, *, restore_focus: bool = True) -> None:
        """Restore the field and visual state without touching its document."""
        editor = self.active
        if editor is None or self._restoring:
            return
        self._restoring = True
        self.active = None
        try:
            state = editor._focus_return_state
            view = editor.desc_edit
            surface = editor._focus_surface
            focused_scroll = view.editor.verticalScrollBar().value()
            surface.hide()
            editor._content_widget.layout().removeWidget(surface)
            view.setMinimumWidth(state["minimum_width"])
            view.setMaximumWidth(state["maximum_width"])
            editor.description_field.insertWidget(0, view)
            view.show()
            editor._presentation.focus_button.setText("Focus writing")
            editor.header_widget.show()
            editor.inspector.show()
            editor._content_widget.layout().activate()
            editor.description_field.setSizes(state["splitter_sizes"])
            view.toolbar.setVisible(state["toolbar"])
            view.toc_widget.setVisible(state["toc"])
            editor.scroll_area.verticalScrollBar().setValue(state["details_scroll"])
            view.editor.verticalScrollBar().setValue(focused_scroll)
            if restore_focus and state["focus"]:
                view.editor.setFocus(Qt.FocusReason.OtherFocusReason)
            elif restore_focus:
                editor._presentation.focus_button.setFocus(
                    Qt.FocusReason.OtherFocusReason
                )
            view.minimum_width_changed.connect(
                editor.description_field._reset_to_minimum_width
            )
            surface.setParent(None)
            surface.deleteLater()
            editor._focus_surface = None
            editor._presentation.focus_button.setText("Focus writing")
            editor._presentation.focus_button.setChecked(False)
            self.active = None
            for tint in self._tints.values():
                tint.hide()
            self._update_action()
        finally:
            self._restoring = False

    def _update_title(self, editor: Any, text: str) -> None:
        if self.active is editor:
            editor._focus_surface.title_label.setText(text)

    def _update_status(self, editor: Any) -> None:
        if self.active is editor:
            editor._focus_surface.status_label.setText(
                "Unsaved changes" if editor.has_unsaved_changes() else "Saved"
            )

    def _apply_theme(self, _theme: dict) -> None:
        for tint in self._tints.values():
            tint.apply_theme()
        if self.active is not None:
            surface = self.active._focus_surface
            theme = ThemeManager().get_theme()
            surface.title_label.setStyleSheet(
                f"color: {theme['text_main']}; font-weight: 600;"
            )
            surface.status_label.setStyleSheet(f"color: {theme['text_dim']};")
            surface.reflow()
            for button in (
                surface.toolbar_button,
                surface.toc_button,
                surface.exit_button,
            ):
                button.setStyleSheet(
                    StyleHelper.get_tool_button_style()
                    + StyleHelper.get_inspector_focus_style()
                )

    def _active_zone(self) -> str | None:
        """Return the workspace zone containing the focused editor."""
        if self.active is None:
            return None
        panel_id = "event" if self.active is self.editors["event"] else "entity"
        return self.workspace.panel_zone(panel_id)

    def _sync_tints(self) -> None:
        active_zone = self._active_zone()
        for zone, tint in self._tints.items():
            pane = self.workspace.panes[zone]
            tint.setVisible(
                active_zone is not None and zone != active_zone and pane.isVisible()
            )
            if tint.isVisible():
                tint.raise_()

    def _on_panel_activated(self, panel_id: str) -> None:
        self._active_panel_id = panel_id
        if self.active is not None:
            active_id = "event" if self.active is self.editors["event"] else "entity"
            if panel_id != active_id:
                self.exit(restore_focus=False)
        self._update_action()

    def _on_focus_changed(self, _old: QWidget | None, now: QWidget | None) -> None:
        if now is None or self._restoring or not shiboken6.isValid(self.window):
            return
        if any(
            pane.isAncestorOf(now)
            for zone, pane in self.workspace.panes.items()
            if zone != (self._active_zone() or "center")
        ):
            self.exit(restore_focus=False)
            self._active_panel_id = None
            self._update_action()
        elif any(editor.isAncestorOf(now) for editor in self.editors.values()):
            self._active_panel_id = (
                "event" if self.editors["event"].isAncestorOf(now) else "entity"
            )
            self._update_action()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Exit on outside navigation while letting the event through."""
        if self.active is None or self._restoring:
            return False
        if not shiboken6.isValid(self.window):
            return False
        if not isinstance(watched, QWidget) or not (
            watched is self.window or self.window.isAncestorOf(watched)
        ):
            return False
        if event.type() == QEvent.Type.KeyPress and hasattr(event, "key"):
            if event.key() == Qt.Key.Key_Escape:
                app = QApplication.instance()
                if isinstance(app, QApplication) and (
                    app.activePopupWidget() is not None
                    or app.activeModalWidget() is not None
                ):
                    return False
                completer = self.active.desc_edit.editor._completer
                popup = completer.popup() if completer is not None else None
                if popup is None or not popup.isVisible():
                    self.exit()
                    return True
        if event.type() == QEvent.Type.MouseButtonPress:
            if any(
                pane is watched or pane.isAncestorOf(watched)
                for zone, pane in self.workspace.panes.items()
                if zone != (self._active_zone() or "center")
            ):
                self.exit(restore_focus=False)
        return False
