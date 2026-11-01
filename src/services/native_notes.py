"""Versioned native note metadata alongside ordinary editable Markdown fields."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml  # type: ignore[import-untyped]  # PyYAML has no bundled typing metadata.

from src.core.entities import Entity
from src.core.events import Event


def note_frontmatter(
    item: Entity | Event,
    relations: list[dict[str, Any]],
    readable_relations: list[dict[str, str]],
    context: dict[str, Any],
) -> list[str]:
    """Serialize all keys and scalar types using safe YAML rather than quoting."""
    record = item.to_dict()
    meta: dict[str, Any] = {
        "title": item.name,
        "type": item.type,
        "tags": list(item.tags),
        "uid": item.id,
        "created": item.created_at,
        "modified": item.modified_at,
        "source": "ProjektKraken",
        "attributes": deepcopy(
            {
                key: value
                for key, value in item.attributes.items()
                if not key.startswith("_")
            }
        ),
    }
    if isinstance(item, Event):
        meta.update(lore_date=item.lore_date, lore_duration=item.lore_duration)
    meta["kraken"] = {
        "schema": 1,
        "kind": "events" if isinstance(item, Event) else "entities",
        "record": record,
        "relations": relations,
        "context": context,
        "related_projection": readable_relations,
    }
    return [
        "---",
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).rstrip(),
        "---",
        "",
    ]


def read_native_note(
    meta: dict[str, Any],
    description: str,
    relations: list[dict[str, str]],
) -> dict[str, Any]:
    """Readable user fields are editable; structured semantics stay authoritative."""
    native = meta["kraken"]
    if not isinstance(native, dict) or native.get("schema") != 1:
        raise ValueError("Unsupported native Kraken note metadata.")
    kind = native.get("kind")
    if kind not in {"entities", "events"} or not isinstance(native.get("record"), dict):
        raise ValueError("Invalid native Kraken record.")
    row = deepcopy(native["record"])
    if meta.get("uid") != row.get("id"):
        raise ValueError("Native note identity conflicts with its readable uid.")
    for field in ("lore_date", "lore_duration"):
        if field in meta and meta[field] != row.get(field):
            raise ValueError(
                f"Readable {field} conflicts with native timing; review it."
            )
    projected = [
        {"rel_type": item["rel_type"], "target_name": item["name"]}
        for item in native.get("related_projection", [])
    ]
    if relations != projected:
        raise ValueError("Readable Related links conflict with native Relations.")
    attributes = meta.get("attributes", {})
    if not isinstance(attributes, dict):
        raise ValueError("Note attributes must be a YAML mapping.")
    internal = {
        key: value
        for key, value in row.get("attributes", {}).items()
        if key.startswith("_")
    }
    if any(not isinstance(key, str) or key.startswith("_") for key in attributes):
        raise ValueError(
            "Editable note attributes cannot replace native internal keys."
        )
    if description == native.get("body_projection"):
        description = row.get("description", "")
    row.update(
        name=meta.get("title", row.get("name")),
        type=meta.get("type", row.get("type")),
        tags=meta.get("tags", []),
        description=description,
        attributes={**internal, **attributes},
        relations=deepcopy(native.get("relations", [])),
        _transfer_context=deepcopy(native.get("context", {})),
    )
    row["_native_kind"] = kind
    return row


def finalize_note(text: str) -> str:
    """Keep generated stat blocks separate from the editable narrative on readback."""
    import frontmatter  # type: ignore[import-untyped]  # Package has no py.typed marker.

    from src.services.markdown_parser import parse_markdown

    post = frontmatter.loads(text)
    post.metadata["kraken"]["body_projection"] = parse_markdown(text).description
    header = yaml.safe_dump(post.metadata, allow_unicode=True, sort_keys=False).rstrip()
    return "---\n" + header + "\n---\n\n" + post.content + "\n"
