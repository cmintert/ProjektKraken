"""User-visible transfer capabilities and serializable exchange contracts."""

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class TransferFormat:
    """Describe an actual operation, including its preservation boundary."""

    key: str
    title: str
    extensions: tuple[str, ...]
    imports: bool
    exports: bool
    description: str
    limitation: str

    @property
    def file_filter(self) -> str:
        """Return the native file-picker filter for this format."""
        return f"{self.title} ({' '.join('*' + e for e in self.extensions)})"


FORMATS = (
    TransferFormat(
        "json",
        "Lore JSON",
        (".json",),
        True,
        True,
        "Exchange entities, events, relations, tags and custom attributes.",
        "Re-importable lore data. Asset files and world settings are excluded.",
    ),
    TransferFormat(
        "csv",
        "Lore CSV tables",
        (".csv", ".tsv"),
        True,
        True,
        "Exchange entity, event or relation tables with spreadsheets.",
        "Map columns before import. Tags and attributes use JSON cells; no assets.",
    ),
    TransferFormat(
        "notes",
        "Markdown / Obsidian notes",
        (".md",),
        True,
        True,
        "Import notes or export linked entity and event notes with frontmatter.",
        "Supported frontmatter and prose can be re-imported; not a world backup.",
    ),
    TransferFormat(
        "markdown",
        "Longform Markdown",
        (".md",),
        False,
        True,
        "Publish the authored longform sequence as a readable document.",
        "Document export does not preserve complete world structure.",
    ),
    TransferFormat(
        "docx",
        "Longform Word document",
        (".docx",),
        False,
        True,
        "Publish an editable document with headings, tables and images.",
        "Publishing only. Word document import is not supported.",
    ),
    TransferFormat(
        "pdf",
        "Longform PDF",
        (".pdf",),
        False,
        True,
        "Publish a paginated document for reading and printing.",
        "Publishing only. PDF import is not supported.",
    ),
    TransferFormat(
        "world",
        "Portable world",
        (".krakenworld",),
        True,
        True,
        "Transfer a complete world: manifest, database and assets.",
        "Import creates a new world. Local preferences and backups are excluded.",
    ),
)

FORMAT_BY_KEY = {item.key: item for item in FORMATS}
LORE_KINDS = ("entities", "events", "relations")
EXCHANGE_VERSION = 1
WORLD_TAB = 2
REFERENCE_TAB = 3

LORE_JSON_EXAMPLE = {
    "exchange_version": EXCHANGE_VERSION,
    "entities": [
        {
            "id": "00000000-0000-4000-8000-000000000101",
            "type": "character",
            "name": "Aria Voss",
            "description": "Navigator of the survey vessel Horizon.",
            "tags": ["crew", "protagonist"],
            "attributes": {
                "occupation": "Navigator",
                "aliases": ["Starfinder"],
                "active": True,
            },
            "created_at": 1767225600.0,
            "modified_at": 1767225600.0,
        }
    ],
    "events": [
        {
            "id": "00000000-0000-4000-8000-000000000102",
            "type": "discovery",
            "name": "The Signal",
            "lore_date": "23 AUG 1895",
            "lore_duration": 0.5,
            "description": "Aria detects a repeating signal beyond the rim.",
            "tags": ["mystery", "first-contact"],
            "attributes": {
                "location": "Outer Rim",
                "certainty": 0.8,
            },
            "created_at": 1767225600.0,
            "modified_at": 1767225600.0,
        }
    ],
    "relations": [
        {
            "id": "00000000-0000-4000-8000-000000000103",
            "source_id": "00000000-0000-4000-8000-000000000101",
            "target_id": "00000000-0000-4000-8000-000000000102",
            "rel_type": "participated_in",
            "attributes": {"role": "discoverer"},
            "created_at": 1767225600.0,
        }
    ],
}
LORE_JSON_EXAMPLE_TEXT = json.dumps(LORE_JSON_EXAMPLE, indent=2, ensure_ascii=False)


def lore_file_filter() -> str:
    """Use the capability catalog for the combined lore input filter."""
    formats = [item for item in FORMATS if item.imports and item.key != "world"]
    extensions = " ".join("*" + ext for item in formats for ext in item.extensions)
    return f"Supported lore ({extensions});;" + ";;".join(
        item.file_filter for item in formats
    )
