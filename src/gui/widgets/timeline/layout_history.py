"""GUI-owned, per-occurrence history; workers only receive frozen snapshots."""

from src.core.timeline_layout import TimelineLayoutSnapshot


class TimelineLayoutHistory:
    """Retain accepted layouts separately for standard, tag and summary scopes."""

    def __init__(self) -> None:
        """Start with no accepted or staged layouts."""
        self._accepted: dict[str, TimelineLayoutSnapshot] = {}
        self._pending: dict[str, TimelineLayoutSnapshot] = {}

    def snapshot(self, scope: str = "standard") -> TimelineLayoutSnapshot:
        """Return immutable accepted state, never an in-flight calculation."""
        return self._accepted.get(scope, TimelineLayoutSnapshot())

    def stage(self, scope: str, lanes: dict[str, int], heights: list[int]) -> None:
        """Stage a result until its GUI pass succeeds."""
        self._pending[scope] = TimelineLayoutSnapshot(
            tuple(sorted(lanes.items())), tuple(heights)
        )

    def commit(self) -> None:
        """Publish a successfully applied pass."""
        self._accepted.update(self._pending)
        self._pending.clear()

    def prepare(self, ids: set[str], scopes: set[str]) -> None:
        """Discard failed staging, removed scopes and deleted event references."""
        self._pending.clear()
        self._accepted = {
            scope: TimelineLayoutSnapshot(
                tuple((key, lane) for key, lane in state.lanes if key in ids),
                state.heights,
            )
            for scope, state in self._accepted.items()
            if scope in scopes and ids
        }

    def clear(self) -> None:
        """Start a compact baseline, also invalidating staged group results."""
        self._accepted.clear()
        self._pending.clear()
