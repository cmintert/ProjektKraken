"""Timeline Display Widget Module.

Provides a read-only widget that displays a chronological list of events affecting an
entity, with payload attributes shown inline.
"""

import re
import textwrap
from typing import Any, Optional

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QTextEdit, QToolTip, QVBoxLayout, QWidget


class TimelineDisplayWidget(QWidget):
    """Read-only widget displaying chronological events affecting an entity.

    Shows events sorted by date with their payload attributes, and highlights events at
    or before the current playhead time.
    """

    # Class-level calendar converter for date formatting
    _calendar_converter: Any = None
    event_clicked = Signal(str)

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

        # Setup UI
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text_display = QTextEdit()
        self._text_display.setReadOnly(True)
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
        from src.core.theme_manager import ThemeManager

        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def set_relations(self, relations: list[dict[str, Any]]) -> None:
        """Set the relations to display in the timeline.

        Args:
            relations: List of relation dicts with source_event_name,
                      source_event_date, source_event_description,
                      and attributes (including payload).

        """
        self._relations = relations
        self._refresh_display()

    def set_playhead_time(self, time: float) -> None:
        """Set the current playhead time for highlighting.

        Args:
            time: The playhead time in lore_date units.

        """
        self._playhead_time = time
        self._refresh_display()

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
        if not self._relations:
            self._text_display.setHtml(
                "<p style='color: gray; font-style: italic;'>"
                "No timeline events for this entity.</p>"
            )
            return

        # Clear description map for new display
        self._description_map = {}
        self._event_id_map = {}

        # Sort relations by date
        sorted_relations = sorted(
            self._relations,
            key=lambda r: self._get_event_date(r),
        )

        # Build HTML content with theme-aware styling
        from src.gui.utils.style_helper import StyleHelper

        html_parts = []
        html_parts.append("<style>")
        html_parts.append(StyleHelper.get_timeline_display_css())
        html_parts.append("</style>")

        for i, rel in enumerate(sorted_relations):
            event_date = self._get_event_date(rel)
            event_name = rel.get("source_event_name") or "Event"
            payload = rel.get("attributes", {}).get("payload", {})
            rel_type = rel.get("rel_type", "")

            # Extract description and build anchor ID
            anchor_id = rel.get("id") or f"card_{i}"
            event_id = rel.get("source_id") or rel.get("source_event_id")
            if event_id:
                self._event_id_map[anchor_id] = str(event_id)
            raw_desc = rel.get("source_event_description") or ""
            self._extract_and_map_description(anchor_id, raw_desc)

            # Format date using calendar converter if available
            if TimelineDisplayWidget._calendar_converter:
                date_str = TimelineDisplayWidget._calendar_converter.format_date(
                    event_date
                )
            else:
                date_str = f"{event_date:.1f}"

            # When the date is 0.0, it may be a genuine epoch event or a failed
            # date parse that defaulted to 0.0.  Show a subtle indicator.
            if event_date == 0.0:
                date_str = f"{date_str} <span class='date-unknown'>(date unknown)</span>"

            # Determine state: active (past/current) or future
            is_active = (
                self._playhead_time is not None and event_date <= self._playhead_time
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
            self._wrap_card_with_anchor(
                html_parts, anchor_id, has_desc or has_event
            )

            # Header: date + event name
            html_parts.append(
                f"<span class='event-date'>{date_str}</span><br>"
            )
            html_parts.append(
                f"<span class='event-name'>{event_name}</span>"
            )
            if rel_type:
                html_parts.append(
                    f" <span class='event-type'>({rel_type})</span>"
                )

            # Payload attributes (if any)
            if payload and isinstance(payload, dict):
                for key, value in payload.items():
                    display_val = "—" if value is None else str(value)
                    html_parts.append(
                        f"<br><span class='payload-key' style='margin-left: 16px;'>"
                        f"{key}:</span> "
                        f"<span class='payload-value'>{display_val}</span>"
                    )

            self._close_card_anchor(
                html_parts, anchor_id, has_desc or has_event
            )

            html_parts.append("</td></tr></table>")

            # Insert PLAYHEAD separator between past and future events
            if self._playhead_time is not None:
                next_idx = i + 1
                if next_idx < len(sorted_relations):
                    next_date = self._get_event_date(sorted_relations[next_idx])
                    # Current is past/present, next is future
                    if event_date <= self._playhead_time < next_date:
                        html_parts.append(
                            "<div class='now-separator'><span>▾ PLAYHEAD ▾</span></div>"
                        )

            # Insert NOW separator for story's current time
            if self._current_time is not None:
                next_idx = i + 1
                if next_idx < len(sorted_relations):
                    next_date = self._get_event_date(sorted_relations[next_idx])
                    if event_date <= self._current_time < next_date:
                        html_parts.append(
                            "<div class='now-line'><span>● NOW ●</span></div>"
                        )

        self._text_display.setHtml("\n".join(html_parts))

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
            html_parts.append(f"<a href='{anchor_id}' style='text-decoration: none;'>")

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

    def _get_event_date(self, rel: dict[str, Any]) -> float:
        """Get the date to use for sorting/displaying an event.

        Uses source_event_date if available, otherwise valid_from.

        Note:
            A returned value of 0.0 is ambiguous: it may mean the event
            genuinely occurs at the calendar epoch, or that its lore_date
            could not be parsed during import and was silently defaulted to
            0.0.  The caller should treat 0.0 with appropriate caution.

        Args:
            rel: Relation dict.

        Returns:
            Date as float.

        """
        # Prefer source_event_date (from Event JOIN)
        if "source_event_date" in rel and rel["source_event_date"] is not None:
            return float(rel["source_event_date"])

        # Fall back to valid_from in attributes
        attrs = rel.get("attributes", {})
        if "valid_from" in attrs and attrs["valid_from"] is not None:
            return float(attrs["valid_from"])

        # Default to 0 if no date available
        return 0.0

    def clear(self) -> None:
        """Clear the timeline display."""
        self._relations = []
        self._playhead_time = None
        self._description_map = {}
        self._event_id_map = {}
        self._text_display.clear()

    def _activate_anchor(self, anchor_id: str) -> bool:
        """Navigate to the event represented by an anchor, when available."""
        event_id = self._event_id_map.get(anchor_id)
        if not event_id:
            return False
        self.event_clicked.emit(event_id)
        return True

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
            anchor = self._text_display.anchorAt(event.position().toPoint())
            if anchor and self._activate_anchor(anchor):
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
