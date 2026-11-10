"""Arbitrary world types receive portable assignments without hash collisions."""

import json
import sqlite3

import pytest

from src.core.category_palette import CATEGORY_ROLES, assign_categories, category_key
from src.core.entities import Entity
from src.services.db_service import DatabaseService
from src.services.repositories.category_palette_repository import (
    PALETTE_KEY,
    CategoryPaletteRepository,
)

pytestmark = pytest.mark.ci_fast


def test_twenty_four_arbitrary_types_use_every_slot_before_reusing():
    categories = [("entity", f"Unknown type {index}") for index in range(24)]
    saved = assign_categories({}, categories)
    assert len(set(saved.values())) == len(CATEGORY_ROLES) == 24
    extended = assign_categories(saved, [("entity", "A later type")])
    assert len(extended) == 25
    assert all(extended[key] == slot for key, slot in saved.items())
    assert assign_categories(saved, reversed(categories)) == saved


def test_added_removed_and_readded_types_keep_previous_assignments():
    categories = [("entity", value) for value in ("Character", "Concept", "Deity")]
    initial = assign_categories({}, categories)
    assert len(set(initial.values())) == 3
    removed = assign_categories(initial, categories[:1])
    assert removed == initial
    added = assign_categories(removed, [("entity", "Religion")])
    assert len(set(added.values())) == 4
    assert assign_categories(added, categories) == added
    assert all(added[key] == slot for key, slot in initial.items())


def test_exact_names_and_object_kinds_never_alias():
    pairs = [
        ("entity", "Deity"),
        ("entity", "deity"),
        ("event", "Deity"),
        ("entity", "A:B"),
        ("entity", "世界"),
    ]
    assert len(set(assign_categories({}, pairs).values())) == len(pairs)


def test_saved_assignments_survive_database_copy_restart_and_new_type(
    db_service, tmp_path
):
    for name in ("Character", "Concept", "Deity"):
        db_service.insert_entity(Entity(name=name, type=name))
    repo = CategoryPaletteRepository(db_service.require_connection())
    saved = repo.ensure_assignments()
    assert len(set(saved.values())) == 3
    portable = tmp_path / "copied-world.kraken"
    with sqlite3.connect(portable) as copy:
        db_service.require_connection().backup(copy)
    reopened = DatabaseService(str(portable))
    reopened.connect()
    try:
        repo = CategoryPaletteRepository(reopened.require_connection())
        assert repo.ensure_assignments() == saved
        reopened.insert_entity(Entity(name="New faith", type="Religion"))
        added = repo.ensure_assignments()
        assert all(added[key] == slot for key, slot in saved.items())
        assert added[category_key("entity", "Religion")] not in saved.values()
    finally:
        reopened.close()


def test_filtering_sorting_and_reloading_do_not_allocate_or_recolor(qtbot):
    from src.gui.widgets.unified_list import UnifiedListWidget

    entities = [
        Entity(name=name, type=name) for name in ("Character", "Concept", "Deity")
    ]
    saved = assign_categories({}, [("entity", entity.type) for entity in entities])
    view = UnifiedListWidget()
    qtbot.addWidget(view)
    view.set_data([], entities)
    view.set_category_assignments(saved)
    view._model.set_use_hashed_colors(True)
    view.sort_combo.setCurrentText("Type")
    view._proxy_model.setFilterFixedString("Deity")
    assert view._model._category_assignments == saved
    view.set_data([], list(reversed(entities)))
    assert view._model._category_assignments == saved


def test_read_only_does_not_write_and_invalid_settings_are_preserved(db_service):
    db_service.insert_entity(Entity(name="Aktia", type="Deity"))
    connection = db_service.require_connection()
    repo = CategoryPaletteRepository(connection)
    result = repo.ensure_assignments(read_only=True)
    assert category_key("entity", "Deity") in result
    assert (
        connection.execute(
            "SELECT value FROM system_meta WHERE key=?", (PALETTE_KEY,)
        ).fetchone()
        is None
    )
    malformed = json.dumps({"schema": 99, "assignments": {}})
    connection.execute("INSERT INTO system_meta VALUES (?,?)", (PALETTE_KEY, malformed))
    connection.commit()
    with pytest.raises(ValueError, match="Unsupported"):
        repo.ensure_assignments()
    assert (
        connection.execute(
            "SELECT value FROM system_meta WHERE key=?", (PALETTE_KEY,)
        ).fetchone()[0]
        == malformed
    )
