"""GUI-independent working state for direct trajectory editing."""

import math
import uuid
from dataclasses import dataclass, replace
from typing import Sequence, TypedDict

from src.core.trajectory import (
    EditableKeyframe,
    Keyframe,
    clone_keyframes,
    infer_midpoint_time,
    validate_keyframes,
)


class EditableKeyframeSnapshot(TypedDict):
    """Serializable editable-keyframe state for GUI rendering."""

    edit_id: str
    t: float
    x: float
    y: float


class TrajectoryEditSnapshot(TypedDict):
    """Serializable trajectory edit-session state for GUI rendering."""

    map_id: str
    marker_id: str
    trajectory_id: str | None
    keyframes: list[EditableKeyframeSnapshot]
    selected_keyframe_id: str | None
    selected_keyframe_index: int | None
    active_date_edit_id: str | None
    is_date_editing: bool
    date_edit_original_t: float | None
    date_edit_proposed_t: float | None
    date_edit_delta: float | None
    keyframe_count: int
    is_dirty: bool
    is_conflicted: bool
    validation_errors: list[str]
    midpoint_errors: dict[str, str]
    can_apply: bool


@dataclass
class TrajectoryEditSession:
    """Own one isolated working trajectory and its spatial edit state."""

    map_id: str
    marker_id: str
    trajectory_id: str | None
    original_keyframes: tuple[EditableKeyframe, ...]
    working_keyframes: list[EditableKeyframe]
    selected_keyframe_id: str | None
    active_date_edit_id: str | None
    playhead_at_session_start: float
    playhead_before_date_edit: float | None
    date_edit_original_t: float | None
    is_dirty: bool
    is_conflicted: bool
    validation_errors: list[str]

    @classmethod
    def create(
        cls,
        map_id: str,
        marker_id: str,
        trajectory_id: str | None,
        keyframes: Sequence[Keyframe],
        playhead: float,
    ) -> "TrajectoryEditSession":
        """Create a session with independent original and working values.

        Args:
            map_id: ID of the containing map.
            marker_id: Entity ID associated with the trajectory.
            trajectory_id: Persisted trajectory row ID, if one exists.
            keyframes: Authoritative keyframes captured at session start.
            playhead: Global lore date captured at session start.

        Returns:
            A clean trajectory edit session.

        """
        original = tuple(
            EditableKeyframe(
                edit_id=str(uuid.uuid4()),
                t=keyframe.t,
                x=keyframe.x,
                y=keyframe.y,
            )
            for keyframe in keyframes
        )
        working = clone_keyframes(original)
        return cls(
            map_id=map_id,
            marker_id=marker_id,
            trajectory_id=trajectory_id,
            original_keyframes=original,
            working_keyframes=working,
            selected_keyframe_id=None,
            active_date_edit_id=None,
            playhead_at_session_start=playhead,
            playhead_before_date_edit=None,
            date_edit_original_t=None,
            is_dirty=False,
            is_conflicted=False,
            validation_errors=validate_keyframes(working),
        )

    @property
    def can_apply(self) -> bool:
        """Whether the working trajectory can be persisted."""
        return self.is_dirty and not self.is_conflicted and not self.validation_errors

    @property
    def active_date_value(self) -> float | None:
        """Return the active keyframe's proposed date, if retiming."""
        if self.active_date_edit_id is None:
            return None
        return self.working_keyframes[
            self._index_of(self.active_date_edit_id)
        ].t

    def select_keyframe(self, edit_id: str) -> None:
        """Select a keyframe by stable edit identity.

        Args:
            edit_id: Session-local keyframe identity.

        Raises:
            ValueError: If no working keyframe has the identity.

        """
        self._index_of(edit_id)
        self.selected_keyframe_id = edit_id

    def move_keyframe(self, edit_id: str, x: float, y: float) -> None:
        """Move one keyframe spatially while preserving its lore date.

        Args:
            edit_id: Session-local keyframe identity.
            x: New normalized X coordinate.
            y: New normalized Y coordinate.

        Raises:
            ValueError: If the identity or coordinates are invalid.

        """
        self._validate_position(x, y)
        index = self._index_of(edit_id)
        current = self.working_keyframes[index]
        self.working_keyframes[index] = replace(current, x=x, y=y)
        self.selected_keyframe_id = edit_id
        self._refresh_state()

    def begin_date_edit(self, edit_id: str, current_playhead: float) -> float:
        """Begin retiming one stable keyframe and capture playhead state.

        Args:
            edit_id: Session-local keyframe identity.
            current_playhead: Global playhead value before retiming begins.

        Returns:
            The keyframe date that the playhead should jump to.

        Raises:
            ValueError: If the identity or playhead value is invalid.

        """
        if not math.isfinite(current_playhead):
            raise ValueError("Playhead time must be finite.")
        index = self._index_of(edit_id)
        if self.active_date_edit_id == edit_id:
            return self.working_keyframes[index].t
        if self.active_date_edit_id is not None:
            raise ValueError("Finish the active keyframe date edit first.")
        keyframe = self.working_keyframes[index]
        self.selected_keyframe_id = edit_id
        self.active_date_edit_id = edit_id
        self.playhead_before_date_edit = current_playhead
        self.date_edit_original_t = keyframe.t
        return keyframe.t

    def update_active_date(self, proposed_time: float) -> None:
        """Update the active keyframe date while retaining invalid previews.

        Timestamp collisions remain in the working state so the UI can explain
        and correct them, while :attr:`can_apply` stays false.

        Args:
            proposed_time: Proposed lore-date value.

        Raises:
            ValueError: If no date edit is active or the value is non-finite.

        """
        if self.active_date_edit_id is None:
            raise ValueError("No keyframe date edit is active.")
        if not math.isfinite(proposed_time):
            raise ValueError("Keyframe time must be finite.")
        index = self._index_of(self.active_date_edit_id)
        current = self.working_keyframes[index]
        self.working_keyframes[index] = replace(current, t=proposed_time)
        self.selected_keyframe_id = current.edit_id
        self._refresh_state()

    def finish_date_edit(self) -> float | None:
        """Keep the proposed date and end only the temporal sub-operation."""
        if self.active_date_edit_id is None:
            return None
        proposed_time = self.working_keyframes[
            self._index_of(self.active_date_edit_id)
        ].t
        self.active_date_edit_id = None
        self.playhead_before_date_edit = None
        self.date_edit_original_t = None
        return proposed_time

    def cancel_date_edit(self) -> float | None:
        """Restore the pre-edit working date and return the prior playhead."""
        if self.active_date_edit_id is None:
            return None
        edit_id = self.active_date_edit_id
        index = self._index_of(edit_id)
        current = self.working_keyframes[index]
        if self.date_edit_original_t is not None:
            self.working_keyframes[index] = replace(
                current, t=self.date_edit_original_t
            )
        playhead = self.playhead_before_date_edit
        self.active_date_edit_id = None
        self.playhead_before_date_edit = None
        self.date_edit_original_t = None
        self.selected_keyframe_id = edit_id
        self._refresh_state()
        return playhead

    def insert_between(
        self,
        start_id: str,
        end_id: str,
        x: float,
        y: float,
    ) -> str:
        """Insert a midpoint-dated keyframe between adjacent neighbours.

        Args:
            start_id: Stable identity of the earlier segment endpoint.
            end_id: Stable identity of the later segment endpoint.
            x: New normalized X coordinate.
            y: New normalized Y coordinate.

        Returns:
            Stable identity assigned to the inserted keyframe.

        Raises:
            ValueError: If endpoints are not adjacent or insertion is invalid.

        """
        self._validate_position(x, y)
        start_index = self._index_of(start_id)
        end_index = self._index_of(end_id)
        if end_index != start_index + 1:
            raise ValueError("Midpoint endpoints must be adjacent keyframes.")

        start = self.working_keyframes[start_index]
        end = self.working_keyframes[end_index]
        inserted = EditableKeyframe(
            edit_id=str(uuid.uuid4()),
            t=infer_midpoint_time(start, end),
            x=x,
            y=y,
        )
        candidate = [*self.working_keyframes, inserted]
        candidate.sort(key=lambda keyframe: keyframe.t)
        errors = validate_keyframes(candidate)
        if errors:
            raise ValueError(errors[0])

        self.working_keyframes = candidate
        self.selected_keyframe_id = inserted.edit_id
        self._refresh_state()
        return inserted.edit_id

    def delete_selected_keyframe(self) -> bool:
        """Delete only the selected working keyframe, including the final one."""
        if self.selected_keyframe_id is None:
            return False
        index = self._index_of(self.selected_keyframe_id)
        del self.working_keyframes[index]
        if self.active_date_edit_id == self.selected_keyframe_id:
            self.active_date_edit_id = None
            self.playhead_before_date_edit = None
            self.date_edit_original_t = None
        if self.working_keyframes:
            next_index = min(index, len(self.working_keyframes) - 1)
            self.selected_keyframe_id = self.working_keyframes[next_index].edit_id
        else:
            self.selected_keyframe_id = None
        self._refresh_state()
        return True

    def mark_conflicted(self) -> None:
        """Block Apply because authoritative state changed externally."""
        self.is_conflicted = True

    def restore_original(self) -> None:
        """Discard all working changes while preserving independent values."""
        self.working_keyframes = clone_keyframes(self.original_keyframes)
        self.selected_keyframe_id = None
        self.active_date_edit_id = None
        self.playhead_before_date_edit = None
        self.date_edit_original_t = None
        self.is_conflicted = False
        self._refresh_state()

    def to_keyframes(self) -> list[Keyframe]:
        """Return an independent persistence-ready working trajectory."""
        return [
            Keyframe(t=keyframe.t, x=keyframe.x, y=keyframe.y)
            for keyframe in self.working_keyframes
        ]

    def to_snapshot(self) -> TrajectoryEditSnapshot:
        """Return immutable-by-convention serialized state for the GUI."""
        selected_index: int | None = None
        if self.selected_keyframe_id is not None:
            selected_index = self._index_of(self.selected_keyframe_id)
        proposed_time: float | None = None
        if self.active_date_edit_id is not None:
            proposed_time = self.working_keyframes[
                self._index_of(self.active_date_edit_id)
            ].t
        date_delta = (
            proposed_time - self.date_edit_original_t
            if proposed_time is not None and self.date_edit_original_t is not None
            else None
        )
        return {
            "map_id": self.map_id,
            "marker_id": self.marker_id,
            "trajectory_id": self.trajectory_id,
            "keyframes": [
                {
                    "edit_id": keyframe.edit_id,
                    "t": keyframe.t,
                    "x": keyframe.x,
                    "y": keyframe.y,
                }
                for keyframe in self.working_keyframes
            ],
            "selected_keyframe_id": self.selected_keyframe_id,
            "selected_keyframe_index": selected_index,
            "active_date_edit_id": self.active_date_edit_id,
            "is_date_editing": self.active_date_edit_id is not None,
            "date_edit_original_t": self.date_edit_original_t,
            "date_edit_proposed_t": proposed_time,
            "date_edit_delta": date_delta,
            "keyframe_count": len(self.working_keyframes),
            "is_dirty": self.is_dirty,
            "is_conflicted": self.is_conflicted,
            "validation_errors": list(self.validation_errors),
            "midpoint_errors": self._midpoint_errors(),
            "can_apply": self.can_apply,
        }

    @staticmethod
    def midpoint_key(start_id: str, end_id: str) -> str:
        """Return the stable snapshot key for one insertion segment."""
        return f"{start_id}:{end_id}"

    def _midpoint_errors(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        for start, end in zip(
            self.working_keyframes, self.working_keyframes[1:]
        ):
            try:
                inserted = EditableKeyframe(
                    edit_id="midpoint-preview",
                    t=infer_midpoint_time(start, end),
                    x=(start.x + end.x) / 2.0,
                    y=(start.y + end.y) / 2.0,
                )
                candidate = [*self.working_keyframes, inserted]
                candidate.sort(key=lambda keyframe: keyframe.t)
                validation = validate_keyframes(candidate)
                if validation:
                    errors[self.midpoint_key(start.edit_id, end.edit_id)] = validation[0]
            except ValueError as exc:
                errors[self.midpoint_key(start.edit_id, end.edit_id)] = str(exc)
        return errors

    def _index_of(self, edit_id: str) -> int:
        for index, keyframe in enumerate(self.working_keyframes):
            if keyframe.edit_id == edit_id:
                return index
        raise ValueError(f"Unknown editable keyframe: {edit_id}")

    @staticmethod
    def _validate_position(x: float, y: float) -> None:
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Keyframe coordinates must be finite.")
        if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
            raise ValueError("Keyframe coordinates must be between 0.0 and 1.0.")

    def _refresh_state(self) -> None:
        self.working_keyframes.sort(key=lambda keyframe: keyframe.t)
        self.validation_errors = validate_keyframes(self.working_keyframes)
        original_values = [
            (keyframe.t, keyframe.x, keyframe.y)
            for keyframe in self.original_keyframes
        ]
        working_values = [
            (keyframe.t, keyframe.x, keyframe.y)
            for keyframe in self.working_keyframes
        ]
        self.is_dirty = working_values != original_values
