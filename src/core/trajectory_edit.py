"""GUI-independent working state for direct trajectory editing."""

import math
import uuid
from dataclasses import dataclass, replace
from typing import Sequence, TypedDict

from src.core.trajectory import (
    EditableKeyframe,
    Keyframe,
    TrajectoryDistanceContext,
    clone_keyframes,
    cumulative_trajectory_distances,
    equalize_keyframe_times,
    infer_midpoint_time,
    validate_keyframes,
)


class EditableKeyframeSnapshot(TypedDict):
    """Serializable editable-keyframe state for GUI rendering."""

    edit_id: str
    t: float
    x: float
    y: float


class EqualizationChangeSnapshot(TypedDict):
    """One intermediate date changed by an equalization preview."""

    edit_id: str
    keyframe_number: int
    original_t: float
    proposed_t: float


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
    speed_anchor_id: str | None
    speed_anchor_index: int | None
    equalization_start_id: str | None
    equalization_end_id: str | None
    is_equalization_previewing: bool
    equalization_changes: list[EqualizationChangeSnapshot]
    equalization_total_distance: float | None
    equalization_average_speed: float | None
    equalization_distance_unit: str | None
    can_equalize_to_selected: bool
    can_equalize_whole: bool
    keyframe_count: int
    is_dirty: bool
    is_conflicted: bool
    validation_errors: list[str]
    midpoint_errors: dict[str, str]
    can_apply: bool


@dataclass(frozen=True)
class EqualizationDateChange:
    """Independent before-and-proposed date for one intermediate keyframe."""

    edit_id: str
    keyframe_number: int
    original_t: float
    proposed_t: float


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
    date_edit_original_t: float | None
    speed_anchor_id: str | None
    equalization_before: tuple[EditableKeyframe, ...] | None
    equalization_start_id: str | None
    equalization_end_id: str | None
    equalization_changes: tuple[EqualizationDateChange, ...]
    equalization_total_distance: float | None
    equalization_average_speed: float | None
    equalization_distance_unit: str | None
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
    ) -> "TrajectoryEditSession":
        """Create a session with independent original and working values.

        Args:
            map_id: ID of the containing map.
            marker_id: Entity ID associated with the trajectory.
            trajectory_id: Persisted trajectory row ID, if one exists.
            keyframes: Authoritative keyframes captured at session start.

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
            date_edit_original_t=None,
            speed_anchor_id=None,
            equalization_before=None,
            equalization_start_id=None,
            equalization_end_id=None,
            equalization_changes=(),
            equalization_total_distance=None,
            equalization_average_speed=None,
            equalization_distance_unit=None,
            is_dirty=False,
            is_conflicted=False,
            validation_errors=validate_keyframes(working),
        )

    @property
    def can_apply(self) -> bool:
        """Whether the working trajectory can be persisted."""
        return (
            self.is_dirty
            and not self.is_conflicted
            and not self.validation_errors
            and self.equalization_before is None
        )

    @property
    def is_equalization_previewing(self) -> bool:
        """Whether redistributed dates await preview confirmation."""
        return self.equalization_before is not None

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
        self._require_no_equalization_preview()
        self._validate_position(x, y)
        index = self._index_of(edit_id)
        current = self.working_keyframes[index]
        self.working_keyframes[index] = replace(current, x=x, y=y)
        self.selected_keyframe_id = edit_id
        self._refresh_state()

    def set_keyframe_time(self, edit_id: str, proposed_time: float) -> None:
        """Assign a proposed date to one stable keyframe identity.

        Invalid trajectory-wide results remain in the working copy so the UI
        can explain them and block Apply without losing the proposal.

        Args:
            edit_id: Session-local keyframe identity.
            proposed_time: Proposed lore-date value.

        Raises:
            ValueError: If the identity or proposed value is invalid.

        """
        self._require_no_equalization_preview()
        if not math.isfinite(proposed_time):
            raise ValueError("Keyframe time must be finite.")
        if (
            self.active_date_edit_id is not None
            and self.active_date_edit_id != edit_id
        ):
            raise ValueError("Finish the active keyframe date edit first.")
        index = self._index_of(edit_id)
        current = self.working_keyframes[index]
        self.working_keyframes[index] = replace(current, t=proposed_time)
        self.selected_keyframe_id = edit_id
        self._refresh_state()

    def begin_date_edit(self, edit_id: str) -> None:
        """Begin an isolated date sub-operation for one stable keyframe.

        Args:
            edit_id: Session-local keyframe identity.

        Raises:
            ValueError: If the identity is invalid or another edit is active.

        """
        self._require_no_equalization_preview()
        index = self._index_of(edit_id)
        if self.active_date_edit_id == edit_id:
            return
        if self.active_date_edit_id is not None:
            raise ValueError("Finish the active keyframe date edit first.")
        keyframe = self.working_keyframes[index]
        self.selected_keyframe_id = edit_id
        self.active_date_edit_id = edit_id
        self.date_edit_original_t = keyframe.t

    def update_active_date(self, proposed_time: float) -> None:
        """Update the active keyframe date while retaining invalid previews.

        Timestamp collisions remain in the working state so the UI can explain
        and correct them, while :attr:`can_apply` stays false.

        Args:
            proposed_time: Proposed lore-date value.

        Raises:
            ValueError: If no date edit is active or the value is non-finite.

        """
        self._require_no_equalization_preview()
        if self.active_date_edit_id is None:
            raise ValueError("No keyframe date edit is active.")
        self.set_keyframe_time(self.active_date_edit_id, proposed_time)

    def finish_date_edit(self) -> bool:
        """Keep the proposed date and end only the temporal sub-operation."""
        if self.active_date_edit_id is None:
            return False
        self.active_date_edit_id = None
        self.date_edit_original_t = None
        return True

    def cancel_date_edit(self) -> bool:
        """Restore the working date captured when the sub-operation began."""
        if self.active_date_edit_id is None:
            return False
        edit_id = self.active_date_edit_id
        index = self._index_of(edit_id)
        current = self.working_keyframes[index]
        if self.date_edit_original_t is not None:
            self.working_keyframes[index] = replace(
                current, t=self.date_edit_original_t
            )
        self.active_date_edit_id = None
        self.date_edit_original_t = None
        self.selected_keyframe_id = edit_id
        self._refresh_state()
        return True

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
        self._require_no_equalization_preview()
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
        self._require_no_equalization_preview()
        if self.selected_keyframe_id is None:
            return False
        index = self._index_of(self.selected_keyframe_id)
        del self.working_keyframes[index]
        if self.active_date_edit_id == self.selected_keyframe_id:
            self.active_date_edit_id = None
            self.date_edit_original_t = None
        if self.speed_anchor_id == self.selected_keyframe_id:
            self.speed_anchor_id = None
        if self.working_keyframes:
            next_index = min(index, len(self.working_keyframes) - 1)
            self.selected_keyframe_id = self.working_keyframes[next_index].edit_id
        else:
            self.selected_keyframe_id = None
        self._refresh_state()
        return True

    def set_speed_anchor(self, edit_id: str) -> None:
        """Mark one stable keyframe as the equalization start anchor."""
        self._require_no_equalization_preview()
        if self.active_date_edit_id is not None:
            raise ValueError("Finish editing the keyframe date first.")
        self._index_of(edit_id)
        self.speed_anchor_id = edit_id
        self.selected_keyframe_id = edit_id

    def clear_speed_anchor(self) -> None:
        """Clear an uncommitted equalization anchor."""
        self._require_no_equalization_preview()
        self.speed_anchor_id = None

    def preview_speed_equalization(
        self,
        end_id: str,
        context: TrajectoryDistanceContext,
    ) -> None:
        """Preview constant-speed dates from the start anchor to ``end_id``."""
        if self.speed_anchor_id is None:
            raise ValueError("Set a start anchor first.")
        self._preview_equalization(self.speed_anchor_id, end_id, context)

    def preview_whole_speed_equalization(
        self, context: TrajectoryDistanceContext
    ) -> None:
        """Preview constant speed across the complete working trajectory."""
        if len(self.working_keyframes) < 3:
            raise ValueError(
                "Whole-trajectory equalization needs an intermediate keyframe."
            )
        start_id = self.working_keyframes[0].edit_id
        end_id = self.working_keyframes[-1].edit_id
        self._preview_equalization(start_id, end_id, context)
        self.speed_anchor_id = start_id

    def confirm_speed_equalization(self) -> bool:
        """Keep previewed dates in the working copy without persisting them."""
        if self.equalization_before is None:
            return False
        self._clear_equalization_state(clear_anchor=True)
        self._refresh_state()
        return True

    def cancel_speed_equalization(self) -> bool:
        """Restore the working dates captured before equalization preview."""
        if self.equalization_before is None:
            return False
        self.working_keyframes = clone_keyframes(self.equalization_before)
        self._clear_equalization_state(clear_anchor=True)
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
        self.date_edit_original_t = None
        self.speed_anchor_id = None
        self._clear_equalization_state(clear_anchor=True)
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
        speed_anchor_index: int | None = None
        if self.speed_anchor_id is not None:
            speed_anchor_index = self._index_of(self.speed_anchor_id)
        can_equalize_to_selected = (
            self.equalization_before is None
            and self.active_date_edit_id is None
            and speed_anchor_index is not None
            and selected_index is not None
            and selected_index - speed_anchor_index >= 2
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
            "speed_anchor_id": self.speed_anchor_id,
            "speed_anchor_index": speed_anchor_index,
            "equalization_start_id": self.equalization_start_id,
            "equalization_end_id": self.equalization_end_id,
            "is_equalization_previewing": self.equalization_before is not None,
            "equalization_changes": [
                {
                    "edit_id": change.edit_id,
                    "keyframe_number": change.keyframe_number,
                    "original_t": change.original_t,
                    "proposed_t": change.proposed_t,
                }
                for change in self.equalization_changes
            ],
            "equalization_total_distance": self.equalization_total_distance,
            "equalization_average_speed": self.equalization_average_speed,
            "equalization_distance_unit": self.equalization_distance_unit,
            "can_equalize_to_selected": can_equalize_to_selected,
            "can_equalize_whole": (
                self.equalization_before is None
                and self.active_date_edit_id is None
                and len(self.working_keyframes) >= 3
            ),
            "keyframe_count": len(self.working_keyframes),
            "is_dirty": self.is_dirty,
            "is_conflicted": self.is_conflicted,
            "validation_errors": list(self.validation_errors),
            "midpoint_errors": self._midpoint_errors(),
            "can_apply": self.can_apply,
        }

    def _preview_equalization(
        self,
        start_id: str,
        end_id: str,
        context: TrajectoryDistanceContext,
    ) -> None:
        self._require_no_equalization_preview()
        if self.active_date_edit_id is not None:
            raise ValueError("Finish editing the keyframe date first.")
        start_index = self._index_of(start_id)
        end_index = self._index_of(end_id)
        if end_index - start_index < 2:
            raise ValueError(
                "Equalize Speed needs at least one intermediate keyframe."
            )

        before = tuple(clone_keyframes(self.working_keyframes))
        equalized = equalize_keyframe_times(
            self.working_keyframes,
            start_index,
            end_index,
            context,
        )
        changes = tuple(
            EqualizationDateChange(
                edit_id=proposed.edit_id,
                keyframe_number=index + 1,
                original_t=original.t,
                proposed_t=proposed.t,
            )
            for index, (original, proposed) in enumerate(
                zip(self.working_keyframes, equalized)
            )
            if start_index < index < end_index
            and not math.isclose(original.t, proposed.t, abs_tol=1e-9)
        )
        if not changes:
            raise ValueError("The selected range already has equalized speed.")

        anchor_range = self.working_keyframes[start_index : end_index + 1]
        total_distance = cumulative_trajectory_distances(
            anchor_range, context
        )[-1]
        duration = (
            self.working_keyframes[end_index].t
            - self.working_keyframes[start_index].t
        )
        self.equalization_before = before
        self.equalization_start_id = start_id
        self.equalization_end_id = end_id
        self.equalization_changes = changes
        self.equalization_total_distance = total_distance
        self.equalization_average_speed = total_distance / duration
        self.equalization_distance_unit = context.unit
        self.working_keyframes = equalized
        self.selected_keyframe_id = end_id
        self._refresh_state()

    def _clear_equalization_state(self, *, clear_anchor: bool) -> None:
        self.equalization_before = None
        self.equalization_start_id = None
        self.equalization_end_id = None
        self.equalization_changes = ()
        self.equalization_total_distance = None
        self.equalization_average_speed = None
        self.equalization_distance_unit = None
        if clear_anchor:
            self.speed_anchor_id = None

    def _require_no_equalization_preview(self) -> None:
        if self.equalization_before is not None:
            raise ValueError("Apply or cancel the equalization preview first.")

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
