"""Exercise dictionary review, history, portability and the Settings route."""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox

from src.app.coordinators.relation_dictionary_coordinator import (
    RelationDictionaryCoordinator,
)
from src.commands.relation_dictionary_command import EditRelationDefinitionCommand
from src.core.entities import Entity
from src.core.relation_dictionary import (
    edit_document,
    kraken_defaults,
    wording_examples,
)
from src.core.relation_guidance import relation_hint
from src.core.relation_vocabulary import VOCABULARY_KEY, load_document, parse_vocabulary
from src.core.theme_manager import ThemeManager
from src.gui.widgets.settings_center import SettingsCenter
from src.services.backup_service import BackupConfig, BackupService
from src.services.db_service import DatabaseService
from src.services.relation_dictionary import RelationDictionaryReader, usage
from src.services.repositories.settings_repository import SettingsRepository
from src.services.transfer_worker import TransferWorker
from src.services.world_transfer import export_world, import_world

pytestmark = pytest.mark.ci_fast


def _definition(**changes):
    return {
        **kraken_defaults()["member_of"],
        "forward_label": "Sworn member of",
        "forward_template": "{source} belongs to {target}.",
        "reverse_template": "{target} counts {source} as a member.",
        **changes,
    }


def _seed(db_service, count=1):
    db_service.insert_entity(Entity(id="source", name="Ari", type="Character"))
    db_service.insert_entity(Entity(id="target", name="Guild", type="Faction"))
    connection = db_service.require_connection()
    with db_service.transaction():
        connection.executemany(
            "INSERT INTO relations(id, source_id, target_id, rel_type, attributes)"
            " VALUES (?, 'source', 'target', ?, ?)",
            [
                (str(index), key, '{"notes":"Original","valid_from":10}')
                for index, key in enumerate(
                    ["member_of"] * count + ["Member_Of", "knows"]
                )
            ],
        )
    return connection


def test_counted_edit_undo_and_redo_keep_relation_rows(db_service):
    connection = _seed(db_service, 240)
    repo = SettingsRepository(connection)
    rows = connection.execute("SELECT * FROM relations ORDER BY id").fetchall()
    evidence = usage(connection, "member_of")
    assert evidence["count"] == 240
    assert evidence["sample"]["source_name"] == "Ari"
    command = EditRelationDefinitionCommand(
        db_service.db_path, None, _definition(symmetric=True), "member_of", evidence
    )
    assert command.execute(db_service).success
    saved = repo.raw(VOCABULARY_KEY)
    conflict = EditRelationDefinitionCommand(
        db_service.db_path, None, _definition(), "member_of", evidence
    ).execute(db_service)
    assert not conflict.success and "dictionary changed" in conflict.message
    assert wording_examples(saved, "member_of", evidence["sample"])[:2] == (
        "Sworn member of · Ari belongs to Guild.",
        "Members · Guild counts Ari as a member.",
    )
    restored_command = EditRelationDefinitionCommand.from_dict(command.to_dict())
    restored_command.undo(db_service)
    assert repo.raw(VOCABULARY_KEY) is None
    assert restored_command.execute(db_service).success
    assert repo.raw(VOCABULARY_KEY) == saved
    assert connection.execute("SELECT * FROM relations ORDER BY id").fetchall() == rows


def test_stale_usage_wrong_world_and_failed_write_leave_metadata_intact(
    db_service, monkeypatch
):
    connection = _seed(db_service)
    repo = SettingsRepository(connection)
    evidence = usage(connection, "member_of")
    assert (
        not EditRelationDefinitionCommand(
            "another-world", None, _definition(), "member_of", evidence
        )
        .execute(db_service)
        .success
    )
    with db_service.transaction():
        connection.execute(
            "INSERT INTO relations(id, source_id, target_id, rel_type)"
            " VALUES ('extra', 'target', 'source', 'member_of')"
        )
    assert (
        not EditRelationDefinitionCommand(
            db_service.db_path, None, _definition(), "member_of", evidence
        )
        .execute(db_service)
        .success
    )
    original_restore = SettingsRepository.restore

    def interrupted_write(self, key, value):
        original_restore(self, key, value)
        raise RuntimeError("Simulated failure after write")

    monkeypatch.setattr(SettingsRepository, "restore", interrupted_write)
    with pytest.raises(RuntimeError, match="Simulated failure"):
        EditRelationDefinitionCommand(
            db_service.db_path,
            None,
            _definition(),
            "member_of",
            usage(connection, "member_of"),
        ).execute(db_service)
    assert repo.raw(VOCABULARY_KEY) is None


def test_definition_validation_preserves_legacy_and_disabled_entries():
    raw = json.dumps(
        {"version": 1, "definitions": [_definition(forward_template="{bad}")]}
    )
    assert "Ari" not in wording_examples(raw, "member_of", None)[0]
    with pytest.raises(ValueError, match="template"):
        edit_document(raw, _definition(forward_template="{source.name}"), "member_of")
    with pytest.raises(ValueError, match="cannot be edited"):
        edit_document(raw, _definition(key="changed"), "member_of")
    with pytest.raises(ValueError, match="reserved"):
        edit_document(raw, _definition(key="Birth"), None)
    with pytest.raises(ValueError, match="reserved"):
        edit_document(raw, _definition(key="mentions"), None)
    with pytest.raises(ValueError, match="unsupported"):
        edit_document('{"version": 2, "definitions": []}', _definition(), None)
    disabled = edit_document(raw, _definition(enabled=False), "member_of")
    assert parse_vocabulary(disabled) == {}
    assert load_document(disabled)["definitions"][0]["forward_template"].startswith(
        "{source}"
    )
    restored = edit_document(disabled, _definition(enabled=True), "member_of")
    assert parse_vocabulary(restored)["member_of"]["forward_label"] == "Sworn member of"


def test_package_reopen_and_backup_restore_keep_world_vocabulary(tmp_path):
    root = tmp_path / "world"
    root.mkdir()
    database = root / "world.kraken"
    service = DatabaseService(str(database))
    service.connect()
    try:
        connection = _seed(service)
        repo = SettingsRepository(connection)
        definition = _definition(preferred_source_kind="event")
        assert (
            EditRelationDefinitionCommand(
                service.db_path,
                None,
                definition,
                "member_of",
                usage(connection, "member_of"),
            )
            .execute(service)
            .success
        )
        saved = repo.raw(VOCABULARY_KEY)
        disabled = edit_document(
            saved, _definition(key="knows", enabled=False), "knows"
        )
        with service.transaction():
            repo.restore(VOCABULARY_KEY, disabled)
        rows = TransferWorker(lambda: service)._run(
            {
                "operation": "prepare_export",
                "db_path": service.db_path,
                "format": "json",
                "scope": "all",
            }
        )["data"]["relations"]
        assert {row["rel_type"] for row in rows} == {"Member_Of", "knows", "member_of"}
        package = tmp_path / "world.krakenworld"
        export_world(
            connection,
            {"path": str(root), "manifest": {"name": "World", "id": "world"}},
            package,
            lambda: False,
        )
    finally:
        service.close()
    backups = BackupService(BackupConfig(backup_dir=tmp_path / "backups"))
    backup = backups.create_backup(database)
    assert backup is not None
    restored = tmp_path / "restored.kraken"
    assert backups.restore_backup(Path(backup.backup_path), restored)
    imported = import_world(package, tmp_path / "imports", "Imported", lambda: False)
    for path in (database, restored, imported / "world.kraken"):
        reopened = DatabaseService(str(path), read_only=True)
        reopened.connect()
        try:
            connection = reopened.require_connection()
            assert SettingsRepository(connection).raw(VOCABULARY_KEY) == disabled
            vocab = parse_vocabulary(disabled)
            assert "knows" not in vocab
            assert relation_hint("member_of", vocab, "entity", "entity")
            assert vocab["member_of"]["reverse_template"].startswith("{target}")
            assert sorted(row["rel_type"] for row in reopened.get_all_relations()) == [
                "Member_Of",
                "knows",
                "member_of",
            ]
            rejected = EditRelationDefinitionCommand(
                reopened.db_path,
                disabled,
                definition,
                "member_of",
                usage(connection, "member_of"),
            ).execute(reopened)
            assert not rejected.success
            assert connection.total_changes == 0
        finally:
            reopened.close()
    other = DatabaseService(":memory:")
    other.connect()
    try:
        assert (
            SettingsRepository(other.require_connection()).raw(VOCABULARY_KEY) is None
        )
    finally:
        other.close()


def test_settings_route_reviews_and_saves_at_standard_and_narrow_sizes(
    qtbot, qapp, db_service, tmp_path, monkeypatch
):
    connection = _seed(db_service, 240)
    parent = SettingsCenter()
    qtbot.addWidget(parent)
    parent._build_dictionary_page()
    parent.show()
    parent.search.setText("relation dictionary")
    assert parent.selected_target()[:2] == ("world", "Relation Dictionary")
    assert parent.relation_dictionary_button.isVisible()
    reader = RelationDictionaryReader(lambda: db_service)

    def execute(command):
        result = command.execute(db_service)
        result.data["command_id"] = command.command_id
        coordinator.on_command_finished(result)
        return True

    coordinator = RelationDictionaryCoordinator(
        lambda: {"database": db_service.db_path, "name": "Fixture world"},
        execute,
        reader,
        parent,
    )
    coordinator.requested.connect(reader.load, Qt.ConnectionType.QueuedConnection)
    reader.finished.connect(coordinator.on_snapshot, Qt.ConnectionType.QueuedConnection)
    parent.relation_dictionary_requested.connect(lambda: coordinator.open(parent))
    qtbot.mouseClick(parent.relation_dictionary_button, Qt.MouseButton.LeftButton)
    view = coordinator.view
    qtbot.waitUntil(lambda: view.entries.count() > 0)
    catalog_item = next(
        view.entries.item(index)
        for index in range(view.entries.count())
        if tuple(view.entries.item(index).data(Qt.ItemDataRole.UserRole))
        == ("default", "member_of")
    )
    view.entries.setCurrentItem(catalog_item)
    qtbot.mouseClick(view.open_button, Qt.MouseButton.LeftButton)
    assert view.fields["key"].isReadOnly()
    qtbot.keyClicks(view.fields["forward_label"], " (reviewed)")
    view.advanced.setChecked(True)
    assert view.migration.isVisible() and not view.migration.isEnabled()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel
    )
    assert coordinator.has_pending_changes()
    assert not coordinator.allow_transition()
    assert view.fields["forward_label"].text().endswith("(reviewed)")
    manager = ThemeManager()
    qss = Path("src/resources/main.qss").read_text(encoding="utf-8")
    prior_sheet, prior_palette = qapp.styleSheet(), qapp.palette()
    try:
        manager.apply_theme(qapp, qss)
        themes = manager.get_available_themes()
        assert len(themes) == 6
        for theme in themes:
            manager.set_theme(theme, persist=False)
            for width in (620, 360):
                view.resize(width, 600)
                qtbot.waitUntil(lambda: view.width() == width)
                assert view.form_scroll.horizontalScrollBar().maximum() == 0
                assert view.grab().save(str(tmp_path / f"{theme}-{width}-edit.png"))
                qtbot.mouseClick(view.review, Qt.MouseButton.LeftButton)
                qtbot.waitUntil(lambda: view.save.isVisible() and view.save.isEnabled())
                assert "240 stored connections" in view.review_text.text()
                assert (
                    "Before" in view.review_text.text()
                    and "After" in view.review_text.text()
                )
                assert view.review_scroll.horizontalScrollBar().maximum() == 0
                assert view.save.hasFocus()
                image = view.grab()
                assert image.toImage().pixelColor(2, 2) == QColor(
                    manager.get_theme()["app_bg"]
                )
                assert image.save(str(tmp_path / f"{theme}-{width}-review.png"))
                qtbot.mouseClick(view.edit, Qt.MouseButton.LeftButton)
                assert not view.save.isVisible()
    finally:
        qapp.setStyleSheet(prior_sheet)
        qapp.setPalette(prior_palette)
    assert SettingsRepository(connection).raw(VOCABULARY_KEY) is None
    template = view.fields["forward_template"]
    qtbot.keyClicks(template, "{bad}")
    assert not view.review.isEnabled()
    assert "only {source} and {target}" in view.message.text()
    qtbot.keyClick(template, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    qtbot.keyClick(template, Qt.Key.Key_Backspace)
    qtbot.mouseClick(view.review, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: view.save.isVisible() and view.save.isEnabled())
    qtbot.keyClick(view.save, Qt.Key.Key_Space)
    qtbot.waitUntil(lambda: view.entries.count() > 0)
    assert "saved" in view.message.text()
    assert (
        "reviewed"
        in parse_vocabulary(SettingsRepository(connection).raw(VOCABULARY_KEY))[
            "member_of"
        ]["forward_label"]
    )
    assert coordinator.allow_transition()
