"""Read-only compact renderer for Event and Entity authoring context."""

from __future__ import annotations

from html import escape

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QResizeEvent, QTextOption
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
)
from src.core.entity_context_mode import ENTITY_CONTEXT_LABELS, EntityContextMode
from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.context_fact_section import ContextFactSection, FactSection
from src.gui.widgets.entity_context_mode_selector import EntityContextModeSelector


class AuthoringContextWidget(QWidget):
    """Render a compact Event context with deterministic overflow."""

    navigate_requested = Signal(str)
    map_requested = Signal(str)
    attachment_requested = Signal(str)
    connections_more_requested = Signal()

    def __init__(
        self, parent: QWidget | None = None, *, object_label: str = "Event"
    ) -> None:
        """Initialize the read-only context surface."""
        super().__init__(parent)
        self._context_scroll = 0
        self._embedded = False
        self._context_id: str | None = None
        self._object_label = object_label
        self._browse_enabled = False
        self._connection_rows: list[ContextRelation] = []
        self._entity_context: EntityAuthoringContext | None = None
        self._description_changes: tuple[ContextAttribute, ...] = ()
        self._description_omitted = 0
        self.sections: dict[str, ContextFactSection] = {}
        self._expanded_sections: set[str] = set()
        layout = QVBoxLayout(self)
        StyleHelper.apply_compact_spacing(layout)

        self.mode_selector = EntityContextModeSelector(self)
        self.mode_selector.setVisible(object_label == "Entity")
        layout.addWidget(self.mode_selector)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.viewport().installEventFilter(self)
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

        self.more_button = declare_inspection(
            QToolButton(),
            "src-gui-widgets-authoring-context-widget-authoringcontextwidget-init-self-more-button|authoring.tags|help-inspect-src-gui-widgets-authoring-context-widget-authoringcontextwidget-init-self-more-button",
        )
        self.more_button.setText("Expand all")
        self.more_button.setCheckable(True)
        self.more_button.setToolTip("Expand every section in the loaded context")
        self.more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_button.toggled.connect(self._toggle_more)
        self.more_button.hide()
        content_layout.addWidget(self.more_button)

        self.sections_host = QWidget(self.scroll_content)
        self.sections_layout = QVBoxLayout(self.sections_host)
        StyleHelper.apply_compact_spacing(self.sections_layout)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.sections_host)
        self.connection_controls = QWidget(self.sections_host)
        connection_layout = QVBoxLayout(self.connection_controls)
        StyleHelper.apply_compact_spacing(connection_layout)
        connection_layout.setContentsMargins(0, 0, 0, 0)
        self.connection_status = QLabel(self.connection_controls)
        self.connection_status.setWordWrap(True)
        self.connection_status.hide()
        connection_layout.addWidget(self.connection_status)
        self.load_connections = declare_inspection(
            QToolButton(self.connection_controls),
            "context-load-connections|authoring.tags|help-context-load-connections",
        )
        self.load_connections.setText("Load more connections")
        self.load_connections.setAccessibleName("Load more saved direct connections")
        self.load_connections.clicked.connect(self.connections_more_requested)
        self.load_connections.hide()
        connection_layout.addWidget(self.load_connections)
        self.connection_controls.hide()
        content_layout.addStretch()

        theme_manager = ThemeManager()
        theme_manager.theme_changed.connect(self._apply_theme)
        self._apply_theme(theme_manager.get_theme())

    def set_embedded(self, embedded: bool) -> None:
        """Let Overview own scrolling while preserving the same renderer."""
        if embedded == self._embedded:
            return
        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)
        if embedded:
            self.scroll_area.takeWidget()
            layout.removeWidget(self.scroll_area)
            self.scroll_area.hide()
            layout.addWidget(self.scroll_content)
            self.scroll_content.show()
        else:
            layout.removeWidget(self.scroll_content)
            self.scroll_area.setWidget(self.scroll_content)
            layout.addWidget(self.scroll_area)
            self.scroll_area.show()
        self._embedded = embedded
        self._fit_visible_browsers()

    def _make_browser(self) -> QTextBrowser:
        browser = QTextBrowser(self)
        browser.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        browser.setOpenLinks(False)
        browser.setOpenExternalLinks(False)
        browser.setFrameShape(QTextBrowser.Shape.NoFrame)
        browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        browser.anchorClicked.connect(self._on_anchor_clicked)
        return browser

    @Slot(dict)
    def _apply_theme(self, theme: dict) -> None:
        """Apply the active palette to controls and rich-text links."""
        surface = theme["surface"]
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ border: none; background-color: {surface}; }}"
        )
        self.scroll_area.viewport().setStyleSheet(f"background-color: {surface};")
        self.scroll_content.setStyleSheet(f"background-color: {surface};")
        self.status_label.setStyleSheet(
            f"color: {theme['text_dim']}; background: transparent;"
        )
        self.more_button.setStyleSheet(StyleHelper.get_flat_tool_button_style())
        self.load_connections.setStyleSheet(StyleHelper.get_flat_tool_button_style())
        self.connection_status.setStyleSheet(f"color: {theme['supporting_caption']};")
        browser_style = (
            f"QTextBrowser {{ background-color: {surface}; border: none; "
            f"color: {theme['text_main']}; }}"
        )
        document_style = (
            f"body {{ color: {theme['text_main']}; }} "
            "h3 { margin: 2px 0 10px 0; } "
            "p { margin: 5px 0; } p.fact { margin: 0 0 12px 0; } "
            f".detail {{ color: {theme['supporting_caption']}; }} "
            f"a {{ color: {theme['link_neutral']}; "
            "text-decoration: underline; } "
            f"a.entity {{ color: {theme['link_entity']}; text-decoration: underline; }} "
            f"a.event {{ color: {theme['link_event']}; text-decoration: underline; }} "
            "a:hover { text-decoration: underline; }"
        )
        for section in self.sections.values():
            section.apply_theme(theme)
        for browser in self._browsers():
            browser.setStyleSheet(browser_style)
            browser.document().setDefaultStyleSheet(document_style)
        for section in self.sections.values():
            self._render_section(section)
        QTimer.singleShot(0, self._fit_visible_browsers)

    def set_loading(self) -> None:
        """Show a non-blocking loading state."""
        if not self.primary_view.isHidden():
            self._context_scroll = self.scroll_area.verticalScrollBar().value()
        self.status_label.setText(f"Loading {self._object_label} context…")
        self.status_label.show()
        self.primary_view.hide()
        self.more_button.hide()
        self.sections_host.hide()

    def clear_context(self) -> None:
        """Reset the surface when no Event is selected."""
        self._context_id = None
        self._entity_context = None
        self._connection_rows = []
        self._description_changes = ()
        self._description_omitted = 0
        self.connection_status.hide()
        self.load_connections.hide()
        self.connection_controls.hide()
        self._expanded_sections.clear()
        self.more_button.setChecked(False)
        self.status_label.setText(self._empty_text())
        self.status_label.show()
        self.primary_view.clear()
        self.primary_view.hide()
        self.more_button.hide()
        self.sections_host.hide()

    def set_unavailable(self) -> None:
        """Show a concise lookup-failure state."""
        self.status_label.setText(
            f"{self._object_label} context is currently unavailable."
        )
        self.status_label.show()
        self.primary_view.hide()
        self.more_button.hide()
        self.sections_host.hide()

    def set_context(
        self, context: EventAuthoringContext, *, date_label: str = ""
    ) -> None:
        """Render one complete serialized Event context snapshot."""
        primary, more = self._render(context, date_label)
        self._present_context(context.event_id, primary, more)

    def set_entity_context(self, context: EntityAuthoringContext) -> None:
        """Render one complete serialized Entity context snapshot."""
        if context.entity_id != self._context_id:
            self._connection_rows = []
        self._entity_context = context
        primary, more = self._render_entity(context)
        self._present_context(context.entity_id, primary, more)

    def enable_connection_browsing(self) -> None:
        """Replace bounded direct-link sections with independently loaded rows."""
        self._browse_enabled = True

    def set_description_changes(self, snapshot: dict) -> None:
        """Accept description-only display facts, separate from the AI snapshot."""
        self._description_changes = tuple(
            ContextAttribute.from_dict(item) for item in snapshot.get("rows", [])
        )
        self._description_omitted = int(snapshot.get("omitted", 0))

    def set_connection_page(
        self,
        rows: list[dict],
        status: str,
        can_load: bool,
        *,
        retry: bool = False,
        reveal: bool = False,
        entity_id: str | None = None,
        loading: bool = False,
    ) -> None:
        """Render already-qualified rows without navigation or generation actions."""
        self._connection_rows = [ContextRelation.from_dict(item) for item in rows]
        self.connection_status.setText(status)
        self.connection_controls.setVisible(self._browse_enabled)
        self.connection_status.setVisible(self._browse_enabled)
        self.load_connections.setText(
            "Loading connections…"
            if loading
            else "Retry connections"
            if retry
            else "Load more connections"
        )
        self.load_connections.setAccessibleName(self.load_connections.text())
        self.load_connections.setToolTip(
            "A page is loading; repeated requests are ignored."
            if loading
            else "Load another page of saved direct connections."
            if can_load
            else "This action is unavailable while refreshing or after the scan finishes."
        )
        self.load_connections.setEnabled(can_load or loading)
        self.load_connections.setVisible(self._browse_enabled)
        if self._entity_context is None or (
            entity_id is not None and self._entity_context.entity_id != entity_id
        ):
            return
        self._context_scroll = self.scroll_area.verticalScrollBar().value()
        if reveal:
            self._expanded_sections.update(
                (
                    "Saved direct connections",
                    "Recorded state changes · Saved direct connections",
                )
            )
        primary, sections = self._render_entity(self._entity_context)
        self._present_context(self._entity_context.entity_id, primary, sections)

    def _present_context(
        self, item_id: str, heading: str, sections: list[FactSection]
    ) -> None:
        """Refresh rows while retaining same-object disclosure and scroll."""
        same_item = self._context_id == item_id
        expanded = same_item and self.more_button.isChecked()
        if not same_item:
            self._context_scroll = 0
            self._expanded_sections.clear()
        previous = dict(self.sections) if same_item else {}
        self.sections_layout.removeWidget(self.connection_controls)
        for name, section in self.sections.items():
            self.sections_layout.removeWidget(section)
            if name not in previous:
                section.hide()
                section.deleteLater()
        self.sections.clear()
        self._context_id = item_id
        self.status_label.hide()
        self.primary_view.setHtml(heading)
        self.primary_view.show()
        for data in sections:
            existing = previous.pop(data.title, None)
            if existing is None:
                section = ContextFactSection(data, self._make_browser(), self)
                section.expansion_changed.connect(self._section_changed)
            else:
                section = existing
                section.set_section(data)
            self.sections[data.title] = section
            self.sections_layout.addWidget(section)
            state_title = "Recorded state changes · Saved direct connections"
            if self._browse_enabled and (
                data.title == state_title
                or (
                    data.title == "Saved direct connections"
                    and not any(item.title == state_title for item in sections)
                )
            ):
                self.sections_layout.addWidget(self.connection_controls)
            section.disclosure.blockSignals(True)
            section.disclosure.setChecked(
                expanded or data.title in self._expanded_sections
            )
            section.disclosure.blockSignals(False)
            section.update_label()
        for section in previous.values():
            section.hide()
            section.deleteLater()
        self.sections_host.show()
        self.more_button.blockSignals(True)
        self.more_button.setChecked(expanded)
        self.more_button.blockSignals(False)
        self.more_button.setText("Collapse all" if expanded else "Expand all")
        self.more_button.setVisible(
            any(
                len(section.rows) > ContextFactSection.PREVIEW_ROWS
                for section in sections
            )
        )
        self._apply_theme(ThemeManager().get_theme())
        self._fit_visible_browsers()
        QTimer.singleShot(0, self._restore_context_scroll)

    def _browsers(self) -> list[QTextBrowser]:
        return [self.primary_view] + [s.browser for s in self.sections.values()]

    def _render_section(self, section: ContextFactSection) -> None:
        section.browser.setHtml(
            "".join(f'<p class="fact">{row}</p>' for row in section.visible_rows())
        )
        self._fit_browser_height(section.browser)

    @Slot()
    def _section_changed(self) -> None:
        self._expanded_sections = {
            name
            for name, section in self.sections.items()
            if section.disclosure.isChecked()
        }
        for section in self.sections.values():
            self._render_section(section)
        expandable = [
            s for s in self.sections.values() if len(s.section.rows) > s.PREVIEW_ROWS
        ]
        expanded = bool(expandable) and all(
            s.disclosure.isChecked() for s in expandable
        )
        self.more_button.blockSignals(True)
        self.more_button.setChecked(expanded)
        self.more_button.setText("Collapse all" if expanded else "Expand all")
        self.more_button.blockSignals(False)
        QTimer.singleShot(0, self._fit_visible_browsers)

    def _restore_context_scroll(self) -> None:
        if shiboken6.isValid(self) and shiboken6.isValid(self.scroll_area):
            self.scroll_area.verticalScrollBar().setValue(self._context_scroll)

    def _empty_text(self) -> str:
        return f"Select an {self._object_label} to view its context."

    @Slot(bool)
    def _toggle_more(self, checked: bool) -> None:
        """Expand or return every loaded section to its three-row preview."""
        for section in self.sections.values():
            section.disclosure.blockSignals(True)
            section.disclosure.setChecked(checked)
            section.disclosure.blockSignals(False)
            section.update_label()
        self._section_changed()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Refit after a scrollbar changes the available content width."""
        if (
            watched is self.scroll_area.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            QTimer.singleShot(0, self._fit_visible_browsers)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Reflow rich text to the available inspector width."""
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit_visible_browsers)

    def _fit_visible_browsers(self) -> None:
        for browser in self._browsers():
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
    ) -> tuple[str, list[FactSection]]:
        display_date = date_label or format(context.context_date, ".12g")
        sections: list[FactSection] = []
        self._append_section(
            sections,
            "Earlier Events",
            [self._event_link(item) for item in reversed(context.previous_events)],
        )
        self._append_section(
            sections,
            "Concurrent Events",
            [self._event_link(item) for item in context.concurrent_events],
        )
        self._append_section(
            sections,
            "Later Events",
            [self._event_link(item) for item in context.next_events],
        )
        self._append_section(
            sections,
            "People & places",
            [
                self._item_link(item)
                for item in (*context.participants, *context.locations)
            ],
        )
        self._append_section(
            sections,
            "At this time",
            [
                self._relation_html(item)
                for item in (*context.direct_relations, *context.neighborhood_relations)
            ],
        )
        self._append_section(
            sections, "Mentioned", [self._item_link(item) for item in context.mentions]
        )
        spatial_rows: list[str] = []
        for spatial in context.spatial:
            lines = spatial.text.splitlines()
            if lines and lines[0].strip() == "[Spatial Context]":
                lines = lines[1:]
            spatial_rows.extend(
                [
                    self._item_link(spatial.anchor)
                    + "<br>"
                    + "<br>".join(escape(line) for line in lines)
                ],
            )
        self._append_section(sections, "Spatial context", spatial_rows)
        self._append_limits(sections, context.omitted_counts)
        heading = f"<h3>Context at {escape(display_date)}</h3>"
        if not sections:
            heading += "<p>No related persisted facts at this date.</p>"
        return heading, sections

    def _render_entity(
        self, context: EntityAuthoringContext
    ) -> tuple[str, list[FactSection]]:
        label = ENTITY_CONTEXT_LABELS[EntityContextMode(context.mode)]
        heading = "Known Entity context" if context.mode == "all_history" else label
        title = f"<h3>{escape(heading)}</h3>"
        if context.context_date is not None:
            title += f"<p>{escape(context.date_label)} · Saved facts</p>"
        sections: list[FactSection] = []
        if context.effective_description is not None:
            self._append_section(
                sections,
                "Resolved description",
                [self._attribute_html(context.effective_description)],
            )
        self._append_section(sections, "Tags", [escape(i.name) for i in context.tags])
        relations = list(
            self._connection_rows if self._browse_enabled else context.direct_relations
        )
        if context.mode == "at_playhead" and not self._browse_enabled:
            relations.extend(context.temporal_history)
        self._append_relationships(
            sections,
            "Saved direct connections" if self._browse_enabled else "Relations",
            relations,
        )
        if self._browse_enabled and not relations:
            sections.append(FactSection("Saved direct connections", ()))
        if context.mode == "at_playhead" and not relations and not self._browse_enabled:
            title += (
                "<p>No authored current relationships at this date. "
                "Choose a history mode to inspect other dated relationships.</p>"
            )
        self._append_section(
            sections,
            "Event appearances",
            [
                self._event_link(item.event)
                + '<br><span class="detail">Role: '
                + escape(", ".join(item.roles))
                + "</span>"
                for item in reversed(context.event_appearances)
            ],
        )
        self._append_section(
            sections,
            "Maps",
            [self._map_appearance_html(item) for item in context.map_appearances],
        )
        self._append_section(
            sections,
            "Explicit references",
            []
            if self._browse_enabled
            else [self._relation_html(item) for item in context.linked_references],
        )
        self._append_section(
            sections,
            "Possible description changes — not established",
            [self._attribute_html(item) for item in self._description_changes],
        )
        self._append_section(
            sections,
            "Timing notices",
            [escape(item) for item in context.temporal_notices],
        )
        if context.mode != "at_playhead" and not self._browse_enabled:
            self._append_relationships(
                sections, "Temporal history", list(context.temporal_history)
            )
        self._append_section(
            sections,
            "Mentioned in Events",
            [self._event_link(item) for item in context.mentions],
        )
        self._append_section(
            sections,
            "Appears with in Events",
            [
                f"{self._item_link(item.item)}<br><span class='detail'>"
                f"{item.event_count} shared Event(s): "
                + ", ".join(self._event_link(event) for event in item.events)
                + "</span>"
                for item in context.co_appearances
            ],
            "Shared participation; this does not establish a direct relationship.",
        )
        self._append_section(
            sections,
            "Attachment captions",
            [
                f'<a href="kraken-attachment://{escape(item.id)}">'
                f"{escape(item.caption)}</a>"
                for item in context.attachments
            ],
        )
        self._append_section(
            sections,
            "Shares tags",
            [
                self._item_link(item.item)
                + '<br><span class="detail">Tags: '
                + escape(", ".join(item.evidence))
                + "</span>"
                for item in context.shared_tags
            ],
            "Matching tags; this does not establish a direct relationship.",
        )
        self._append_section(
            sections,
            "Also placed on maps",
            [
                self._item_link(item.item)
                + '<br><span class="detail">Maps: '
                + escape(", ".join(item.evidence))
                + "</span>"
                for item in context.shared_maps
            ],
            "Shared maps; placements are not necessarily contemporaneous.",
        )
        self._append_relationships(
            sections, "Surrounding relations", list(context.neighborhood_relations)
        )
        excluded_notices = {"attributes", "attribute_details", "possible_changes"}
        if self._browse_enabled:
            excluded_notices.update(
                {"direct_relations", "temporal_history", "linked_references"}
            )
        omissions = tuple(
            (name, count)
            for name, count in context.omitted_counts
            if name not in excluded_notices
        )
        if self._description_omitted:
            omissions += (("possible_description_changes", self._description_omitted),)
        self._append_limits(sections, omissions)
        if not sections:
            title += "<p>No related persisted facts.</p>"
        return title, sections

    def _append_relationships(
        self,
        sections: list[FactSection],
        title: str,
        relations: list[ContextRelation],
    ) -> None:
        self._append_section(
            sections,
            title,
            [
                self._relation_html(item, include_window=True)
                for item in relations
                if item.rel_type != "changes_state"
            ],
        )
        self._append_section(
            sections,
            f"Recorded state changes · {title}",
            [
                self._item_link(item.source)
                + " → "
                + f"<b>{escape(item.rel_type)}</b> → "
                + self._item_link(item.target)
                + self._relation_details(item, include_window=True)
                for item in relations
                if item.rel_type == "changes_state"
            ],
            "Saved state-change records; inspect the source Event for its changes.",
        )

    @staticmethod
    def _append_section(
        target: list[FactSection], title: str, items: list[str], hint: str = ""
    ) -> None:
        if items:
            target.append(FactSection(title, tuple(items), hint))

    def _append_limits(
        self, sections: list[FactSection], omitted: tuple[tuple[str, int], ...]
    ) -> None:
        self._append_section(
            sections,
            "Not included in this snapshot",
            [
                f"{count} additional {escape(name.replace('_', ' '))} omitted"
                for name, count in omitted
            ],
            "Expand all reveals loaded entries only. Omitted entries remain omitted.",
        )

    @staticmethod
    def _item_link(item: ContextItem) -> str:
        return (
            f'<a class="{escape(item.object_type)}" title="{escape(item.object_type.title())}: {escape(item.name)}" href="kraken://{escape(item.id)}">'
            f"{escape(item.name)}</a>"
        )

    def _event_link(self, event: ContextEvent) -> str:
        text = self._item_link(ContextItem(event.id, "event", event.name))
        if event.temporal_label:
            text += (
                '<br><span class="detail">' + escape(event.temporal_label) + "</span>"
            )
        return text

    def _relation_html(
        self, relation: ContextRelation, *, include_window: bool = False
    ) -> str:
        result = (
            f"{self._item_link(relation.source)} → "
            f"<b>{escape(relation.rel_type)}</b> → {self._item_link(relation.target)}"
        )
        if (
            relation.source.object_type == "event"
            or relation.target.object_type == "event"
        ):
            result += '<br><span class="detail">Saved link; does not by itself establish Event occurrence.</span>'
        return result + self._relation_details(relation, include_window=include_window)

    def _relation_details(
        self, relation: ContextRelation, *, include_window: bool
    ) -> str:
        result = ""
        if relation.temporal_summary:
            result += f"{escape(relation.temporal_summary)}"
            evidence = relation.temporal_evidence or {}
            for event in evidence.get("events", []):
                result += "<br>Source: " + self._item_link(
                    ContextItem(event["id"], "event", event["name"])
                )
        if (
            include_window
            and not relation.temporal_summary
            and relation.temporal_kind != "persistent"
        ):
            start = (
                "not supplied"
                if relation.valid_from is None
                else format(relation.valid_from, ".12g")
            )
            end = (
                "not supplied"
                if relation.valid_to is None
                else format(relation.valid_to, ".12g")
            )
            result += f"Timing: {escape(relation.temporal_kind)}; start: {start}; end: {end} (lore days)"
        return f'<br><span class="detail">{result}</span>' if result else ""

    @staticmethod
    def _attribute_html(attribute: ContextAttribute) -> str:
        text = f"<b>{escape(attribute.name)}:</b> {escape(str(attribute.value))}"
        source = attribute.source
        if source is not None:
            if source.get("event_id"):
                text += (
                    '<br><span class="detail">Source: </span>'
                    + AuthoringContextWidget._item_link(
                        ContextItem(
                            str(source["event_id"]),
                            "event",
                            str(source.get("event_name", "Event")),
                        )
                    )
                )
            else:
                text += '<br><span class="detail">Undated baseline</span>'
        if attribute.temporal_status != "definite":
            text += f" · {escape(attribute.temporal_status)}"
        return text

    def _map_appearance_html(self, appearance: ContextMapAppearance) -> str:
        feature = appearance.feature_type.strip().casefold()
        map_link = (
            f'<a href="kraken-map://{escape(appearance.map_id)}">'
            f"{escape(appearance.map_name)}</a>"
        )
        if feature in {"", "point"}:
            result = f"Placed on {map_link}"
        else:
            result = f"Placed on {map_link} as a {escape(appearance.feature_type)}"
        if appearance.marker_label:
            result += f" — {escape(appearance.marker_label)}"
        if appearance.parent_maps:
            result += " within " + " › ".join(
                f'<a href="kraken-map://{escape(parent.id)}">{escape(parent.name)}</a>'
                for parent in appearance.parent_maps
            )
        return result

    @staticmethod
    def _fit_browser_height(browser: QTextBrowser) -> None:
        """Fit all rich text; the surrounding context surface owns scrolling."""
        browser.document().setTextWidth(max(1, browser.viewport().width()))
        document_height = int(browser.document().size().height()) + 12
        browser.setFixedHeight(max(32, document_height))
