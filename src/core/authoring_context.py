"""Serializable value objects for deterministic authoring context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

ObjectType = Literal["entity", "event", "map", "attachment"]
TemporalKind = Literal["persistent", "interval", "instant"]


@dataclass(frozen=True)
class ContextItem:
    """A named world item referenced by authoring context."""

    id: str
    object_type: ObjectType
    name: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {
            "id": self.id,
            "object_type": self.object_type,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextItem":
        """Restore a context item from serialized data."""
        raw_type = str(data.get("object_type", "entity"))
        object_type = cast(
            ObjectType,
            raw_type
            if raw_type in {"entity", "event", "map", "attachment"}
            else "entity",
        )
        return cls(str(data["id"]), object_type, str(data["name"]))


@dataclass(frozen=True)
class ContextEvent:
    """A compact chronological Event reference."""

    id: str
    name: str
    lore_date: float
    event_type: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {
            "id": self.id,
            "name": self.name,
            "lore_date": self.lore_date,
            "event_type": self.event_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextEvent":
        """Restore an Event reference from serialized data."""
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            lore_date=float(data["lore_date"]),
            event_type=str(data.get("event_type", "generic")),
        )


@dataclass(frozen=True)
class ContextRelation:
    """A resolved authored relationship relevant to the context."""

    id: str
    source: ContextItem
    target: ContextItem
    rel_type: str
    hop: int
    temporal_kind: TemporalKind
    valid_from: float | None = None
    valid_to: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {
            "id": self.id,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "rel_type": self.rel_type,
            "hop": self.hop,
            "temporal_kind": self.temporal_kind,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextRelation":
        """Restore a context relation from serialized data."""
        raw_kind = str(data.get("temporal_kind", "persistent"))
        kind = cast(
            TemporalKind,
            raw_kind
            if raw_kind in {"persistent", "interval", "instant"}
            else "persistent",
        )
        return cls(
            id=str(data["id"]),
            source=ContextItem.from_dict(dict(data["source"])),
            target=ContextItem.from_dict(dict(data["target"])),
            rel_type=str(data["rel_type"]),
            hop=int(data.get("hop", 0)),
            temporal_kind=kind,
            valid_from=(
                float(data["valid_from"])
                if data.get("valid_from") is not None
                else None
            ),
            valid_to=(
                float(data["valid_to"])
                if data.get("valid_to") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class SpatialAuthoringContext:
    """Grounded spatial context for one Event or location anchor."""

    anchor: ContextItem
    text: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {"anchor": self.anchor.to_dict(), "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpatialAuthoringContext":
        """Restore a spatial context from serialized data."""
        return cls(
            anchor=ContextItem.from_dict(dict(data["anchor"])),
            text=str(data["text"]),
        )


@dataclass(frozen=True)
class ContextAttribute:
    """One deterministic, display-safe structured Entity attribute."""

    name: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {"name": self.name, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextAttribute":
        """Restore an Entity attribute."""
        return cls(name=str(data["name"]), value=data.get("value"))


@dataclass(frozen=True)
class ContextMapAppearance:
    """A durable association between an Entity and a map feature."""

    map_id: str
    map_name: str
    feature_type: str
    marker_label: str | None = None
    parent_maps: tuple[ContextItem, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {
            "map_id": self.map_id,
            "map_name": self.map_name,
            "feature_type": self.feature_type,
            "marker_label": self.marker_label,
            "parent_maps": [item.to_dict() for item in self.parent_maps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextMapAppearance":
        """Restore a map appearance."""
        return cls(
            map_id=str(data["map_id"]),
            map_name=str(data["map_name"]),
            feature_type=str(data.get("feature_type", "point")),
            marker_label=(
                str(data["marker_label"])
                if data.get("marker_label") is not None
                else None
            ),
            parent_maps=tuple(
                ContextItem.from_dict(dict(item))
                for item in data.get("parent_maps", [])
            ),
        )


@dataclass(frozen=True)
class ContextTag:
    """One user-facing tag, independent of its private storage representation."""

    id: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {"id": self.id, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextTag":
        """Restore a public tag reference."""
        return cls(id=str(data.get("id", "")), name=str(data["name"]))


@dataclass(frozen=True)
class ContextEventAppearance:
    """An Event in which an Entity has one or more authored roles."""

    event: ContextEvent
    roles: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {"event": self.event.to_dict(), "roles": list(self.roles)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextEventAppearance":
        """Restore an Event appearance."""
        return cls(
            event=ContextEvent.from_dict(dict(data["event"])),
            roles=tuple(str(item) for item in data.get("roles", [])),
        )


@dataclass(frozen=True)
class ContextCoAppearance:
    """Evidence that two Entities have structured roles in shared Events."""

    item: ContextItem
    events: tuple[ContextEvent, ...]
    event_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {
            "item": self.item.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "event_count": self.event_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextCoAppearance":
        """Restore structured Event co-appearance evidence."""
        return cls(
            item=ContextItem.from_dict(dict(data["item"])),
            events=tuple(
                ContextEvent.from_dict(dict(event))
                for event in data.get("events", [])
            ),
            event_count=int(data.get("event_count", 0)),
        )


@dataclass(frozen=True)
class ContextSharedAssociation:
    """A weak deterministic association with explicit supporting labels."""

    item: ContextItem
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {"item": self.item.to_dict(), "evidence": list(self.evidence)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextSharedAssociation":
        """Restore a supported weak association."""
        return cls(
            item=ContextItem.from_dict(dict(data["item"])),
            evidence=tuple(str(item) for item in data.get("evidence", [])),
        )


@dataclass(frozen=True)
class ContextAttachment:
    """Authored caption metadata for an Entity attachment."""

    id: str
    caption: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {"id": self.id, "caption": self.caption}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextAttachment":
        """Restore attachment caption metadata."""
        return cls(id=str(data["id"]), caption=str(data["caption"]))


@dataclass(frozen=True)
class EventAuthoringContext:
    """Complete bounded factual context for authoring one Event."""

    event_id: str
    context_date: float
    participants: tuple[ContextItem, ...] = ()
    locations: tuple[ContextItem, ...] = ()
    mentions: tuple[ContextItem, ...] = ()
    previous_events: tuple[ContextEvent, ...] = ()
    concurrent_events: tuple[ContextEvent, ...] = ()
    next_events: tuple[ContextEvent, ...] = ()
    direct_relations: tuple[ContextRelation, ...] = ()
    neighborhood_relations: tuple[ContextRelation, ...] = ()
    spatial: tuple[SpatialAuthoringContext, ...] = ()
    omitted_counts: tuple[tuple[str, int], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation for queued Qt delivery."""
        return {
            "event_id": self.event_id,
            "context_date": self.context_date,
            "participants": [item.to_dict() for item in self.participants],
            "locations": [item.to_dict() for item in self.locations],
            "mentions": [item.to_dict() for item in self.mentions],
            "previous_events": [item.to_dict() for item in self.previous_events],
            "concurrent_events": [
                item.to_dict() for item in self.concurrent_events
            ],
            "next_events": [item.to_dict() for item in self.next_events],
            "direct_relations": [item.to_dict() for item in self.direct_relations],
            "neighborhood_relations": [
                item.to_dict() for item in self.neighborhood_relations
            ],
            "spatial": [item.to_dict() for item in self.spatial],
            "omitted_counts": dict(self.omitted_counts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventAuthoringContext":
        """Restore an Event context from serialized data."""
        omitted = data.get("omitted_counts") or {}
        return cls(
            event_id=str(data["event_id"]),
            context_date=float(data["context_date"]),
            participants=tuple(
                ContextItem.from_dict(dict(item))
                for item in data.get("participants", [])
            ),
            locations=tuple(
                ContextItem.from_dict(dict(item)) for item in data.get("locations", [])
            ),
            mentions=tuple(
                ContextItem.from_dict(dict(item)) for item in data.get("mentions", [])
            ),
            previous_events=tuple(
                ContextEvent.from_dict(dict(item))
                for item in data.get("previous_events", [])
            ),
            concurrent_events=tuple(
                ContextEvent.from_dict(dict(item))
                for item in data.get("concurrent_events", [])
            ),
            next_events=tuple(
                ContextEvent.from_dict(dict(item))
                for item in data.get("next_events", [])
            ),
            direct_relations=tuple(
                ContextRelation.from_dict(dict(item))
                for item in data.get("direct_relations", [])
            ),
            neighborhood_relations=tuple(
                ContextRelation.from_dict(dict(item))
                for item in data.get("neighborhood_relations", [])
            ),
            spatial=tuple(
                SpatialAuthoringContext.from_dict(dict(item))
                for item in data.get("spatial", [])
            ),
            omitted_counts=tuple(
                sorted((str(key), int(value)) for key, value in dict(omitted).items())
            ),
        )


@dataclass(frozen=True)
class EntityAuthoringContext:
    """Complete bounded durable context for authoring one Entity."""

    entity_id: str
    attributes: tuple[ContextAttribute, ...] = ()
    tags: tuple[ContextTag, ...] = ()
    event_appearances: tuple[ContextEventAppearance, ...] = ()
    mentions: tuple[ContextEvent, ...] = ()
    linked_references: tuple[ContextRelation, ...] = ()
    direct_relations: tuple[ContextRelation, ...] = ()
    temporal_history: tuple[ContextRelation, ...] = ()
    neighborhood_relations: tuple[ContextRelation, ...] = ()
    map_appearances: tuple[ContextMapAppearance, ...] = ()
    co_appearances: tuple[ContextCoAppearance, ...] = ()
    shared_tags: tuple[ContextSharedAssociation, ...] = ()
    shared_maps: tuple[ContextSharedAssociation, ...] = ()
    attachments: tuple[ContextAttachment, ...] = ()
    omitted_counts: tuple[tuple[str, int], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation for queued Qt delivery."""
        return {
            "entity_id": self.entity_id,
            "attributes": [item.to_dict() for item in self.attributes],
            "tags": [item.to_dict() for item in self.tags],
            "event_appearances": [
                item.to_dict() for item in self.event_appearances
            ],
            "mentions": [item.to_dict() for item in self.mentions],
            "linked_references": [
                item.to_dict() for item in self.linked_references
            ],
            "direct_relations": [item.to_dict() for item in self.direct_relations],
            "temporal_history": [item.to_dict() for item in self.temporal_history],
            "neighborhood_relations": [
                item.to_dict() for item in self.neighborhood_relations
            ],
            "map_appearances": [
                item.to_dict() for item in self.map_appearances
            ],
            "co_appearances": [item.to_dict() for item in self.co_appearances],
            "shared_tags": [item.to_dict() for item in self.shared_tags],
            "shared_maps": [item.to_dict() for item in self.shared_maps],
            "attachments": [item.to_dict() for item in self.attachments],
            "omitted_counts": dict(self.omitted_counts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityAuthoringContext":
        """Restore an Entity context from serialized data."""
        omitted = data.get("omitted_counts") or {}
        return cls(
            entity_id=str(data["entity_id"]),
            attributes=tuple(
                ContextAttribute.from_dict(dict(item))
                for item in data.get("attributes", [])
            ),
            tags=tuple(
                ContextTag.from_dict(dict(item)) for item in data.get("tags", [])
            ),
            event_appearances=tuple(
                (
                    ContextEventAppearance.from_dict(dict(item))
                    if "event" in item
                    else ContextEventAppearance(
                        event=ContextEvent.from_dict(dict(item)), roles=()
                    )
                )
                for item in data.get("event_appearances", [])
            ),
            mentions=tuple(
                ContextEvent.from_dict(dict(item))
                for item in data.get("mentions", [])
            ),
            linked_references=tuple(
                ContextRelation.from_dict(dict(item))
                for item in data.get("linked_references", [])
            ),
            direct_relations=tuple(
                ContextRelation.from_dict(dict(item))
                for item in data.get("direct_relations", [])
            ),
            temporal_history=tuple(
                ContextRelation.from_dict(dict(item))
                for item in data.get("temporal_history", [])
            ),
            neighborhood_relations=tuple(
                ContextRelation.from_dict(dict(item))
                for item in data.get("neighborhood_relations", [])
            ),
            map_appearances=tuple(
                ContextMapAppearance.from_dict(dict(item))
                for item in data.get("map_appearances", [])
            ),
            co_appearances=tuple(
                ContextCoAppearance.from_dict(dict(item))
                for item in data.get("co_appearances", [])
            ),
            shared_tags=tuple(
                ContextSharedAssociation.from_dict(dict(item))
                for item in data.get("shared_tags", [])
            ),
            shared_maps=tuple(
                ContextSharedAssociation.from_dict(dict(item))
                for item in data.get("shared_maps", [])
            ),
            attachments=tuple(
                ContextAttachment.from_dict(dict(item))
                for item in data.get("attachments", [])
            ),
            omitted_counts=tuple(
                sorted((str(key), int(value)) for key, value in dict(omitted).items())
            ),
        )
