"""Read-only companion presentation; all navigation is emitted as intent."""

from __future__ import annotations

import html
from typing import Any

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QCloseEvent, QImage, QResizeEvent
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.action_flow_layout import ActionFlowLayout


class HelpBrowser(QTextBrowser):
    """Request local resources through the coordinator, never Qt's URL loader."""

    resource_requested = Signal(int, QUrl)

    def __init__(self, parent: QWidget) -> None:
        """Disable automatic navigation and external access."""
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.resource_result: Any = None

    def loadResource(self, kind: int, url: QUrl | str) -> Any:  # noqa: N802
        """Synchronously request a validated resource on the GUI thread."""
        self.resource_result = QImage()
        self.resource_requested.emit(kind, QUrl(url))
        return self.resource_result


class HelpViewer(QWidget):
    """Present content and navigation without services or world dependencies."""

    back_requested = Signal()
    forward_requested = Signal()
    manual_requested = Signal()
    refresh_requested = Signal()
    return_requested = Signal()
    link_requested = Signal(QUrl)
    search_requested = Signal()
    query_changed = Signal(str)
    search_activate_requested = Signal()
    result_requested = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        """Build a wrapping, keyboard-accessible companion."""
        from PySide6.QtCore import Qt

        super().__init__(parent, Qt.WindowType.Window)
        self.setProperty("krakenHelpWindow", True)
        self.setObjectName("ReadOnlyCompanion")
        self.setWindowTitle("ProjektKraken Help")
        self._content: str | None = None
        self._related_links: list[tuple[str, str]] = []
        self.resize(640, 560)
        layout = QVBoxLayout(self)
        row = QWidget(self)
        flow = ActionFlowLayout(row)
        self.buttons: dict[str, QPushButton] = {}
        for label, signal in (
            ("Back", self.back_requested),
            ("Forward", self.forward_requested),
            ("Manual", self.manual_requested),
            ("Search", self.search_requested),
            ("Refresh context", self.refresh_requested),
            ("Return to work", self.return_requested),
        ):
            button = QPushButton(label, row)
            button.setAccessibleName(label)
            button.clicked.connect(signal.emit)
            flow.addWidget(button)
            self.buttons[label] = button
        layout.addWidget(row)
        self.search_panel = QWidget(self)
        self.search_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        search_layout = QVBoxLayout(self.search_panel)
        search_layout.setContentsMargins(0, 0, 0, 0)
        self.search_label = QLabel("Search the offline manual", self.search_panel)
        self.query = QLineEdit(self.search_panel)
        self.query.setAccessibleName("Search the offline manual")
        self.search_label.setBuddy(self.query)
        self.query.textChanged.connect(self.query_changed.emit)
        self.query.returnPressed.connect(self.search_activate_requested.emit)
        self.search_status = QLabel(self.search_panel)
        self.search_status.setWordWrap(True)
        self.results = QListWidget(self.search_panel)
        self.results.setAccessibleName("Help search results")
        self.results.setWordWrap(True)
        self.results.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.setMaximumHeight(160)
        self.results.itemActivated.connect(
            lambda item: self.result_requested.emit(self.results.row(item))
        )
        for widget in (self.search_label, self.query, self.search_status, self.results):
            search_layout.addWidget(widget)
        layout.addWidget(self.search_panel)
        self.search_panel.hide()
        self.title = QLabel(self)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.browser = HelpBrowser(self)
        self.browser.setAccessibleName("Help topic reader")
        self.browser.anchorClicked.connect(self.link_requested.emit)
        layout.addWidget(self.browser)
        self.related = QLabel(self)
        self.related.setWordWrap(True)
        self.related.setOpenExternalLinks(False)
        self.related.linkActivated.connect(
            lambda link: self.link_requested.emit(QUrl(link))
        )
        layout.addWidget(self.related)
        self.set_history(False, False)
        connect_theme(self, self.apply_theme)
        self.apply_theme()

    def set_history(self, back: bool, forward: bool) -> None:
        """Expose history availability without hiding navigation."""
        self.buttons["Back"].setEnabled(back)
        self.buttons["Forward"].setEnabled(forward)
        self.buttons["Back"].setToolTip("Previous Help page")
        self.buttons["Forward"].setToolTip("Next Help page")

    def show_search(self) -> None:
        """Reveal the retained query and focus it without changing the topic."""
        self.search_panel.show()
        self._fit_search()
        self.query.setFocus()
        self.query.selectAll()

    def hide_search(self) -> None:
        """Return to reading without discarding query or results."""
        self.search_panel.hide()
        self.browser.setFocus()

    def set_search_results(self, rows: list[str], status: str) -> None:
        """Present plain-text search snapshots and explicit status."""
        self.results.clear()
        self.results.addItems(rows)
        if rows:
            self.results.setCurrentRow(0)
        self.search_status.setText(status)
        self.results.setVisible(bool(rows))
        self._fit_search()

    def _fit_search(self) -> None:
        layout = self.search_panel.layout()
        if layout is not None:
            layout.activate()
            height = layout.totalHeightForWidth(self.search_panel.width())
            if height < 0:
                height = layout.sizeHint().height()
            self.search_panel.setFixedHeight(height)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Keep the search region compact as labels wrap at narrower widths."""
        super().resizeEvent(event)
        if hasattr(self, "search_panel"):
            self._fit_search()

    def set_content(self, content: str) -> None:
        """Retain the original rendered HTML for lossless theme refresh."""
        self._content = content
        self.browser.setHtml(content)

    def set_error(self, message: str) -> None:
        """Replace reference text with a local recovery message."""
        self._content = None
        self.browser.setPlainText(message)

    def set_related(self, links: list[tuple[str, str]]) -> None:
        """Render related-topic snapshots with the shared neutral link style."""
        self._related_links = links
        style = StyleHelper.get_wiki_link_style()
        self.related.setText(
            " · ".join(
                f'<a href="{html.escape(uri)}" style="{style}">{html.escape(title)}</a>'
                for uri, title in links
            )
        )

    def apply_theme(self, _theme: dict[str, Any] | None = None) -> None:
        """Use shared navigation and semantic reader/link roles."""
        theme = ThemeManager().get_theme()
        self.setStyleSheet(StyleHelper.get_read_only_companion_style())
        for button in self.buttons.values():
            button.setStyleSheet(StyleHelper.get_secondary_button_style())
        self.query.setStyleSheet(StyleHelper.get_search_field_style())
        self.results.setStyleSheet(StyleHelper.get_read_only_list_style())
        self.search_status.setStyleSheet(f"color: {theme['supporting_caption']};")
        self.search_label.setStyleSheet(StyleHelper.get_read_only_text_style())
        self.title.setStyleSheet(f"color: {theme['supporting_caption']};")
        self.related.setStyleSheet(f"color: {theme['link_neutral']};")
        self.set_related(self._related_links)
        position = self.browser.verticalScrollBar().value()
        cursor = self.browser.textCursor()
        self.browser.document().setDefaultStyleSheet(
            f"body {{ color: {theme['text_main']}; }} "
            f"a {{ color: {theme['link_neutral']}; text-decoration: underline; }}"
        )
        if self._content is not None:
            self.browser.setHtml(self._content)
            self.browser.setTextCursor(cursor)
            self.browser.verticalScrollBar().setValue(position)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Closing has the same origin-return semantics as the visible action."""
        event.ignore()
        self.return_requested.emit()
