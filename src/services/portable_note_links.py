"""Portable Obsidian body links with explicit native identity provenance."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping

from src.core.entities import Entity
from src.core.events import Event
from src.core.markdown_content import rewrite_wikilinks_in_source
from src.core.markdown_extensions import WIKI_PATTERN


def _link(target: str, label: str, original: str, in_table: bool) -> str:
    match = WIKI_PATTERN.fullmatch(original)
    # Keep authored alias spelling (including entities) in the derived note.
    alias = match[2] if match and match[2] is not None else label
    if in_table:
        alias = re.sub(r"(?<!\\)((?:\\\\)*)\|", r"\1\\|", alias)
    if target == alias and not (match and match[2] is not None):
        return f"[[{target}]]"
    separator = "\\|" if in_table else "|"
    return f"[[{target}{separator}{alias}]]"


def note_name_candidates(items: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    """Capture world-wide name ambiguity independently of an export selection."""
    names: dict[str, set[str]] = defaultdict(set)
    for identity, name in items:
        names[name.casefold()].add(identity)
    return {name: sorted(identities) for name, identities in names.items()}


class PortableNoteLinks:
    """Resolve only known identities and unique authored names in one export."""

    def __init__(
        self,
        items: Iterable[Entity | Event],
        filenames: Mapping[str, str],
        name_candidates: Mapping[str, list[str]] | None = None,
    ) -> None:
        """Use the final filename allocation, never independently sanitize a link."""
        self.targets = {
            identity: filename
            if filename[:-3].lower().endswith(".md")
            else filename[:-3]
            for identity, filename in filenames.items()
        }
        self.filenames = dict(filenames)
        names = (
            name_candidates
            if name_candidates is not None
            else note_name_candidates((item.id, item.name) for item in items)
        )
        self.names = {name: ids[0] for name, ids in names.items() if len(ids) == 1}

    def _identity(self, target: str) -> str | None:
        return (
            target[3:]
            if target.startswith("id:")
            else self.names.get(target.casefold())
        )

    def unresolved_targets(self, source: str) -> list[str]:
        """Keep unresolved authored targets distinct from coincident note names."""
        unresolved: set[str] = set()

        def inspect(target: str, label: str, original: str, in_table: bool) -> None:
            if self._identity(target) not in self.targets:
                unresolved.add(target)

        rewrite_wikilinks_in_source(source, inspect)
        return sorted(unresolved)

    def project(self, source: str) -> tuple[str, dict[str, str]]:
        """Return derived prose and only the target identities used by that prose."""
        identities: dict[str, str] = {}
        unresolved = {name.casefold() for name in self.unresolved_targets(source)}

        def rewrite(
            target: str, label: str, original: str, in_table: bool
        ) -> str | None:
            identity = self._identity(target)
            destination = self.targets.get(identity or "")
            if destination is None:
                return _link(target, label, original, True) if in_table else None
            if destination.casefold() in unresolved:
                destination = self.filenames[str(identity)]
                if destination.casefold() in unresolved:
                    raise ValueError(
                        "Portable note links conflict with unresolved targets; "
                        "rename the note or clarify those links."
                    )
            identities[destination] = str(identity)
            return _link(destination, label, original, in_table)

        return rewrite_wikilinks_in_source(source, rewrite), identities


def restore_note_links(source: str, mapping: object, unresolved: object = None) -> str:
    """Rebind edited native-note links only through validated export provenance."""
    if not isinstance(mapping, dict) or any(
        not isinstance(name, str)
        or not name
        or not isinstance(identity, str)
        or not identity
        for name, identity in mapping.items()
    ):
        raise ValueError("Native note link targets must map note names to record IDs.")
    index: dict[str, str] = {}
    if unresolved is None:
        unresolved = []
    if not isinstance(unresolved, list) or any(
        not isinstance(name, str) for name in unresolved
    ):
        raise ValueError("Native unresolved note links must be a list of targets.")
    blocked = {name.casefold() for name in unresolved}
    for name, identity in mapping.items():
        key = name.casefold()
        if key in index and index[key] != identity:
            raise ValueError("Native note link targets contain ambiguous note names.")
        index[key] = identity

    def rewrite(target: str, label: str, original: str, in_table: bool) -> str | None:
        if target.casefold() in blocked:
            return None
        identity = index.get(target.casefold())
        if identity is None and target.lower().endswith(".md"):
            identity = index.get(target[:-3].casefold())
        if identity is None:
            return None
        return _link(f"id:{identity}", label, original, in_table)

    return rewrite_wikilinks_in_source(source, rewrite)
