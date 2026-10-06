"""Shared existing-object search for relation authoring."""

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter, QLineEdit, QWidget


class RelationTargetEdit(QLineEdit):
    """Resolve named suggestions to canonical IDs without inventing objects."""

    def __init__(
        self,
        items: list[tuple[str, str, str]],
        target_id: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """Build a disambiguating, case-insensitive existing-object picker."""
        super().__init__(parent)
        self.initial_id = target_id
        self.display_to_id: dict[str, str] = {}
        self.id_to_display: dict[str, str] = {}
        self.id_to_kind: dict[str, str] = {}
        self.name_to_ids: dict[str, list[str]] = {}
        counts = Counter(name.casefold() for _, name, _ in items)
        for item_id, name, kind in items:
            display = (
                f"{name} ({kind}, {item_id})" if counts[name.casefold()] > 1 else name
            )
            self.display_to_id[display] = item_id
            self.id_to_display[item_id] = display
            self.id_to_kind[item_id] = kind.casefold()
            self.name_to_ids.setdefault(name.casefold(), []).append(item_id)
        completer = QCompleter(sorted(self.display_to_id, key=str.lower), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCompleter(completer)
        self.setPlaceholderText("Search for entity or event...")
        if target_id:
            self.setText(self.id_to_display.get(target_id, target_id))

    def resolve(self) -> str | None:
        """Return an existing ID, retaining an unchanged existing target."""
        candidate = self.text().strip()
        if candidate in self.display_to_id:
            return self.display_to_id[candidate]
        if candidate in self.id_to_display:
            return candidate
        if candidate and candidate == self.initial_id:
            return candidate
        matches = self.name_to_ids.get(candidate.casefold(), [])
        return matches[0] if len(matches) == 1 else None
