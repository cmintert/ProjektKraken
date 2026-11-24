"""Temporary access to canonical timing evidence from the Timeline."""

from collections.abc import Callable

from PySide6.QtCore import QObject

from src.core.authoring_scope import AuthoringScope
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.core.timeline_dependencies import timeline_dependencies
from src.gui.widgets.timeline import TimelineWidget


class ScopedHistory(QObject):
    """Describe which hidden events are relevant to the accepted selection."""

    def __init__(
        self, timeline: TimelineWidget, events: Callable[[], list[Event]]
    ) -> None:
        """Connect the display exception to canonical event snapshots."""
        super().__init__(timeline)
        self._timeline = timeline
        self._events = events
        self._scope = AuthoringScope()
        self._selection = ("", "")
        self._related: set[str] = set()
        self._sources: set[str] = set()
        self._shown = False
        self._unplaced_menu = timeline.unplaced_history_menu
        timeline.history_reveal_button.clicked.connect(self.toggle)
        self.refresh()

    def scope_changed(self, scope: AuthoringScope) -> None:
        """Reset history presentation for the new scope."""
        self._scope = scope
        self._shown = False
        self._timeline.view.set_authoring_scope(scope)
        self.refresh()

    def selected(self, kind: str, identity: str, outcome: str) -> None:
        """Keep the reveal attached to the accepted navigation target."""
        if outcome != "selected" or self._selection == (kind, identity):
            return
        self._selection = kind, identity
        self._related.clear()
        self._sources.clear()
        self._shown = False
        self.refresh()

    def relations(self, kind: str, identity: str, rows: list[dict]) -> None:
        """Collect canonical authored relation endpoints and legacy event links."""
        if self._selection != (kind, identity):
            return
        related: set[str] = set()
        for row in rows:
            if row.get("rel_type", "").strip().casefold() == "mentions":
                continue
            related.update(
                value.removeprefix("id:")
                for key in ("source_id", "target_id")
                if isinstance(value := row.get(key), str) and value != identity
            )
            historical = row.get("historical_event")
            if isinstance(historical, dict) and isinstance(historical.get("id"), str):
                related.add(historical["id"])
            attributes = row.get("attributes") or {}
            spec = attributes.get("temporal", {})
            if isinstance(spec, dict):
                related.update(self._relation_anchors(spec))
        self._related = related
        self.refresh()

    @staticmethod
    def _relation_anchors(spec: dict) -> set[str]:
        result: set[str] = set()
        for key in ("start", "end", "at"):
            boundary = spec.get(key)
            if isinstance(boundary, dict) and isinstance(
                anchor := boundary.get("anchor"), dict
            ):
                value = anchor.get("anchor_id")
                if isinstance(value, str) and value.startswith("event:"):
                    result.add(value.split(":")[1])
        return result

    def state(self, identity: str, state: dict) -> None:
        """Retain the event identities that supply resolved Entity facts."""
        if self._selection != ("entity", identity):
            return
        sources = [state.get("description_source")]
        for field in ("attribute_sources", "absent_attribute_sources"):
            values = state.get(field)
            if isinstance(values, dict):
                sources.extend(values.values())
        self._sources = {
            source["event_id"]
            for source in sources
            if isinstance(source, dict) and isinstance(source.get("event_id"), str)
        }
        self.refresh()

    def toggle(self) -> None:
        """Show or dismiss related events without changing the viewing date."""
        self._shown = not self._shown
        self.refresh()

    def refresh(self) -> None:
        """Recompute the reveal against the latest unfiltered world snapshot."""
        hidden = self._hidden_events() if self._scope.tags else frozenset()
        self._shown = self._shown and bool(hidden)
        button = self._timeline.history_reveal_button
        self._timeline.action_toolbar.set_button_available(button, bool(hidden))
        button.setText(
            "Hide revealed history" if self._shown else "Show hidden history"
        )
        button.setToolTip(f"{len(hidden)} related events outside the current scope")
        self._timeline.view.reveal_history(hidden if self._shown else frozenset())
        self._present_unplaced(hidden)

    def _present_unplaced(self, hidden: frozenset[str]) -> None:
        identities = (
            self._timeline.view.unplaced_event_ids() & hidden
            if self._shown
            else frozenset()
        )
        button = self._timeline.unplaced_history_button
        self._timeline.action_toolbar.set_button_available(button, bool(identities))
        self._unplaced_menu.clear()
        if identities:
            for event in self._events():
                if event.id in identities:
                    self._unplaced_menu.addAction(
                        event.name,
                        lambda _checked=False,
                        identity=event.id: self._timeline.event_selected.emit(identity),
                    )

    def _hidden_events(self) -> frozenset[str]:
        events = self._events()
        related = self._related | self._sources
        kind, identity = self._selection
        if kind == "event":
            for dependency in timeline_dependencies(events):
                pair = {dependency.source_id, dependency.target_id}
                if identity in pair:
                    related.update(pair - {identity})
            for rule in TemporalResolutionContext.build(events, None).constraints():
                pair = {
                    anchor.split(":")[1]
                    for anchor in (rule.anchor_a, rule.anchor_b)
                    if anchor.startswith("event:")
                }
                if identity in pair:
                    related.update(pair - {identity})
        return frozenset(
            event.id
            for event in events
            if event.id in related and not self._scope.matches(event.tags)
        )
