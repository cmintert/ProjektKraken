"""Read-only compact renderer for Event and Entity authoring context."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.authoring_context import (
    ContextAttribute,
    ContextEvent,
    ContextItem,
    ContextMapAppearance,
    ContextRelation,
    EntityAuthoringContext,
    EventAuthoringContext,
    SpatialAuthoringContext,
)
from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper

_PRIMARY_RELATION_LIMIT = 6
_PRIMARY_ATTRIBUTE_LIMIT = 6
_PRIMARY_EVENT_LIMIT = 4


class AuthoringContextWidget(QWidget):
    """Render a compact Event context with deterministic overflow."""

    navigate_requested = Signal(str)
    map_requested = Signal(str)
    attachment_requested = Signal(str)

    def __init__(
        self, parent: QWidget | None = None, *, object_label: str = "Event"
    ) -> None:
        """Initialize the read-only context surface."""
        super().__init__(parent)
        self._object_label = object_label
        layout = QVBoxLayout(self)
        StyleHelper.apply_compact_spacing(layout)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_content = QWidget()
        content_layout = QVBoxLayout(self.scroll_content)
        StyleHelper.apply_compact_spacing(content_layout)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

        self.status_label = QLabel(self._empty_text())
        self.status_label.setWordWrap(True)
        content_layout.addWidget(self.status_label)

        self.primary_view = self._make_browser()
        self.primary_view.hide()
        content_layout.addWidget(self.primary_view)

        self.more_button = QToolButton()
        self.more_button.setText("More…")
        self.more_button.setCheckable(True)
        self.more_button.setToolTip("Show additional bounded context")
        self.more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_button.toggled.connect(self._toggle_more)
        self.more_button.hide()
        content_layout.addWidget(self.more_button)

        self.more_view = self._make_browser()
        self.more_view.hide()
        content_layout.addWidget(self.more_view)
        content_layout.addStretch()

        theme_manager = ThemeManager()
        theme_manager.theme_changed.connect(self._apply_theme)
        self._apply_theme(theme_manager.get_theme())

    def _make_browser(self) -> QTextBrowser:
        browser = QTextBrowser(self)
        browser.setOpenLinks(False)
        browser.setOpenExternalLinks(False)
        browser.setFrameShape(QTextBrowser.Shape.NoFrame)
        browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        browser.anchorClicked.connect(self._on_anchor_clicked)
        return browser

    @Slot(dict)
    def _apply_theme(self, theme: dict) -> None:
        """Apply the active palette to controls and rich-text links."""
        surface = theme["surface"]
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: none; "
            f"background-color: {surface}; }}"
        )
        self.scroll_area.viewport().setStyleSheet(
            f"background-color: {surface};"
        )
        self.scroll_content.setStyleSheet(f"background-color: {surface};")
        self.status_label.setStyleSheet(
            f"color: {theme['text_dim']}; background: transparent;"
        )
        self.more_button.setStyleSheet(StyleHelper.get_flat_tool_button_style())
        browser_style = (
            f"QTextBrowser {{ background-color: {surface}; border: none; "
            f"color: {theme['text_main']}; }}"
        )
        document_style = (
            f"body {{ color: {theme['text_main']}; }} "
            "h3 { margin: 2px 0 10px 0; } "
            "p { margin: 5px 0; } "
            f"a {{ color: {theme['accent_secondary']}; "
            "text-decoration: none; }} "
            f"a:hover {{ color: {theme['primary']}; text-decoration: underline; }}"
        )
        for browser in (self.primary_view, self.more_view):
            browser.setStyleSheet(browser_style)
            browser.document().setDefaultStyleSheet(document_style)

    def set_loading(self) -> None:
        """Show a non-blocking loading state."""
        self.status_label.setText(f"Loading {self._object_label} context…")
        self.status_label.show()
        self.primary_view.hide()
        self.more_button.hide()
        self.more_view.hide()

    def clear_context(self) -> None:
        """Reset the surface when no Event is selected."""
        self.status_label.setText(self._empty_text())
        self.status_label.show()
        self.primary_view.clear()
        self.primary_view.hide()
        self.more_button.hide()
        self.more_view.clear()
        self.more_view.hide()

    def set_unavailable(self) -> None:
        """Show a concise lookup-failure state."""
        self.status_label.setText(
            f"{self._object_label} context is currently unavailable."
        )
        self.status_label.show()
        self.primary_view.hide()
        self.more_button.hide()
        self.more_view.hide()

    def set_context(
        self, context: EventAuthoringContext, *, date_label: str = ""
    ) -> None:
        """Render one complete serialized Event context snapshot."""
        primary, more = self._render(context, date_label)
        self.status_label.hide()
        self.primary_view.setHtml(primary)
        self._fit_browser_height(self.primary_view)
        self.primary_view.show()
        self.more_view.setHtml(more)
        self._fit_browser_height(self.more_view)
        self.more_button.setVisible(bool(more))
        self.more_button.setChecked(False)
        self.more_view.hide()

    def set_entity_context(self, context: EntityAuthoringContext) -> None:
        """Render one complete serialized Entity context snapshot."""
        primary, more = self._render_entity(context)
        self.status_label.hide()
        self.primary_view.setHtml(primary)
        self._fit_browser_height(self.primary_view)
        self.primary_view.show()
        self.more_view.setHtml(more)
        self._fit_browser_height(self.more_view)
        self.more_button.setVisible(bool(more))
        self.more_button.setChecked(False)
        self.more_view.hide()

    def _empty_text(self) -> str:
        return f"Select an {self._object_label} to view its context."

    @Slot(bool)
    def _toggle_more(self, checked: bool) -> None:
        self.more_button.setText("Less" if checked else "More…")
        self.more_view.setVisible(checked)
        if checked:
            QTimer.singleShot(0, lambda: self._fit_browser_height(self.more_view))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Reflow rich text to the available inspector width."""
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit_visible_browsers)

    def _fit_visible_browsers(self) -> None:
        for browser in (self.primary_view, self.more_view):
            if browser.isVisible():
                self._fit_browser_height(browser)

    @Slot(QUrl)
    def _on_anchor_clicked(self, url: QUrl) -> None:
        if url.scheme() == "kraken" and url.host():
            self.navigate_requested.emit(url.host())
        elif url.scheme() == "kraken-map" and url.host():
            self.map_requested.emit(url.host())
        elif url.scheme() == "kraken-attachment" and url.host():
            self.attachment_requested.emit(url.host())

    def _render(
        self, context: EventAuthoringContext, date_label: str
    ) -> tuple[str, str]:
        display_date = date_label or format(context.context_date, ".12g")
        primary: list[str] = [f"<h3>Context at {escape(display_date)}</h3>"]
        more: list[str] = []

        timeline_primary: list[str] = []
        if context.previous_events:
            timeline_primary.append(
                "← " + self._event_link(context.previous_events[-1])
            )
        timeline_primary.extend(
            "• " + self._event_link(item) for item in context.concurrent_events
        )
        if context.next_events:
            timeline_primary.append("→ " + self._event_link(context.next_events[0]))
        self._append_section(primary, "Timeline", timeline_primary)

        people_places = [self._item_link(item) for item in context.participants]
        people_places.extend(self._item_link(item) for item in context.locations)
        self._append_section(primary, "People &amp; places", people_places)

        relations = list(context.direct_relations) + list(
            context.neighborhood_relations
        )
        self._append_section(
            primary,
            "At this time",
            [self._relation_html(item) for item in relations[:_PRIMARY_RELATION_LIMIT]],
        )
        if context.spatial:
            self._append_spatial(primary, context.spatial[0])
        if len(primary) == 1:
            primary.append("<p>No related persisted facts at this date.</p>")

        extra_timeline = [
            "← " + self._event_link(item) for item in context.previous_events[:-1]
        ]
        extra_timeline.extend(
            "→ " + self._event_link(item) for item in context.next_events[1:]
        )
        self._append_section(more, "Additional timeline", extra_timeline)
        self._append_section(
            more,
            "Additional relations",
            [self._relation_html(item) for item in relations[_PRIMARY_RELATION_LIMIT:]],
        )
        self._append_section(
            more,
            "Mentioned",
            [self._item_link(item) for item in context.mentions],
        )
        for spatial in context.spatial[1:]:
            self._append_spatial(more, spatial)
        if context.omitted_counts:
            notices = [
                f"{count} additional {escape(section.replace('_', ' '))} omitted"
                for section, count in context.omitted_counts
            ]
            self._append_section(more, "Limits", notices)
        return "".join(primary), "".join(more)

    def _render_entity(
        self, context: EntityAuthoringContext
    ) -> tuple[str, str]:
        primary: list[str] = ["<h3>Known Entity context</h3>"]
        more: list[str] = []
        self._append_section(
            primary,
            "Attributes",
            [
                self._attribute_html(item)
                for item in context.attributes[:_PRIMARY_ATTRIBUTE_LIMIT]
            ],
        )
        self._append_section(
            primary,
            "Tags",
            [escape(item.name) for item in context.tags],
        )
        relations = list(context.direct_relations)
        self._append_section(
            primary,
            "Relations",
            [self._relation_html(item) for item in relations[:_PRIMARY_RELATION_LIMIT]],
        )
        recent_events = list(context.event_appearances[-_PRIMARY_EVENT_LIMIT:])
        self._append_section(
            primary,
            "Event appearances",
            [
                f"{self._event_link(item.event)} — "
                + escape(", ".join(item.roles))
                for item in recent_events
            ],
        )
        self._append_section(
            primary,
            "Maps",
            [
                self._map_appearance_html(item)
                for item in context.map_appearances
            ],
        )
        self._append_section(
            primary,
            "Explicit references",
            [self._relation_html(item) for item in context.linked_references[:6]],
        )
        if len(primary) == 1:
            primary.append("<p>No related persisted facts.</p>")

        self._append_section(
            more,
            "Additional attributes",
            [
                self._attribute_html(item)
                for item in context.attributes[_PRIMARY_ATTRIBUTE_LIMIT:]
            ],
        )
        self._append_section(
            more,
            "Additional relations",
            [
                self._relation_html(item)
                for item in relations[_PRIMARY_RELATION_LIMIT:]
            ],
        )
        prior_events = (
            context.event_appearances[: -len(recent_events)]
            if recent_events
            else context.event_appearances
        )
        self._append_section(
            more,
            "Earlier Event appearances",
            [
                f"{self._event_link(item.event)} — "
                + escape(", ".join(item.roles))
                for item in prior_events
            ],
        )
        self._append_section(
            more,
            "Temporal history",
            [self._relation_html(item, include_window=True) for item in context.temporal_history],
        )
        self._append_section(
            more,
            "Mentioned in Events",
            [self._event_link(item) for item in context.mentions],
        )
        self._append_section(
            more,
            "Additional explicit references",
            [self._relation_html(item) for item in context.linked_references[6:]],
        )
        self._append_section(
            more,
            "Appears with in Events",
            [
                f"{self._item_link(item.item)} — {item.event_count} shared; "
                + ", ".join(self._event_link(event) for event in item.events)
                for item in context.co_appearances
            ],
        )
        self._append_section(
            more,
            "Attachment captions",
            [
                f'<a href="kraken-attachment://{escape(item.id)}">'
                f"{escape(item.caption)}</a>"
                for item in context.attachments
            ],
        )
        self._append_section(
            more,
            "Shares tags",
            [
                f"{self._item_link(item.item)} — "
                + escape(", ".join(item.evidence))
                for item in context.shared_tags
            ],
        )
        self._append_section(
            more,
            "Also placed on maps",
            [
                f"{self._item_link(item.item)} — "
                + escape(", ".join(item.evidence))
                for item in context.shared_maps
            ],
        )
        self._append_section(
            more,
            "Surrounding relations",
            [
                self._relation_html(item, include_window=True)
                for item in context.neighborhood_relations
            ],
        )
        if context.omitted_counts:
            self._append_section(
                more,
                "Limits",
                [
                    f"{count} additional {escape(section.replace('_', ' '))} omitted"
                    for section, count in context.omitted_counts
                ],
            )
        return "".join(primary), "".join(more)

    @staticmethod
    def _append_section(target: list[str], title: str, items: list[str]) -> None:
        if not items:
            return
        target.append(f"<p><b>{title}</b><br>{' · '.join(items)}</p>")

    def _append_spatial(
        self, target: list[str], spatial: SpatialAuthoringContext
    ) -> None:
        lines = spatial.text.splitlines()
        if lines and lines[0].strip() == "[Spatial Context]":
            lines = lines[1:]
        body = "<br>".join(escape(line) for line in lines)
        target.append(
            f"<p><b>Map · {self._item_link(spatial.anchor)}</b><br>{body}</p>"
        )

    @staticmethod
    def _item_link(item: ContextItem) -> str:
        return f'<a href="kraken://{escape(item.id)}">{escape(item.name)}</a>'

    def _event_link(self, event: ContextEvent) -> str:
        return self._item_link(ContextItem(event.id, "event", event.name))

    def _relation_html(
        self, relation: ContextRelation, *, include_window: bool = False
    ) -> str:
        result = (
            f"{self._item_link(relation.source)} → "
            f"{escape(relation.rel_type)} → {self._item_link(relation.target)}"
        )
        if include_window and relation.temporal_kind != "persistent":
            start = "?" if relation.valid_from is None else format(relation.valid_from, ".12g")
            end = "?" if relation.valid_to is None else format(relation.valid_to, ".12g")
            result += f" ({escape(relation.temporal_kind)}: {start}–{end})"
        return result

    @staticmethod
    def _attribute_html(attribute: ContextAttribute) -> str:
        return f"{escape(attribute.name)}: {escape(str(attribute.value))}"

    def _map_appearance_html(self, appearance: ContextMapAppearance) -> str:
        feature = appearance.feature_type.strip().casefold()
        map_link = (
            f'<a href="kraken-map://{escape(appearance.map_id)}">'
            f"{escape(appearance.map_name)}</a>"
        )
        if feature in {"", "point"}:
            result = f"Placed on {map_link}"
        else:
            result = (
                f"Placed on {map_link} as a "
                f"{escape(appearance.feature_type)}"
            )
        if appearance.marker_label:
            result += f" — {escape(appearance.marker_label)}"
        if appearance.parent_maps:
            result += " within " + " › ".join(
                f'<a href="kraken-map://{escape(parent.id)}">'
                f"{escape(parent.name)}</a>"
                for parent in appearance.parent_maps
            )
        return result

    @staticmethod
    def _fit_browser_height(browser: QTextBrowser) -> None:
        """Fit all rich text; the surrounding context surface owns scrolling."""
        browser.document().setTextWidth(max(1, browser.viewport().width()))
        browser.document().adjustSize()
        document_height = int(browser.document().size().height()) + 12
        browser.setFixedHeight(max(32, document_height))
