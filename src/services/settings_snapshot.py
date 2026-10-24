"""Worker-owned reads of portable configuration."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.core.ai_generation import AIGenerationPreferences
from src.services.db_service import DatabaseService
from src.services.repositories.settings_repository import (
    META_KEYS,
    POLICY_KEY,
    SettingsRepository,
)

logger = logging.getLogger(__name__)


def world_snapshot(db: DatabaseService) -> dict[str, Any]:
    """Read a detached snapshot, exclusively on the database-owning thread."""
    repo = SettingsRepository(db.require_connection())
    policy = repo.policy()
    values: dict[str, Any] = {
        "world.auto_relations": bool(policy.get("auto_relations", False)),
        "world.excluded_attributes": list(policy.get("excluded_attributes", [])),
    }
    for setting, key in META_KEYS.items():
        raw = repo.raw(key)
        values[setting] = (
            (raw or "")
            if setting == "world.theme"
            else (json.loads(raw) if raw is not None else None)
        )
    calendar = db.get_active_calendar_config()
    values["world.ai"] = values.get("world.ai") or AIGenerationPreferences().to_dict()
    values["world.calendar"] = calendar.to_dict() if calendar else None
    values["world.tag_colors"] = {
        tag["name"]: db.get_tag_color(tag["name"]) for tag in db.get_all_tags()
    }
    return values


class SettingsSnapshotWorker(QObject):
    """A feature endpoint sharing the existing database thread, not its UI."""

    loaded = Signal(dict)
    index_state_changed = Signal()

    def __init__(self, database: Callable[[], DatabaseService | None]) -> None:
        """Initialize detached settings state and explicit dependencies."""
        super().__init__()
        self._database = database

    @Slot(dict)
    def load(self, request: dict[str, Any]) -> None:
        """Initialize policy once and return an identity-bound snapshot."""
        result = {"token": request["token"], "database": request["database"]}
        try:
            db = self._database()
            if db is None or db.db_path != request["database"]:
                raise RuntimeError("The world is no longer available.")
            repo = SettingsRepository(db.require_connection())
            if not db.read_only:
                repo.ensure_policy(request.get("seed", {}))
                if repo.raw(META_KEYS["world.ai"]) is None:
                    with repo.transaction():
                        repo.restore(
                            META_KEYS["world.ai"],
                            json.dumps(
                                request.get("ai_seed")
                                or AIGenerationPreferences().to_dict()
                            ),
                        )
            result.update(
                values=world_snapshot(db),
                writable=not db.read_only,
                tags=[
                    {
                        "name": tag["name"],
                        "color": db.get_tag_color(tag["name"]),
                        "count": db.get_group_metadata([tag["name"]])[0]["count"],
                    }
                    for tag in db.get_tags_with_events()
                ],
                entity_types=sorted({entity.type for entity in db.get_entities()}),
                relation_types=sorted(
                    {relation["rel_type"] for relation in db.get_all_relations()}
                ),
                index_requires_rebuild=repo.policy().get(
                    "index_requires_rebuild", False
                ),
            )
        except Exception as exc:
            logger.error("World settings snapshot failed (%s)", type(exc).__name__)
            result["error"] = "World configuration could not be loaded."
        self.loaded.emit(result)

    @Slot(dict)
    def mark_index_rebuilt(self, request: dict[str, Any]) -> None:
        """Clear the warning only for a full successful rebuild of current exclusions."""
        db = self._database()
        if db is None or db.read_only or db.db_path != request.get("database"):
            return
        repo = SettingsRepository(db.require_connection())
        policy = repo.policy()
        if policy.get("excluded_attributes", []) != request.get("excluded_attributes"):
            return
        policy["index_requires_rebuild"] = False
        with repo.transaction():
            repo.restore(POLICY_KEY, json.dumps(policy))
        self.index_state_changed.emit()
