"""Machine-local activity layouts, independent of portable world storage."""

from __future__ import annotations

import json
import logging
import uuid
from copy import deepcopy
from typing import Any

from PySide6.QtCore import QSettings

from src.core.workspaces import (
    BUILTIN_IDS,
    BUILTIN_WORKSPACES,
    WORKSPACE_COLLECTION_KEY,
    WORKSPACE_LAYOUT_VERSION,
)

logger = logging.getLogger(__name__)
_NAVIGATION_PRESENTATION_VERSION = 2


def _mapping(raw: object) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


def _layout(raw: object) -> dict[str, Any] | None:
    value = _mapping(raw)
    if value.get("layout_version") != WORKSPACE_LAYOUT_VERSION or not isinstance(
        value.get("zones"), dict
    ):
        return None
    return deepcopy(value)


class WorkspaceStore:
    """Read/write one versioned local collection and migrate legacy snapshots once."""

    def __init__(self, settings: QSettings) -> None:
        """Use the application's existing local settings namespace."""
        self.settings = settings

    def load(self) -> dict[str, Any]:
        """Recover entries independently; absent built-in layouts stay lazy."""
        raw = _mapping(self.settings.value(WORKSPACE_COLLECTION_KEY))
        if raw.get("version") != 1:
            return self._migrate()
        entries = self._builtins()
        saved = _mapping(raw.get("entries"))
        for identifier, value in saved.items():
            entry = self._entry(identifier, value)
            if entry is not None:
                entries[identifier] = entry
        active = raw.get("active", "overview")
        return {
            "version": 1,
            "entries": entries,
            "active": active
            if isinstance(active, str) and active in entries
            else "overview",
            "expanded": raw.get("expanded") is True
            and raw.get("navigation_version") == _NAVIGATION_PRESENTATION_VERSION,
            "navigation_version": _NAVIGATION_PRESENTATION_VERSION,
        }

    @staticmethod
    def _builtins() -> dict[str, Any]:
        return {
            item.id: {"name": item.name, "layout": None} for item in BUILTIN_WORKSPACES
        }

    @staticmethod
    def _entry(identifier: str, raw: object) -> dict[str, Any] | None:
        value = _mapping(raw)
        layout = _layout(value.get("layout"))
        if identifier in BUILTIN_IDS:
            name = next(
                item.name for item in BUILTIN_WORKSPACES if item.id == identifier
            )
            return {"name": name, "layout": layout}
        custom_name = value.get("name")
        baseline = _layout(value.get("baseline"))
        if layout is None and baseline is not None:
            layout = deepcopy(baseline)
        if not identifier.startswith("custom:") or not isinstance(custom_name, str):
            return None
        if not custom_name.strip() or layout is None:
            return None
        return {
            "name": custom_name.strip(),
            "layout": layout,
            "baseline": baseline or deepcopy(layout),
        }

    def _migrate(self) -> dict[str, Any]:
        entries = self._builtins()
        entries["overview"]["layout"] = _layout(self.settings.value("workspace_layout"))
        for name, raw in _mapping(self.settings.value("saved_layouts")).items():
            layout = _layout(raw)
            if layout is not None and str(name).strip():
                identifier = "custom:" + str(uuid.uuid4())
                entries[identifier] = {
                    "name": str(name),
                    "layout": layout,
                    "baseline": deepcopy(layout),
                }
        return {
            "version": 1,
            "entries": entries,
            "active": "overview",
            "expanded": False,
            "navigation_version": _NAVIGATION_PRESENTATION_VERSION,
        }

    def save(self, collection: dict[str, Any]) -> None:
        """Flush settled layouts without changing legacy recovery settings."""
        self.settings.setValue(
            WORKSPACE_COLLECTION_KEY, json.dumps(collection, sort_keys=True)
        )
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            logger.error("Unable to persist activity workspace settings")

    def reset_view_state(self) -> None:
        """Reset built-in arrangements and display while retaining named resources."""
        if self.settings.value(WORKSPACE_COLLECTION_KEY) is None:
            return
        collection = self.load()
        for identifier in BUILTIN_IDS:
            collection["entries"][identifier]["layout"] = None
        collection.update(active="overview", expanded=False)
        self.save(collection)
