"""Worker-owned read transaction for Entity World Context snapshots."""

from pathlib import Path
from typing import Any

from src.core.entity_context_mode import EntityContextMode
from src.services.db_service import DatabaseService


def read_entity_context_snapshot(
    db: DatabaseService | None,
    db_path: str,
    entity_id: str,
    mode: str = "all_history",
    context_date: float = 0.0,
) -> dict[str, Any]:
    """Read a fresh detached projection without owning worker signals or errors."""
    from src.services.authoring_context_builder import AuthoringContextBuilder

    if db is None:
        return {}
    db.ensure_fresh_view()
    with db.transaction():
        builder = AuthoringContextBuilder(db, world_root=Path(db_path).resolve().parent)
        if mode == "all_history":
            context = builder.build_entity_context(entity_id)
        else:
            context = builder.build_entity_context(
                entity_id, mode=EntityContextMode(mode), context_date=context_date
            )
    return context.to_dict() if context is not None else {}
