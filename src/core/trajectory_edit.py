"""GUI-independent working state for direct trajectory editing."""

import math
import uuid
from dataclasses import dataclass, replace
from typing import Any, Sequence, TypedDict

from src.core.trajectory import (
    KEYFRAME_TIME_EPSILON,
    POINT_KIND_ROUTE,
    POINT_KIND_TIMED,
    SEGMENT_MODE_LINEAR,
    SEGMENT_MODE_STEP,
    EditableKeyframe,
    Keyframe,
    SegmentKey,
    SegmentMode,
    TrajectoryDistanceContext,
    build_trajectory_properties,
    clone_keyframes,
    cumulative_trajectory_distances,
    equalize_keyframe_times,
    infer_midpoint_time,
    is_stay_segment,
    materialize_route_point_times,
    segment_mode,
    validate_keyframes,
)

_MIN_EQUALIZATION_KEYFRAMES = 3
_MIN_INDEX_SPAN_WITH_INTERMEDIATE = 2


class EditableKeyframeSnapshot(TypedDict):
    """Serializable editable-keyframe state for GUI rendering."""

    edit_id: str
    t: float
    x: float
    y: float
    arrival_mode: SegmentMode | None
    point_kind: str


class EqualizationChangeSnapshot(TypedDict):
    """One intermediate date changed by an equalization preview."""

    edit_id: str
    keyframe_number: int
    original_t: float
    proposed_t: float


class SelectedSegmentSnapshot(TypedDict):
    """Serializable details for the selected arrival segment."""

    from_id: str
    to_id: str
    mode: SegmentMode
    duration_days: float
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    is_stay: bool


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
    date_min_t: float | None
    date_max_t: float | None
    can_shift_later: bool
    selected_segment: SelectedSegmentSnapshot | None
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
    can_make_route_point: bool
    can_make_timed_location: bool
    can_make_intermediate_automatic: bool
    is_awaiting_second_location: bool
    second_location_x: float | None
    second_location_y: float | None
    is_second_location_following_cursor: bool
    can_accept_second_location: bool


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
    original_segment_modes: dict[SegmentKey, SegmentMode]
    working_segment_modes: dict[SegmentKey, SegmentMode]
    base_properties: dict[str, Any]
    distance_context: TrajectoryDistanceContext
    selected_keyframe_id: str | None
    active_date_edit_id: str | None
    date_edit_original_t: float | None
    date_edit_segment_modes_before: dict[SegmentKey, SegmentMode] | None
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
    second_location_x: float | None
    second_location_y: float | None
    is_second_location_following_cursor: bool

    @classmethod
    def create(
        cls,
        map_id: str,
        marker_id: str,
        trajectory_id: str | None,
        keyframes: Sequence[Keyframe],
        segment_modes: dict[SegmentKey, SegmentMode] | None = None,
        properties: dict[str, Any] | None = None,
        is_new: bool = False,
        distance_context: TrajectoryDistanceContext | None = None,
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
                edit_id=keyframe.keyframe_id or str(uuid.uuid4()),
                t=keyframe.t,
                x=keyframe.x,
                y=keyframe.y,
                point_kind=keyframe.point_kind,
            )
            for keyframe in keyframes
        )
        working = clone_keyframes(original)
        original_values = () if is_new else original
        modes = dict(segment_modes or {})
        for start, end in zip(working, working[1:]):
            modes.setdefault((start.edit_id, end.edit_id), SEGMENT_MODE_LINEAR)
        return cls(
            map_id=map_id,
            marker_id=marker_id,
            trajectory_id=trajectory_id,
            original_keyframes=original_values,
            working_keyframes=working,
            original_segment_modes={} if is_new else dict(modes),
            working_segment_modes=modes,
            base_properties=dict(properties or {}),
            distance_context=(distance_context or TrajectoryDistanceContext(1.0, 1.0)),
            selected_keyframe_id=None,
            active_date_edit_id=None,
            date_edit_original_t=None,
            date_edit_segment_modes_before=None,
            speed_anchor_id=None,
            equalization_before=None,
            equalization_start_id=None,
            equalization_end_id=None,
            equalization_changes=(),
            equalization_total_distance=None,
            equalization_average_speed=None,
            equalization_distance_unit=None,
            is_dirty=is_new,
            is_conflicted=False,
            validation_errors=validate_keyframes(working),
            second_location_x=(working[0].x if len(working) == 1 else None),
            second_location_y=(working[0].y if len(working) == 1 else None),
            is_second_location_following_cursor=(len(working) == 1),
        )

    @property
    def can_apply(self) -> bool:
        """Whether the working trajectory can be persisted."""
        return (
            self.is_dirty
            and not self.is_conflicted
            and not self.validation_errors
            and self.equalization_before is None
            and not self.is_awaiting_second_location
        )

    @property
    def is_awaiting_second_location(self) -> bool:
        """Whether the editor must collect a second timed location."""
        return len(self.working_keyframes) == 1

    def move_second_location(self, x: float, y: float) -> None:
        """Move the temporary guided-workflow destination marker."""
        if not self.is_awaiting_second_location:
            raise ValueError("The trajectory already has a second location.")
        self._validate_position(x, y)
        self.second_location_x = x
        self.second_location_y = y

    def accept_second_location(self, t: float) -> str:
        """Promote the temporary destination to the second timed location."""
        if not self.is_awaiting_second_location:
            raise ValueError("The trajectory already has a second location.")
        if self.is_second_location_following_cursor:
            raise ValueError("Click the map to place the destination first.")
        if not math.isfinite(t):
            raise ValueError("Location date must be finite.")
        first = self.working_keyframes[0]
        if t <= first.t + KEYFRAME_TIME_EPSILON:
            raise ValueError(
                "Move the playhead to a date later than the first location."
            )
        if self.second_location_x is None or self.second_location_y is None:
            raise ValueError("Place the destination marker first.")
        inserted = EditableKeyframe(
            edit_id=str(uuid.uuid4()),
            t=t,
            x=self.second_location_x,
            y=self.second_location_y,
            point_kind=POINT_KIND_TIMED,
        )
        self.working_keyframes.append(inserted)
        self.second_location_x = None
        self.second_location_y = None
        self.selected_keyframe_id = inserted.edit_id
        self._refresh_state()
        return inserted.edit_id

    def place_second_location(self) -> None:
        """Lock the cursor-led destination at its current temporary position."""
        if not self.is_awaiting_second_location:
            raise ValueError("The trajectory already has a second location.")
        self.is_second_location_following_cursor = False

    @property
    def is_equalization_previewing(self) -> bool:
        """Whether redistributed dates await preview confirmation."""
        return self.equalization_before is not None

    @property
    def active_date_value(self) -> float | None:
        """Return the active keyframe's proposed date, if retiming."""
        if self.active_date_edit_id is None:
            return None
        return self.working_keyframes[self._index_of(self.active_date_edit_id)].t

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
        try:
            self._materialize_routes()
        except ValueError:
            self.working_keyframes[index] = current
            raise
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
        if self.active_date_edit_id is not None and self.active_date_edit_id != edit_id:
            raise ValueError("Finish the active keyframe date edit first.")
        index = self._index_of(edit_id)
        if self.working_keyframes[index].point_kind != POINT_KIND_TIMED:
            raise ValueError("Route-point dates are calculated automatically.")
        minimum, maximum = self._date_bounds(index)
        if minimum is not None and proposed_time <= minimum:
            raise ValueError(
                f"Date must be later than {minimum:g} to keep route order."
            )
        if maximum is not None and proposed_time >= maximum:
            raise ValueError(
                f"Date must be earlier than {maximum:g} to keep route order."
            )
        current = self.working_keyframes[index]
        self.working_keyframes[index] = replace(current, t=proposed_time)
        try:
            self._materialize_routes()
        except ValueError:
            self.working_keyframes[index] = current
            raise
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
        if keyframe.point_kind != POINT_KIND_TIMED:
            raise ValueError("Convert this route point to a timed location first.")
        self.selected_keyframe_id = edit_id
        self.active_date_edit_id = edit_id
        self.date_edit_original_t = keyframe.t
        self.date_edit_segment_modes_before = dict(self.working_segment_modes)

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
        self.date_edit_segment_modes_before = None
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
        if self.date_edit_segment_modes_before is not None:
            self.working_segment_modes = dict(self.date_edit_segment_modes_before)
        self.active_date_edit_id = None
        self.date_edit_original_t = None
        self.date_edit_segment_modes_before = None
        self.selected_keyframe_id = edit_id
        self._refresh_state()
        return True

    def add_location(self, t: float, x: float, y: float) -> str:
        """Add a dated location at an explicit time and position."""
        self._require_no_equalization_preview()
        self._validate_position(x, y)
        if not math.isfinite(t):
            raise ValueError("Location date must be finite.")
        inserted = EditableKeyframe(
            edit_id=str(uuid.uuid4()),
            t=t,
            x=x,
            y=y,
            point_kind=POINT_KIND_TIMED,
        )
        end_index = next(
            (
                index
                for index, point in enumerate(self.working_keyframes)
                if point.t > t
            ),
            len(self.working_keyframes),
        )
        candidate = [
            *self.working_keyframes[:end_index],
            inserted,
            *self.working_keyframes[end_index:],
        ]
        self.working_keyframes = candidate
        self._normalize_segment_modes()
        self.selected_keyframe_id = inserted.edit_id
        self._refresh_state()
        return inserted.edit_id

    def shift_selected_and_later(self, delta_days: float) -> None:
        """Shift the selected location and all later dates by one delta."""
        self._require_no_equalization_preview()
        if self.selected_keyframe_id is None:
            raise ValueError("Select a keyframe first.")
        if not math.isfinite(delta_days):
            raise ValueError("Date shift must be finite.")
        index = self._index_of(self.selected_keyframe_id)
        if index > 0:
            shifted = self.working_keyframes[index].t + delta_days
            minimum = self.working_keyframes[index - 1].t + KEYFRAME_TIME_EPSILON
            if shifted <= minimum:
                raise ValueError(
                    "Shift would move this location before the previous one."
                )
        for item_index in range(index, len(self.working_keyframes)):
            current = self.working_keyframes[item_index]
            if current.point_kind != POINT_KIND_TIMED:
                continue
            self.working_keyframes[item_index] = replace(
                current, t=current.t + delta_days
            )
        self._materialize_routes()
        self._refresh_state()

    def shift_later_by_active_delta(self) -> None:
        """Apply the active selected-date delta to every later location."""
        if self.active_date_edit_id is None or self.date_edit_original_t is None:
            raise ValueError("Start editing a keyframe date first.")
        index = self._index_of(self.active_date_edit_id)
        current = self.working_keyframes[index]
        delta = current.t - self.date_edit_original_t
        if math.isclose(delta, 0.0, abs_tol=1e-12):
            raise ValueError("Change the selected date before shifting later dates.")
        for item_index in range(index + 1, len(self.working_keyframes)):
            later = self.working_keyframes[item_index]
            if later.point_kind != POINT_KIND_TIMED:
                continue
            self.working_keyframes[item_index] = replace(later, t=later.t + delta)
        self._materialize_routes()
        self._refresh_state()

    def set_arrival_mode(self, edit_id: str, mode: SegmentMode) -> None:
        """Set how the selected location is reached from its predecessor."""
        self._require_no_equalization_preview()
        if mode not in {SEGMENT_MODE_LINEAR, SEGMENT_MODE_STEP}:
            raise ValueError(f"Unsupported trajectory segment mode: {mode}")
        index = self._index_of(edit_id)
        if index == 0 or self.working_keyframes[index].point_kind != POINT_KIND_TIMED:
            raise ValueError("The first location has no arrival segment.")
        start_index = self._previous_timed_index(index)
        if start_index is None:
            raise ValueError("The first location has no arrival segment.")
        if mode == SEGMENT_MODE_STEP and index != start_index + 1:
            raise ValueError("A relocation leg cannot contain route points.")
        for first, second in zip(
            self.working_keyframes[start_index:index],
            self.working_keyframes[start_index + 1 : index + 1],
        ):
            self.working_segment_modes[(first.edit_id, second.edit_id)] = mode
        self.selected_keyframe_id = edit_id
        self._refresh_state()

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
        if self._mode_between(start, end) == SEGMENT_MODE_STEP:
            raise ValueError("A relocation segment has no travel midpoint.")
        inserted = EditableKeyframe(
            edit_id=str(uuid.uuid4()),
            t=infer_midpoint_time(start, end),
            x=x,
            y=y,
            point_kind=POINT_KIND_ROUTE,
        )
        candidate = [*self.working_keyframes, inserted]
        candidate.sort(key=lambda keyframe: keyframe.t)
        errors = validate_keyframes(candidate)
        if errors:
            raise ValueError(errors[0])

        previous_keyframes = self.working_keyframes
        previous_modes = dict(self.working_segment_modes)
        self.working_keyframes = candidate
        self.working_segment_modes.pop((start_id, end_id), None)
        self._normalize_segment_modes()
        try:
            self._materialize_routes()
        except ValueError:
            self.working_keyframes = previous_keyframes
            self.working_segment_modes = previous_modes
            raise
        self.selected_keyframe_id = inserted.edit_id
        self._refresh_state()
        return inserted.edit_id

    def delete_selected_keyframe(self) -> bool:
        """Delete only the selected working keyframe, including the final one."""
        self._require_no_equalization_preview()
        if self.selected_keyframe_id is None:
            return False
        index = self._index_of(self.selected_keyframe_id)
        deleted = self.working_keyframes[index]
        if deleted.point_kind == POINT_KIND_TIMED:
            if index == 0 and len(self.working_keyframes) > 1:
                self.working_keyframes[1] = replace(
                    self.working_keyframes[1], point_kind=POINT_KIND_TIMED
                )
            elif index == len(self.working_keyframes) - 1 and index > 0:
                self.working_keyframes[index - 1] = replace(
                    self.working_keyframes[index - 1], point_kind=POINT_KIND_TIMED
                )
        del self.working_keyframes[index]
        self._normalize_segment_modes()
        if self.working_keyframes:
            self._materialize_routes()
        if self.active_date_edit_id == self.selected_keyframe_id:
            self.active_date_edit_id = None
            self.date_edit_original_t = None
            self.date_edit_segment_modes_before = None
        if self.speed_anchor_id == self.selected_keyframe_id:
            self.speed_anchor_id = None
        if self.working_keyframes:
            next_index = min(index, len(self.working_keyframes) - 1)
            self.selected_keyframe_id = self.working_keyframes[next_index].edit_id
        else:
            self.selected_keyframe_id = None
        if self.is_awaiting_second_location:
            remaining = self.working_keyframes[0]
            self.second_location_x = remaining.x
            self.second_location_y = remaining.y
            self.is_second_location_following_cursor = True
        else:
            self.second_location_x = None
            self.second_location_y = None
            self.is_second_location_following_cursor = False
        self._refresh_state()
        return True

    def make_selected_route_point(self) -> None:
        """Convert one interior timed location into an automatic route point."""
        if not self._can_convert_selected_to_route():
            raise ValueError("This timed location cannot become a route point.")
        assert self.selected_keyframe_id is not None
        index = self._index_of(self.selected_keyframe_id)
        current = self.working_keyframes[index]
        self.working_keyframes[index] = replace(current, point_kind=POINT_KIND_ROUTE)
        self._materialize_routes()
        self._refresh_state()

    def make_selected_timed_location(self) -> None:
        """Promote one calculated route point to an authoritative date."""
        if self.selected_keyframe_id is None:
            raise ValueError("Select a route point first.")
        index = self._index_of(self.selected_keyframe_id)
        current = self.working_keyframes[index]
        if current.point_kind != POINT_KIND_ROUTE:
            raise ValueError("The selected point is already a timed location.")
        self.working_keyframes[index] = replace(current, point_kind=POINT_KIND_TIMED)
        self._refresh_state()

    def make_intermediate_points_automatic(self, end_id: str) -> int:
        """Convert every point between two timed endpoints to route points."""
        if self.speed_anchor_id is None:
            raise ValueError("Set a timed start location first.")
        start_index = self._index_of(self.speed_anchor_id)
        end_index = self._index_of(end_id)
        if end_index - start_index < _MIN_INDEX_SPAN_WITH_INTERMEDIATE:
            raise ValueError("The selected range has no intermediate points.")
        if (
            self.working_keyframes[start_index].point_kind != POINT_KIND_TIMED
            or self.working_keyframes[end_index].point_kind != POINT_KIND_TIMED
        ):
            raise ValueError("Automatic ranges need timed endpoints.")
        for first, second in zip(
            self.working_keyframes[start_index:end_index],
            self.working_keyframes[start_index + 1 : end_index + 1],
        ):
            if self._mode_between(first, second) == SEGMENT_MODE_STEP:
                raise ValueError("A relocation cannot contain route points.")
        changed = 0
        for index in range(start_index + 1, end_index):
            current = self.working_keyframes[index]
            if current.point_kind != POINT_KIND_ROUTE:
                self.working_keyframes[index] = replace(
                    current, point_kind=POINT_KIND_ROUTE
                )
                changed += 1
        if changed == 0:
            raise ValueError("All intermediate points are already automatic.")
        self._materialize_routes()
        self.speed_anchor_id = None
        self.selected_keyframe_id = end_id
        self._refresh_state()
        return changed

    def set_speed_anchor(self, edit_id: str) -> None:
        """Mark one stable keyframe as the equalization start anchor."""
        self._require_no_equalization_preview()
        if self.active_date_edit_id is not None:
            raise ValueError("Finish editing the keyframe date first.")
        index = self._index_of(edit_id)
        if self.working_keyframes[index].point_kind != POINT_KIND_TIMED:
            raise ValueError("Choose a timed location as the range start.")
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
        if len(self.working_keyframes) < _MIN_EQUALIZATION_KEYFRAMES:
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
        self.working_segment_modes = dict(self.original_segment_modes)
        self.selected_keyframe_id = None
        self.active_date_edit_id = None
        self.date_edit_original_t = None
        self.date_edit_segment_modes_before = None
        self.speed_anchor_id = None
        self._clear_equalization_state(clear_anchor=True)
        self.is_conflicted = False
        if len(self.working_keyframes) == 1:
            self.second_location_x = self.working_keyframes[0].x
            self.second_location_y = self.working_keyframes[0].y
            self.is_second_location_following_cursor = True
        else:
            self.second_location_x = None
            self.second_location_y = None
            self.is_second_location_following_cursor = False
        self._refresh_state()

    def to_keyframes(self) -> list[Keyframe]:
        """Return an independent persistence-ready working trajectory."""
        return [
            Keyframe(
                t=keyframe.t,
                x=keyframe.x,
                y=keyframe.y,
                point_kind=keyframe.point_kind,
                keyframe_id=keyframe.edit_id,
            )
            for keyframe in self.working_keyframes
        ]

    def to_properties(self) -> dict[str, Any]:
        """Return complete properties with current trajectory metadata."""
        return build_trajectory_properties(
            self.base_properties,
            self.to_keyframes(),
            self.working_segment_modes,
        )

    def to_snapshot(
        self, *, playhead_time: float | None = None
    ) -> TrajectoryEditSnapshot:
        """Return immutable-by-convention serialized state for the GUI."""
        selected_index: int | None = None
        if self.selected_keyframe_id is not None:
            selected_index = self._index_of(self.selected_keyframe_id)
        proposed_time: float | None = None
        if self.active_date_edit_id is not None:
            proposed_time = self.working_keyframes[
                self._index_of(self.active_date_edit_id)
            ].t
        date_min: float | None = None
        date_max: float | None = None
        if selected_index is not None:
            date_min, date_max = self._date_bounds(selected_index)
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
            and selected_index - speed_anchor_index
            >= _MIN_INDEX_SPAN_WITH_INTERMEDIATE
            and self.working_keyframes[speed_anchor_index].point_kind
            == POINT_KIND_TIMED
            and self.working_keyframes[selected_index].point_kind == POINT_KIND_TIMED
        )
        selected_segment: SelectedSegmentSnapshot | None = None
        if (
            selected_index is not None
            and selected_index > 0
            and self.working_keyframes[selected_index].point_kind == POINT_KIND_TIMED
        ):
            start_index = self._previous_timed_index(selected_index)
            assert start_index is not None
            segment_start = self.working_keyframes[start_index]
            segment_end = self.working_keyframes[selected_index]
            selected_segment = {
                "from_id": segment_start.edit_id,
                "to_id": segment_end.edit_id,
                "mode": self._mode_between(segment_start, segment_end),
                "duration_days": segment_end.t - segment_start.t,
                "start_x": segment_start.x,
                "start_y": segment_start.y,
                "end_x": segment_end.x,
                "end_y": segment_end.y,
                "is_stay": is_stay_segment(segment_start, segment_end),
            }
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
                    "arrival_mode": (
                        None
                        if index == 0
                        else self._mode_between(
                            self.working_keyframes[index - 1], keyframe
                        )
                    ),
                    "point_kind": keyframe.point_kind,
                }
                for index, keyframe in enumerate(self.working_keyframes)
            ],
            "selected_keyframe_id": self.selected_keyframe_id,
            "selected_keyframe_index": selected_index,
            "active_date_edit_id": self.active_date_edit_id,
            "is_date_editing": self.active_date_edit_id is not None,
            "date_edit_original_t": self.date_edit_original_t,
            "date_edit_proposed_t": proposed_time,
            "date_edit_delta": date_delta,
            "date_min_t": date_min,
            "date_max_t": date_max,
            "can_shift_later": (
                selected_index is not None
                and selected_index < len(self.working_keyframes) - 1
            ),
            "selected_segment": selected_segment,
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
                and len(self.working_keyframes) >= _MIN_EQUALIZATION_KEYFRAMES
            ),
            "keyframe_count": len(self.working_keyframes),
            "is_dirty": self.is_dirty,
            "is_conflicted": self.is_conflicted,
            "validation_errors": list(self.validation_errors),
            "midpoint_errors": self._midpoint_errors(),
            "can_apply": self.can_apply,
            "can_make_route_point": self._can_convert_selected_to_route(),
            "can_make_timed_location": (
                selected_index is not None
                and self.working_keyframes[selected_index].point_kind
                == POINT_KIND_ROUTE
            ),
            "can_make_intermediate_automatic": can_equalize_to_selected,
            "is_awaiting_second_location": self.is_awaiting_second_location,
            "second_location_x": self.second_location_x,
            "second_location_y": self.second_location_y,
            "is_second_location_following_cursor": (
                self.is_second_location_following_cursor
            ),
            "can_accept_second_location": (
                self.is_awaiting_second_location
                and self.second_location_x is not None
                and self.second_location_y is not None
                and not self.is_second_location_following_cursor
                and playhead_time is not None
                and playhead_time
                > self.working_keyframes[0].t + KEYFRAME_TIME_EPSILON
            ),
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
        if end_index - start_index < _MIN_INDEX_SPAN_WITH_INTERMEDIATE:
            raise ValueError("Equalize Speed needs at least one intermediate keyframe.")
        for start, end in zip(
            self.working_keyframes[start_index:end_index],
            self.working_keyframes[start_index + 1 : end_index + 1],
        ):
            if self._mode_between(start, end) == SEGMENT_MODE_STEP:
                raise ValueError(
                    "Speed equalization is unavailable across a relocation."
                )
            if is_stay_segment(start, end):
                raise ValueError("Speed equalization is unavailable across a stay.")

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
        total_distance = cumulative_trajectory_distances(anchor_range, context)[-1]
        duration = (
            self.working_keyframes[end_index].t - self.working_keyframes[start_index].t
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
        for start, end in zip(self.working_keyframes, self.working_keyframes[1:]):
            if self._mode_between(start, end) == SEGMENT_MODE_STEP:
                errors[self.midpoint_key(start.edit_id, end.edit_id)] = (
                    "A relocation segment has no travel midpoint."
                )
                continue
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
                    errors[self.midpoint_key(start.edit_id, end.edit_id)] = validation[
                        0
                    ]
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
        self._normalize_segment_modes()
        self.validation_errors = validate_keyframes(self.working_keyframes)
        original_values = [
            (
                keyframe.edit_id,
                keyframe.t,
                keyframe.x,
                keyframe.y,
                keyframe.point_kind,
            )
            for keyframe in self.original_keyframes
        ]
        working_values = [
            (
                keyframe.edit_id,
                keyframe.t,
                keyframe.x,
                keyframe.y,
                keyframe.point_kind,
            )
            for keyframe in self.working_keyframes
        ]
        self.is_dirty = (
            working_values != original_values
            or self.working_segment_modes != self.original_segment_modes
        )

    def _date_bounds(self, index: int) -> tuple[float | None, float | None]:
        previous_index = self._previous_timed_index(index)
        next_index = self._next_timed_index(index)
        minimum = (
            self.working_keyframes[previous_index].t + KEYFRAME_TIME_EPSILON
            if previous_index is not None
            else None
        )
        maximum = (
            self.working_keyframes[next_index].t - KEYFRAME_TIME_EPSILON
            if next_index is not None
            else None
        )
        return minimum, maximum

    def _previous_timed_index(self, index: int) -> int | None:
        for candidate in range(index - 1, -1, -1):
            if self.working_keyframes[candidate].point_kind == POINT_KIND_TIMED:
                return candidate
        return None

    def _next_timed_index(self, index: int) -> int | None:
        for candidate in range(index + 1, len(self.working_keyframes)):
            if self.working_keyframes[candidate].point_kind == POINT_KIND_TIMED:
                return candidate
        return None

    def _materialize_routes(self) -> None:
        self.working_keyframes = materialize_route_point_times(
            self.working_keyframes, self.distance_context
        )

    def _can_convert_selected_to_route(self) -> bool:
        if self.selected_keyframe_id is None:
            return False
        index = self._index_of(self.selected_keyframe_id)
        if (
            index == 0
            or index == len(self.working_keyframes) - 1
            or self.working_keyframes[index].point_kind != POINT_KIND_TIMED
        ):
            return False
        previous_index = self._previous_timed_index(index)
        next_index = self._next_timed_index(index)
        if previous_index is None or next_index is None:
            return False
        adjacent = zip(
            self.working_keyframes[previous_index:next_index],
            self.working_keyframes[previous_index + 1 : next_index + 1],
        )
        return all(
            self._mode_between(start, end) == SEGMENT_MODE_LINEAR
            for start, end in adjacent
        )

    def _mode_between(
        self, start: EditableKeyframe, end: EditableKeyframe
    ) -> SegmentMode:
        return segment_mode(start, end, self.working_segment_modes)

    def _normalize_segment_modes(self) -> None:
        adjacent = {
            (start.edit_id, end.edit_id)
            for start, end in zip(self.working_keyframes, self.working_keyframes[1:])
        }
        self.working_segment_modes = {
            pair: self.working_segment_modes.get(pair, SEGMENT_MODE_LINEAR)
            for pair in adjacent
        }
