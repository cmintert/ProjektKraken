"""Markdown Parser Module.

Stateless utility for parsing Obsidian-compatible Markdown files into
structured data suitable for import into Projekt Kraken.

Extracts three distinct zones from a Markdown file:
- YAML Frontmatter (metadata and user-defined attributes)
- TL;DR Block (summary text from blockquote)
- Narrative Body (description text)
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import frontmatter

logger = logging.getLogger(__name__)

# Pattern for summary blockquote: > **Summary**: <text>
_SUMMARY_PATTERN = re.compile(
    r"^>\s*\*\*Summary\*\*:\s*(.+)$", re.MULTILINE
)

# Pattern for wiki-links: [[Name]]
_WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")

# Pattern for related entries: - rel_type: [[Name]]
_RELATED_ENTRY_PATTERN = re.compile(
    r"^-\s*([^:]+):\s*\[\[([^\]]+)\]\]\s*$", re.MULTILINE
)


@dataclass
class ParsedMarkdown:
    """Result of parsing a single Markdown file.

    Attributes:
        yaml_metadata: All key-value pairs from YAML frontmatter.
        tl_dr_block: Extracted summary text, or empty string.
        description: Narrative body text (description content).
        relations: List of dicts with 'rel_type' and 'target_name'.
        wiki_links: List of wiki-link target names found in the body.

    """

    yaml_metadata: Dict[str, Any] = field(default_factory=dict)
    tl_dr_block: str = ""
    description: str = ""
    relations: List[Dict[str, str]] = field(default_factory=list)
    wiki_links: List[str] = field(default_factory=list)


def parse_markdown(text: str) -> ParsedMarkdown:
    """Parse an Obsidian-compatible Markdown string into structured data.

    Extracts YAML frontmatter, summary blockquote, description body,
    related entries, and wiki-links.

    Args:
        text: Raw Markdown content string.

    Returns:
        ParsedMarkdown with extracted zones.

    """
    result = ParsedMarkdown()

    # Parse frontmatter using python-frontmatter
    post = frontmatter.loads(text)
    result.yaml_metadata = dict(post.metadata)

    body = post.content.strip()

    # Extract summary blockquote
    summary_match = _SUMMARY_PATTERN.search(body)
    if summary_match:
        result.tl_dr_block = summary_match.group(1).strip()
        # Remove the summary line from the body
        body = _SUMMARY_PATTERN.sub("", body).strip()

    # Extract ## Related section
    related_section_pattern = re.compile(
        r"^##\s+Related\s*\n((?:-\s*.+\n?)*)", re.MULTILINE
    )
    related_match = related_section_pattern.search(body)
    if related_match:
        related_block = related_match.group(0)
        for entry_match in _RELATED_ENTRY_PATTERN.finditer(related_block):
            result.relations.append(
                {
                    "rel_type": entry_match.group(1).strip(),
                    "target_name": entry_match.group(2).strip(),
                }
            )
        # Remove the Related section from body
        before = body[: related_match.start()].rstrip()
        after = body[related_match.end() :].lstrip("\n")
        body = (before + ("\n\n" + after if after else "")).strip()

    # Extract wiki-links from description body
    result.wiki_links = _WIKI_LINK_PATTERN.findall(body)

    # Remove "# Description" header if present
    body = re.sub(r"^#\s+Description\s*\n?", "", body, flags=re.MULTILINE).strip()

    result.description = body

    return result


def markdown_to_import_data(parsed: ParsedMarkdown) -> Dict[str, Any]:
    """Convert ParsedMarkdown to an import-ready data dictionary.

    Maps YAML metadata to the standard import schema used by ImportService.
    Handles identity fields (uid, title), type detection, and attribute
    assembly.

    Args:
        parsed: A ParsedMarkdown instance from parse_markdown().

    Returns:
        Dict suitable for ImportService.import_batch().

    """
    meta = parsed.yaml_metadata
    data: Dict[str, Any] = {}

    # Identity fields
    uid = meta.get("uid")
    if uid:
        data["id"] = str(uid)

    title = meta.get("title", "")
    if title:
        data["name"] = str(title)

    item_type = meta.get("type", "generic")
    data["type"] = str(item_type)

    # Tags
    tags = meta.get("tags", [])
    if isinstance(tags, list):
        data.setdefault("attributes", {})["_tags"] = tags

    # Lore date (for events)
    if "lore_date" in meta:
        data["lore_date"] = meta["lore_date"]

    if "lore_duration" in meta:
        data["lore_duration"] = meta["lore_duration"]

    # User-defined attributes from YAML (exclude known/internal keys)
    _RESERVED_KEYS = {
        "uid", "title", "type", "tags", "lore_date", "lore_duration",
        "created", "modified", "source",
    }
    for key, value in meta.items():
        if key not in _RESERVED_KEYS:
            data.setdefault("attributes", {})[key] = value

    # Summary -> _summary_data attribute
    if parsed.tl_dr_block:
        summary_hash = hashlib.md5(
            parsed.tl_dr_block.encode("utf-8")
        ).hexdigest()
        data.setdefault("attributes", {})["_summary_data"] = {
            "text": parsed.tl_dr_block,
            "hash": summary_hash,
            "timestamp": 0.0,
            "model": "imported",
            "detail_level": "standard",
        }

    # Description
    data["description"] = parsed.description

    # Relations
    if parsed.relations:
        data["relations"] = [
            {
                "rel_type": rel["rel_type"],
                "target_name": rel["target_name"],
            }
            for rel in parsed.relations
        ]

    return data


def is_entity_data(data: Dict[str, Any]) -> bool:
    """Determine if import data represents an Entity (not an Event).

    Args:
        data: Import data dictionary.

    Returns:
        True if the data is for an Entity, False if for an Event.

    """
    return "lore_date" not in data
