"""Read-only companion presentation; all navigation is emitted as intent."""

from __future__ import annotations

import html
from typing import Any

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QCloseEvent, QImage
from PySide6.QtWidgets import QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
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
            ("Refresh context", self.refresh_requested),
            ("Return to work", self.return_requested),
        ):
            button = QPushButton(label, row)
            button.setAccessibleName(label)
            button.clicked.connect(signal.emit)
            flow.addWidget(button)
            self.buttons[label] = button
        layout.addWidget(row)
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
        ThemeManager().theme_changed.connect(self.apply_theme)
        self.apply_theme()

    def set_history(self, back: bool, forward: bool) -> None:
        """Expose history availability without hiding navigation."""
        self.buttons["Back"].setEnabled(back)
        self.buttons["Forward"].setEnabled(forward)
        self.buttons["Back"].setToolTip("Previous Help page")
        self.buttons["Forward"].setToolTip("Next Help page")

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
