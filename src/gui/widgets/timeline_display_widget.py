"""
Timeline Display Widget Module.

Provides a read-only widget that displays a chronological list of events
affecting an entity, with payload attributes shown inline.
"""

from typing import Any, Optional

from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class TimelineDisplayWidget(QWidget):
    """
    Read-only widget displaying chronological events affecting an entity.

    Shows events sorted by date with their payload attributes, and highlights
    events at or before the current playhead time.
    """

    # Class-level calendar converter for date formatting
    _calendar_converter: Any = None

    @classmethod
    def set_calendar_converter(cls, converter: Any) -> None:
        """Set the calendar converter for date formatting."""
        cls._calendar_converter = converter

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the timeline display widget.

        Args:
            parent: Parent widget, if any.
        """
        super().__init__(parent)

        self._relations: list[dict[str, Any]] = []
        self._playhead_time: Optional[float] = None
        self._current_time: Optional[float] = None  # Story's "current time"

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

    def set_relations(self, relations: list[dict[str, Any]]) -> None:
        """
        Set the relations to display in the timeline.

        Args:
            relations: List of relation dicts with source_event_name,
                      source_event_date, and attributes (including payload).
        """
        self._relations = relations
        self._refresh_display()

    def set_playhead_time(self, time: float) -> None:
        """
        Set the current playhead time for highlighting.

        Args:
            time: The playhead time in lore_date units.
        """
        self._playhead_time = time
        self._refresh_display()

    def set_current_time(self, time: Optional[float]) -> None:
        """
        Set the story's 'current time' for the NOW marker.

        Args:
            time: The current time in lore_date units, or None to hide.
        """
        self._current_time = time
        self._refresh_display()

    def get_display_text(self) -> str:
        """
        Get the current display text (for testing).

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

        # Sort relations by date
        sorted_relations = sorted(
            self._relations,
            key=lambda r: self._get_event_date(r),
        )

        # Build HTML content with refined styling
        html_parts = []
        html_parts.append("<style>")
        # Clean, modern styling
        html_parts.append(
            """
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
            .timeline-entry { 
                padding: 8px 10px; 
                margin: 6px 2px;
                border-radius: 3px;
                border: 1px solid #555;
            }
            .timeline-entry.active { 
                border-color: #4CAF50;
                border-width: 2px;
            }
            .timeline-entry.future { 
                opacity: 0.5;
                border-color: #444;
            }
            .event-header { margin-bottom: 4px; }
            .event-date { 
                color: #888; 
                font-size: 11px;
                font-weight: 500;
            }
            .event-name { 
                color: #E0E0E0; 
                font-weight: 600;
                font-size: 13px;
            }
            .event-type { 
                color: #666; 
                font-size: 10px;
                font-style: italic;
            }
            .payload-list { 
                margin: 4px 0 0 16px;
                padding: 0;
            }
            .payload-item { 
                color: #888; 
                font-size: 11px;
                line-height: 1.4;
            }
            .payload-key { color: #6A9FB5; }
            .payload-value { color: #B5BD68; }
            .now-separator {
                display: flex;
                align-items: center;
                margin: 12px 0;
                color: #FFD700;
                font-size: 10px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .now-separator::before,
            .now-separator::after {
                content: '';
                flex: 1;
                height: 1px;
                background: linear-gradient(to right, transparent, #FFD700, transparent);
            }
            .now-separator span {
                padding: 0 10px;
            }
            .now-line {
                display: flex;
                align-items: center;
                margin: 12px 0;
                color: #4CAF50;
                font-size: 10px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .now-line::before,
            .now-line::after {
                content: '';
                flex: 1;
                height: 2px;
                background: #4CAF50;
            }
            .now-line span {
                padding: 0 10px;
            }
        """
        )
        html_parts.append("</style>")

        for i, rel in enumerate(sorted_relations):
            event_date = self._get_event_date(rel)
            event_name = rel.get("source_event_name") or "Event"
            payload = rel.get("attributes", {}).get("payload", {})
            rel_type = rel.get("rel_type", "")

            # Format date using calendar converter if available
            if TimelineDisplayWidget._calendar_converter:
                date_str = TimelineDisplayWidget._calendar_converter.format_date(
                    event_date
                )
            else:
                date_str = f"{event_date:.1f}"

            # Determine state: active (past/current) or future
            is_active = (
                self._playhead_time is not None and event_date <= self._playhead_time
            )

            # Use table for border (QTextEdit renders table borders properly)
            border_color = "#4CAF50" if is_active else "#888888"
            text_opacity = "" if is_active else "color: #888;"

            html_parts.append(
                f"<table width='100%' cellpadding='8' cellspacing='0' "
                f"style='margin: 4px 0; border: 2px solid {border_color}; "
                f"border-radius: 6px;'>"
            )
            html_parts.append("<tr><td>")

            # Header: date + event name
            html_parts.append(
                f"<span style='color: #888; font-size: 11px;'>{date_str}</span><br>"
            )
            html_parts.append(
                f"<span style='color: #E0E0E0; font-weight: bold; {text_opacity}'>"
                f"{event_name}</span>"
            )
            if rel_type:
                html_parts.append(
                    f" <span style='color: #666; font-size: 10px; font-style: italic;'>"
                    f"({rel_type})</span>"
                )

            # Payload attributes (if any)
            if payload and isinstance(payload, dict):
                for key, value in payload.items():
                    display_val = "—" if value is None else str(value)
                    html_parts.append(
                        f"<br><span style='margin-left: 16px; color: #6A9FB5;'>"
                        f"{key}:</span> "
                        f"<span style='color: #B5BD68;'>{display_val}</span>"
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

    def _get_event_date(self, rel: dict[str, Any]) -> float:
        """
        Get the date to use for sorting/displaying an event.

        Uses source_event_date if available, otherwise valid_from.

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
        self._text_display.clear()
