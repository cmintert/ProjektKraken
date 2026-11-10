"""Timeline Display Widget Module.

Provides a read-only widget that displays a chronological list of events affecting an
entity, with payload attributes shown inline.
"""

import re
import textwrap
from bisect import bisect_right
from html import escape
from typing import Any, Optional

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QTextBrowser, QToolTip, QVBoxLayout, QWidget

from src.core.events import Event
from src.core.temporal_display import TemporalDisplay, event_temporal_display
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.theme_connections import connect_theme


class TimelineDisplayWidget(QWidget):
    """Read-only widget displaying chronological events affecting an entity.

    Shows events sorted by date with their payload attributes, and highlights events at
    or before the current playhead time.
    """

    # Class-level calendar converter for date formatting
    _calendar_converter: Any = None
    event_clicked = Signal(str)
    association_requested = Signal(str, dict)

    @classmethod
    def set_calendar_converter(cls, converter: Any) -> None:
        """Set the calendar converter for date formatting."""
        cls._calendar_converter = converter

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the timeline display widget.

        Args:
            parent: Parent widget, if any.

        """
        super().__init__(parent)

        self._relations: list[dict[str, Any]] = []
        self._playhead_time: Optional[float] = None
        self._current_time: Optional[float] = None  # Story's "current time"
        self._description_map: dict[str, str] = {}  # anchor_id -> description
        self._event_id_map: dict[str, str] = {}  # anchor_id -> source event ID
        self._association_map: dict[str, list[dict[str, Any]]] = {}

        # Setup UI
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._living_status_label = QLabel()
        self._living_status_label.hide()
        layout.addWidget(self._living_status_label)

        self._text_display = declare_inspection(
            QTextBrowser(),
            "src-gui-widgets-timeline-display-widget-timelinedisplaywidget-init-self-text-display|timeline.viewing|help-inspect-src-gui-widgets-timeline-display-widget-timelinedisplaywidget-init-self-text-display",
        )
        self._text_display.setReadOnly(True)
        self._text_display.setOpenLinks(False)
        self._text_display.anchorClicked.connect(
            lambda url: self._follow_card_link(
                url.toString(), self._text_display.cursorRect().bottomLeft()
            )
        )
        self._text_display.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._text_display.customContextMenuRequested.connect(self._show_card_menu)
        self._text_display.setMinimumHeight(100)
        self._text_display.setMinimumHeight(100)
        # Allow widget to expand to fill available space
        # self._text_display.setMaximumHeight(200)
        layout.addWidget(self._text_display)

        # Setup hover tooltip detection
        self._text_display.viewport().setMouseTracking(True)
        self._text_display.viewport().installEventFilter(self)

        # Apply theme-aware styling to the QTextEdit
        self._apply_widget_style()

        # Connect to theme changes

        connect_theme(self, self._on_theme_changed)

    def set_relations(self, relations: list[dict[str, Any]]) -> None:
        """Set the relations to display in the timeline.

        Args:
            relations: List of relation dicts with source_event_name,
                      source_event_date, source_event_description,
                      and attributes (including payload).

        """
        cards: list[dict[str, Any]] = []
        by_event: dict[str, dict[str, Any]] = {}
        for relation in relations:
            event_id = relation.get("source_event_id")
            if event_id and event_id in by_event:
                by_event[event_id]["associations"].append(relation)
                continue
            card = {**relation, "associations": [relation]}
            cards.append(card)
            if event_id:
                by_event[event_id] = card
        self._relations = cards
        self._refresh_display()

    def set_playhead_time(self, time: float) -> None:
        """Set the current playhead time for highlighting.

        Args:
            time: The playhead time in lore_date units.

        """
        if self._playhead_time != time:
            self.set_living_status(None)
        self._playhead_time = time
        self._refresh_display()

    def set_living_status(self, status: dict[str, Any] | None) -> None:
        """Show the derived status at the viewed time when available."""
        value = status.get("value") if status else None
        labels = {"alive": "Alive", "dead": "Dead", "indeterminate": "Indeterminate"}
        self._living_status_label.setText(
            f"Living status at viewed time: {labels[value]}" if value in labels else ""
        )
        self._living_status_label.setVisible(value in labels)

    def set_current_time(self, time: Optional[float]) -> None:
        """Set the story's 'current time' for the NOW marker.

        Args:
            time: The current time in lore_date units, or None to hide.

        """
        self._current_time = time
        self._refresh_display()

    def get_display_text(self) -> str:
        """Get the current display text (for testing).

        Returns:
            HTML content currently displayed.

        """
        return self._text_display.toHtml()

    def _refresh_display(self) -> None:
        """Refresh the timeline display based on current relations."""
        # Clear description map for new display
        self._description_map = {}
        self._event_id_map = {}
        self._association_map = {}

        # Sort relations by date
        dated: list[tuple[float, TemporalDisplay, dict[str, Any]]] = []
        unresolved: list[tuple[None, TemporalDisplay, dict[str, Any]]] = []
        for relation in self._relations:
            timing = self._event_timing(relation)
            if timing.possible_start is None:
                unresolved.append((None, timing, relation))
            else:
                dated.append((timing.possible_start, timing, relation))
        dated.sort(key=lambda item: item[0])
        dates = [date for date, _, _ in dated]
        entries = [*dated, *unresolved]
        markers: dict[int, list[tuple[float, str]]] = {}
        for time, label, css_class in (
            (self._playhead_time, "Viewing", "viewed-marker"),
            (self._current_time, "World Time", "world-marker"),
        ):
            if time is not None:
                date_text = escape(self._format_date(time))
                marker = (
                    f"<div class='{css_class}'><span>{label}: {date_text}</span></div>"
                )
                markers.setdefault(bisect_right(dates, time), []).append((time, marker))

        # Build HTML content with theme-aware styling
        from src.gui.utils.style_helper import StyleHelper

        html_parts = []
        html_parts.append("<style>")
        html_parts.append(StyleHelper.get_timeline_display_css())
        html_parts.append("</style>")

        for i, (_, timing, rel) in enumerate(entries):
            for _, marker in sorted(markers.get(i, [])):
                html_parts.append(marker)
            event_name = rel.get("source_event_name") or "Event"

            # Extract description and build anchor ID
            anchor_id = rel.get("id") or f"card_{i}"
            self._association_map[anchor_id] = rel["associations"]
            event_id = rel.get("source_event_id") or rel.get("source_id")
            if event_id:
                self._event_id_map[anchor_id] = str(event_id)
            raw_desc = rel.get("source_event_description") or ""
            self._extract_and_map_description(anchor_id, raw_desc)

            # Format date using calendar converter if available
            date_html = escape(timing.caption)

            # Determine state: active (past/current) or future
            is_active = (
                self._playhead_time is not None
                and timing.possible_end is not None
                and timing.possible_end <= self._playhead_time
            )

            # Use CSS classes for styling instead of inline styles
            entry_class = "timeline-entry active" if is_active else "timeline-entry"

            html_parts.append(
                f"<table width='100%' cellpadding='8' cellspacing='0' "
                f"class='{entry_class}' style='margin: 4px 0;'>"
            )
            html_parts.append("<tr><td>")

            # Anchors support navigation and, when available, description tooltips.
            has_desc = anchor_id in self._description_map
            has_event = anchor_id in self._event_id_map
            self._wrap_card_with_anchor(html_parts, anchor_id, has_desc or has_event)

            # Lead with Event identity, then retain the complete timing caption.
            html_parts.append(
                f"<span class='event-name'>{escape(str(event_name))}</span><br>"
            )
            html_parts.append(f"<span class='event-date'>{date_html}</span>")
            self._append_associations(html_parts, rel["associations"])

            self._close_card_anchor(html_parts, anchor_id, has_desc or has_event)
            if has_event and any(
                self._is_authored_association(row) for row in rel["associations"]
            ):
                html_parts.append(
                    f"<br><a href='actions:{escape(anchor_id, quote=True)}'>Association actions</a>"
                )

            html_parts.append("</td></tr></table>")

        for _, marker in sorted(markers.get(len(entries), [])):
            html_parts.append(marker)
        if not entries:
            html_parts.append(
                "<p class='timeline-empty'>No timeline events for this entity.</p>"
            )

        scrollbar = self._text_display.verticalScrollBar()
        previous_scroll = scrollbar.value()
        self._text_display.setHtml("\n".join(html_parts))
        scrollbar.setValue(previous_scroll)

    def _format_date(self, time: float) -> str:
        """Format an event or time marker with the active world calendar."""
        converter = TimelineDisplayWidget._calendar_converter
        return converter.format_date(time) if converter else f"{time:.1f}"

    def _append_associations(
        self, html_parts: list[str], associations: list[dict[str, Any]]
    ) -> None:
        for relation in associations:
            rel_type = relation.get("rel_type")
            if rel_type:
                html_parts.append(
                    f" <span class='event-type'>({escape(str(rel_type))})</span>"
                )
            payload = relation.get("attributes", {}).get("payload", {})
            if self._payload_has_state_changes(payload):
                self._append_payload_v2(html_parts, payload)

    @staticmethod
    def _payload_has_state_changes(payload: object) -> bool:
        """Return whether a stored payload contains an effective state change."""
        if not isinstance(payload, dict):
            return False
        changed_attributes = payload.get("attributes")
        if isinstance(changed_attributes, dict) and changed_attributes:
            return True
        unset_attributes = payload.get("unset_attributes")
        if isinstance(unset_attributes, list) and unset_attributes:
            return True
        return "description" in payload and isinstance(payload["description"], str)

    @staticmethod
    def _append_payload_v2(html_parts: list[str], payload: dict[str, Any]) -> None:
        """Append readable Payload v2 mutations to a timeline card."""
        html_parts.append(
            "<br><span class='state-changes-heading'>State changes</span>"
        )
        changed_attributes = payload.get("attributes", {})
        if isinstance(changed_attributes, dict):
            for key, value in changed_attributes.items():
                display_val = "—" if value is None else str(value)
                html_parts.append(
                    "<br><span class='payload-key' style='margin-left: 16px;'>"
                    f"{escape(str(key))}:</span> "
                    f"<span class='payload-value'>{escape(display_val)}</span>"
                )

        unset_attributes = payload.get("unset_attributes", [])
        if isinstance(unset_attributes, list):
            for key in unset_attributes:
                html_parts.append(
                    "<br><span class='payload-key' style='margin-left: 16px;'>"
                    "Remove:</span> "
                    f"<span class='payload-value'>{escape(str(key))}</span>"
                )

        if "description" in payload:
            display_val = str(payload["description"])
            html_parts.append(
                "<br><span class='payload-key' style='margin-left: 16px;'>"
                "Description:</span> "
                f"<span class='payload-value'>{escape(display_val)}</span>"
            )

    def _extract_and_map_description(self, anchor_id: str, raw_desc: str) -> None:
        """Extract description text and add to description map.

        Strips HTML tags, wraps to 80 characters per line, and stores
        in _description_map if non-empty.

        Args:
            anchor_id: The anchor ID (relation ID) for the card.
            raw_desc: Raw description text, possibly containing HTML.

        """
        if raw_desc:
            plain_desc = re.sub(r"<[^>]+>", "", raw_desc).strip()
            if plain_desc:
                wrapped = "\n".join(textwrap.wrap(plain_desc, width=80))
                self._description_map[anchor_id] = wrapped

    def _wrap_card_with_anchor(
        self, html_parts: list[str], anchor_id: str, has_anchor: bool
    ) -> None:
        """Conditionally wrap card content for navigation or hover tooltip.

        Args:
            html_parts: HTML parts list to append opening anchor (if needed).
            anchor_id: The anchor ID (relation ID).
            has_anchor: Whether this card supports navigation or a tooltip.

        """
        if has_anchor:
            safe_anchor_id = escape(str(anchor_id), quote=True)
            html_parts.append(
                f"<a href='{safe_anchor_id}' style='text-decoration: none;'>"
            )

    def _close_card_anchor(
        self, html_parts: list[str], anchor_id: str, has_anchor: bool
    ) -> None:
        """Conditionally close a card's navigation or tooltip anchor.

        Args:
            html_parts: HTML parts list to append closing anchor (if needed).
            anchor_id: The anchor ID (relation ID).
            has_anchor: Whether this card supports navigation or a tooltip.

        """
        if has_anchor:
            html_parts.append("</a>")

    def _get_event_date(self, rel: dict[str, Any]) -> float | None:
        """Keep an explicitly unknown Event date separate from relation validity."""
        date = rel.get("source_event_date")
        if "source_event_date" not in rel:
            date = rel.get("attributes", {}).get("valid_from")
        return float(date) if date is not None else None

    def _event_timing(self, relation: dict[str, Any]) -> TemporalDisplay:
        date = self._get_event_date(relation)
        attributes = relation.get("source_event_attributes") or {}
        if attributes.get("_temporal_v2"):
            return event_temporal_display(
                Event(
                    name=relation.get("source_event_name") or "Event",
                    lore_date=date,
                    lore_duration=relation.get("source_event_duration"),
                    attributes=attributes,
                ),
                self._calendar_converter,
            )
        caption = "Date unknown" if date is None else self._format_date(date)
        return TemporalDisplay(date, date, caption=caption)

    def clear(self) -> None:
        """Clear the timeline display."""
        self._relations = []
        self._playhead_time = None
        self._description_map = {}
        self._event_id_map = {}
        self.set_living_status(None)
        self._text_display.clear()

    def _activate_anchor(self, anchor_id: str) -> bool:
        """Navigate to the event represented by an anchor, when available."""
        event_id = self._event_id_map.get(anchor_id)
        if not event_id:
            return False
        self.event_clicked.emit(event_id)
        return True

    def _show_card_menu(self, position: QPoint) -> None:
        anchor = self._text_display.anchorAt(position)
        self._open_card_menu(anchor.removeprefix("actions:"), position)

    @staticmethod
    def _is_authored_association(relation: dict) -> bool:
        return bool(relation.get("id")) and relation.get("rel_type") != "mentions"

    def _open_card_menu(self, anchor: str, position: QPoint) -> None:
        menu = self._text_display.createStandardContextMenu(position)
        if anchor in self._event_id_map:
            menu.addAction("Open event", lambda: self._activate_anchor(anchor))
        for relation in self._association_map.get(anchor, []):
            if not self._is_authored_association(relation):
                continue
            actions = menu.addMenu(str(relation.get("rel_type", "Association")))
            actions.addAction(
                "Change associated event…",
                lambda _checked=False, row=relation: self.association_requested.emit(
                    "replace", row
                ),
            )
            actions.addAction(
                "Remove association",
                lambda _checked=False, row=relation: self.association_requested.emit(
                    "unlink", row
                ),
            )
        menu.exec(self._text_display.viewport().mapToGlobal(position))
        menu.deleteLater()

    def _follow_card_link(self, anchor: str, position: QPoint) -> bool:
        if anchor.startswith("actions:"):
            self._open_card_menu(anchor.removeprefix("actions:"), position)
            return True
        return self._activate_anchor(anchor)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Handle card hover tooltips and event navigation clicks.

        Args:
            obj: The object that received the event.
            event: The event.

        Returns:
            bool: True if event was handled, False otherwise.

        """
        if (
            obj is self._text_display.viewport()
            and event.type() == QEvent.Type.MouseMove
            and isinstance(event, QMouseEvent)
        ):
            pos = event.position().toPoint()
            anchor = self._text_display.anchorAt(pos)
            if anchor and anchor in self._description_map:
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    self._description_map[anchor],
                    self._text_display.viewport(),
                )
            else:
                QToolTip.hideText()
        elif (
            obj is self._text_display.viewport()
            and event.type() == QEvent.Type.MouseButtonRelease
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            position = event.position().toPoint()
            anchor = self._text_display.anchorAt(position)
            if anchor and self._follow_card_link(anchor, position):
                return True
        return super().eventFilter(obj, event)

    def _apply_widget_style(self) -> None:
        """Apply theme-aware QSS to the QTextEdit container."""
        from src.gui.utils.style_helper import StyleHelper

        self._text_display.setStyleSheet(StyleHelper.get_timeline_textedit_style())

    def _on_theme_changed(self, theme: dict) -> None:
        """Handle theme changes by refreshing the display.

        Args:
            theme: The new theme data (unused, but required by signal).

        """
        self._apply_widget_style()
        self._refresh_display()
