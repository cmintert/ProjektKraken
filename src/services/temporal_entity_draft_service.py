"""Pure preparation of source-aware entity edits from captured draft values.

This service has no storage or UI dependencies. The caller owns draft revisions,
dialogs, submission and acknowledgement; preparation never changes its inputs.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class TemporalEntityDraftSnapshot:
    """Values captured together before resolving any modal ownership choices."""

    entity_id: str
    lore_time: float
    generation: int
    revision: int
    state: dict[str, Any]
    baseline_metadata: dict[str, Any]
    name: str
    entity_type: str
    description: str
    attributes: dict[str, Any]
    tags: list[str]
    sheet_layout: Any
    displayed_sheet_layout: Any
    description_event: dict[str, Any] | None
    summary_changed: bool
    summary_data: dict[str, Any] | None


@dataclass(frozen=True)
class NoChanges:
    """The captured draft matches its comparison values."""


@dataclass(frozen=True)
class ChoiceRequired:
    """An added or removed visible attribute needs an explicit author decision."""

    key: str
    kind: Literal["addition", "removal"]


@dataclass(frozen=True)
class PreparedSave:
    """Independent patch and metadata payloads ready for revision capture."""

    patches: list[dict[str, Any]]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PendingTemporalSubmission:
    """Owned copies of intent that can be cleared after its acknowledgement."""

    metadata: dict[str, Any]
    description_event: dict[str, Any] | None

    def __post_init__(self) -> None:
        """Keep transport payloads and live edits independent of pending intent."""
        object.__setattr__(self, "metadata", deepcopy(self.metadata))
        object.__setattr__(self, "description_event", deepcopy(self.description_event))


class TemporalEntityDraftService:
    """Compare a captured entity draft without resolving dates or executing edits."""

    @staticmethod
    def prepare(
        snapshot: TemporalEntityDraftSnapshot,
        choices: dict[str, dict[str, Any]],
    ) -> NoChanges | ChoiceRequired | PreparedSave:
        """Return the next missing choice or an independent complete payload.

        Choices are the existing dialog results: a destination for an addition,
        or a complete removal patch. No partial payload escapes preparation.
        """
        draft = deepcopy(snapshot)
        decisions = deepcopy(choices)
        original = _visible(draft.state["attributes"])
        current = _visible(draft.attributes)
        patches = _description_patches(draft)
        for key, value in current.items():
            if key in original and original[key] == value:
                continue
            patch = {"field": "attribute", "key": key, "action": "set", "value": value}
            if key not in original:
                if key not in decisions:
                    return ChoiceRequired(key, "addition")
                patch.update(decisions[key])
            patches.append(patch)
        for key in original.keys() - current.keys():
            if key not in decisions:
                return ChoiceRequired(key, "removal")
            patches.append(decisions[key])
        metadata = _metadata(draft, current.keys() == original.keys())
        if not patches and not metadata:
            return NoChanges()
        return PreparedSave(patches, metadata)


def _visible(attributes: dict[str, Any]) -> dict[str, Any]:
    """Exclude baseline-only hidden metadata from temporal field edits."""
    return {key: value for key, value in attributes.items() if not key.startswith("_")}


def _description_patches(draft: TemporalEntityDraftSnapshot) -> list[dict[str, Any]]:
    """Preserve explicit dated intent even when the description is unchanged."""
    if (
        draft.description == draft.state["description"]
        and draft.description_event is None
    ):
        return []
    patch = {"field": "description", "action": "set", "value": draft.description}
    if draft.description_event is not None:
        patch.update({"scope": "dated", **draft.description_event})
    return [patch]


def _metadata(draft: TemporalEntityDraftSnapshot, same_keys: bool) -> dict[str, Any]:
    """Keep baseline metadata edits distinct from visible temporal patches."""
    metadata: dict[str, Any] = {}
    if draft.name != draft.baseline_metadata["name"]:
        metadata["name"] = draft.name
    if draft.entity_type != draft.baseline_metadata["type"]:
        metadata["type"] = draft.entity_type
    hidden: dict[str, Any] = {}
    if draft.tags != list(draft.baseline_metadata.get("_tags") or []):
        hidden["_tags"] = draft.tags
    if draft.sheet_layout != draft.displayed_sheet_layout and same_keys:
        hidden["_sheet_layout"] = draft.sheet_layout
    if draft.summary_changed:
        hidden["_summary_data"] = draft.summary_data
    if hidden:
        metadata["hidden_attributes"] = hidden
    return metadata
