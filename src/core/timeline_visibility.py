"""Shared presentation choices for Follow Event dependency connections."""

from enum import StrEnum


class DependencyVisibility(StrEnum):
    """Choose which completed connections the timeline paints."""

    ALL = "all"
    SELECTED = "selected"
    TRAIL = "trail"
    OFF = "off"


DEPENDENCY_VISIBILITY_KEY = "timeline/dependency_visibility"
LEGACY_DEPENDENCY_VISIBILITY_KEY = "timeline/show_dependencies"
DEPENDENCY_VISIBILITY_LABELS = {
    DependencyVisibility.ALL: "All",
    DependencyVisibility.SELECTED: "Selected",
    DependencyVisibility.TRAIL: "Show dependency trail",
    DependencyVisibility.OFF: "Off",
}


def dependency_visibility(value: object) -> DependencyVisibility:
    """Normalize a persisted choice, recovering invalid values to Selected."""
    if not isinstance(value, str):
        return DependencyVisibility.SELECTED
    try:
        return DependencyVisibility(value)
    except ValueError:
        return DependencyVisibility.SELECTED
