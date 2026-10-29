"""Settings boundaries: drafts, backend acknowledgements and embedded forms."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QSettings

from src.commands.settings_commands import ApplyWorldSettingsCommand
from src.core.settings_registry import BY_ID, SettingsDraft
from src.gui.widgets.settings_center import SettingsCenter
from src.services.local_settings import LocalSettingsAdapter
from src.services.repositories.settings_repository import POLICY_KEY, SettingsRepository
from src.services.settings_snapshot import world_snapshot

pytestmark = pytest.mark.ci_fast


def test_world_refresh_uses_the_graph_coordinator():
    from src.app.settings_composition import _refresh_world_consumers

    window = Mock()
    _refresh_world_consumers(window, {})
    window.data_coordinator.load_graph_data.assert_called_once_with()
    window.worker.load_graph_data.assert_not_called()


def test_center_uses_theme_surface_and_keeps_keyboard_ownership(
    qtbot, init_theme_manager
):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor

    from src.core.theme_manager import ThemeManager

    view = SettingsCenter()
    qtbot.addWidget(view)
    view.show()
    assert view.grab().toImage().pixelColor(2, 2) == QColor(
        ThemeManager().get_theme()["app_bg"]
    )
    qtbot.keyClick(view.search, Qt.Key.Key_Return)
    assert view.isVisible()
    with qtbot.waitSignal(view.close_requested):
        qtbot.keyClick(view.search, Qt.Key.Key_Escape)
    assert view.isVisible()


def test_draft_merges_external_changes_and_resolves_conflicts():
    draft = SettingsDraft()
    draft.replace({"a": [1], "b": False})
    draft.values["a"] = [2]
    draft.merge({"a": [3], "b": True})
    assert draft.values == {"a": [2], "b": True}
    assert draft.conflicts == {"a": [3]}
    draft.resolve("a", keep_edit=True)
    assert draft.changes() == {"a": [2]}
    draft.acknowledge({"a": [2]})
    assert not draft.changes()


def test_acknowledgement_preserves_edit_made_while_saving():
    draft = SettingsDraft()
    draft.replace({"x": 1})
    draft.values["x"] = 3
    draft.acknowledge({"x": 2})
    assert draft.changes() == {"x": 3}


@pytest.fixture
def local(tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("src.services.secret_store.get_api_key", lambda provider: "")
    monkeypatch.setattr("src.services.secret_store.read_api_key", lambda provider: "")
    monkeypatch.setattr("src.services.secret_store.set_api_key", lambda *args: True)
    return LocalSettingsAdapter(settings)


def test_legacy_seed_is_frozen_across_worlds_and_resets(local):
    local.settings.setValue("wiki/auto_create_relations", True)
    local.settings.setValue("ai_search_excluded_attrs", "secret, private")
    first = local.legacy_seed()
    local.settings.setValue("wiki/auto_create_relations", False)
    local.reset_preferences()
    assert local.legacy_seed() == first
    assert first["auto_relations"] is True
    assert first["excluded_attributes"] == ["secret", "private"]


def test_targeted_resets_preserve_resources_credentials_and_worlds(local):
    preserved = {
        "world_storage/active_world_path": "world",
        "world_storage/external_database_approvals": "trusted",
        "named_layouts": "resource",
        "raster/brush_presets": "resource",
        "SpellCheck/api_key": "legacy",
        "settings_center/sentinel": "keep",
    }
    for key, value in preserved.items():
        local.settings.setValue(key, value)
    local.settings.setValue("longform_auto_refresh", False)
    local.settings.setValue("workspace_layout", "temporary")
    local.reset_preferences()
    assert local.settings.value("workspace_layout") == "temporary"
    local.reset_workspace()
    assert not local.settings.contains("workspace_layout")
    for key, value in preserved.items():
        assert local.settings.value(key) == value


def test_credential_failure_retains_plaintext_and_failed_draft(local, monkeypatch):
    local.settings.setValue("SpellCheck/api_key", "legacy")
    monkeypatch.setattr("src.services.secret_store.set_api_key", lambda *args: False)
    assert local.migrate_credentials()
    assert local.settings.value("SpellCheck/api_key") == "legacy"
    saved, errors = local.save(
        {"longform_auto_refresh": False, "secret.languagetool.api_key": "new"}
    )
    assert saved == {"longform_auto_refresh": False}
    assert errors
    assert local.settings.value("SpellCheck/api_key") == "legacy"


def test_policy_initialization_is_idempotent_and_undo_restores_absence(db_service):
    repo = SettingsRepository(db_service.require_connection())
    repo.ensure_policy({"auto_relations": True, "excluded_attributes": ["private"]})
    repo.ensure_policy({"auto_relations": False})
    assert repo.policy()["auto_relations"] is True
    before = repo.raw(POLICY_KEY)
    snapshot = world_snapshot(db_service)
    command = ApplyWorldSettingsCommand(
        {"world.theme": "light_mode", "world.auto_relations": False},
        {key: snapshot[key] for key in ("world.theme", "world.auto_relations")},
    )
    assert command.execute(db_service).success
    assert repo.raw("world_theme") == "light_mode"
    command.undo(db_service)
    assert repo.raw("world_theme") is None
    assert repo.raw(POLICY_KEY) == before


def test_stale_world_patch_has_no_partial_writes(db_service):
    repo = SettingsRepository(db_service.require_connection())
    repo.ensure_policy({})
    command = ApplyWorldSettingsCommand(
        {"world.theme": "light_mode", "world.auto_relations": True},
        {"world.auto_relations": True},
    )
    assert not command.execute(db_service).success
    assert repo.raw("world_theme") is None
    assert repo.policy()["auto_relations"] is False


def test_world_command_roundtrip_preserves_target_and_exact_undo(db_service):
    SettingsRepository(db_service.require_connection()).ensure_policy({})
    command = ApplyWorldSettingsCommand(
        {"world.theme": "light_mode"}, {"world.theme": ""}, db_service.db_path
    )
    restored = ApplyWorldSettingsCommand.from_dict(command.to_dict())
    assert restored.database == db_service.db_path
    assert restored.execute(db_service).success
    undo = ApplyWorldSettingsCommand.from_dict(restored.to_dict())
    undo.undo(db_service)
    assert world_snapshot(db_service)["world.theme"] == ""


def test_registry_search_never_uses_values_or_resets_credentials():
    assert BY_ID["world.ai"].matches("persona")
    assert BY_ID["world.auto_relations"].matches("wikilinks")
    assert not BY_ID["secret.openai"].resettable


def test_embedded_center_construction_has_no_persistence(
    qtbot, init_theme_manager, monkeypatch, local
):
    write = Mock(side_effect=AssertionError("Opening settings must not write"))
    monkeypatch.setattr("src.services.secret_store.set_api_key", write)
    view = SettingsCenter()
    qtbot.addWidget(view)
    view.render_values(local.snapshot())
    view.controls["longform_auto_refresh"].setChecked(False)
    assert not write.called
    assert view.collect()["longform_auto_refresh"] is False
    assert not view.ai.isWindow()


def test_embedded_world_forms_preserve_values(qtbot, init_theme_manager, db_service):
    from src.core.calendar import CalendarConfig

    db_service.insert_calendar_config(CalendarConfig.create_default())
    calendar = db_service.get_all_calendar_configs()[0]
    db_service.set_active_calendar_config(calendar.id)
    SettingsRepository(db_service.require_connection()).ensure_policy({})
    values = world_snapshot(db_service)
    view = SettingsCenter()
    qtbot.addWidget(view)
    view.build_world_pages(
        {"values": values, "tags": [], "entity_types": [], "relation_types": []}
    )
    view.render_values(values)
    view.show()
    view.navigate("world.calendar")
    assert view.selected_target()[:2] == ("world", "Timeline")
    assert not view.calendar.isWindow()
    assert not view.grouping.isWindow()
    assert view.calendar.isVisibleTo(view)
    assert view.grouping.isVisibleTo(view)
    assert view.calendar.draft_config() == values["world.calendar"]
    assert view.grouping.draft_config() is None
    view.search.setText("calendar")
    assert view.navigation.count() == 1
    assert "This World" in view.navigation.item(0).text()


@pytest.fixture
def settings_coordinator(qtbot, init_theme_manager, local, db_service):
    from PySide6.QtWidgets import QWidget

    from src.app.coordinators.settings_coordinator import SettingsCoordinator
    from src.core.calendar import CalendarConfig

    parent = QWidget()
    qtbot.addWidget(parent)
    calendar = CalendarConfig.create_default()
    db_service.insert_calendar_config(calendar)
    db_service.set_active_calendar_config(calendar.id)
    SettingsRepository(db_service.require_connection()).ensure_policy({})
    submitted = []
    coordinator = SettingsCoordinator(
        lambda: {"database": db_service.db_path, "name": "Test World"},
        submitted.append,
        parent,
        local,
    )
    coordinator.open_settings()
    coordinator.on_snapshot(
        {
            "token": coordinator._token,
            "database": db_service.db_path,
            "values": world_snapshot(db_service),
            "tags": [],
            "entity_types": [],
            "relation_types": [],
            "writable": True,
        }
    )
    return coordinator, submitted


def test_open_navigate_search_and_cancel_write_nothing(settings_coordinator, local):
    coordinator, submitted = settings_coordinator
    assert not coordinator.draft.changes()
    view = coordinator.view
    view.controls["longform_auto_refresh"].setChecked(False)
    view.navigate("world.theme")
    view.search.setText("backup")
    coordinator.cancel()
    assert not submitted
    assert local.snapshot()["longform_auto_refresh"] is True
    coordinator.open_settings("longform_auto_refresh")
    assert coordinator.view.controls["longform_auto_refresh"].isChecked()


def test_read_failure_disables_world_pages_and_contextual_writes(settings_coordinator):
    coordinator, submitted = settings_coordinator
    availability = []
    coordinator.world_availability_changed.connect(
        lambda enabled, reason: availability.append((enabled, reason))
    )
    coordinator.on_snapshot(
        {
            "token": coordinator._token,
            "database": coordinator._database,
            "error": "World configuration could not be loaded.",
        }
    )
    assert availability == [(False, "World configuration could not be loaded.")]
    assert not coordinator.view.pages[("world", "Writing")].isEnabled()
    coordinator.set_contextual("world.auto_relations", True)
    assert not submitted


def test_apply_waits_for_world_acknowledgement(settings_coordinator, db_service):
    coordinator, submitted = settings_coordinator
    view = coordinator.view
    view.controls["world.auto_relations"].setChecked(True)
    coordinator.apply()
    assert len(submitted) == 1
    assert "world.auto_relations" in coordinator.draft.changes()
    result = submitted[0].execute(db_service)
    result.data["command_id"] = submitted[0].command_id
    coordinator.on_command_finished(result)
    assert not coordinator.draft.changes()
    assert SettingsRepository(db_service.require_connection()).policy()[
        "auto_relations"
    ]


def test_partial_failure_keeps_only_failed_drafts(settings_coordinator, monkeypatch):
    coordinator, submitted = settings_coordinator
    coordinator.view.controls["longform_auto_refresh"].setChecked(False)
    coordinator.view.controls["secret.openai"].setText("new")
    monkeypatch.setattr("src.services.secret_store.set_api_key", lambda *args: False)
    coordinator.apply()
    assert coordinator.draft.changes() == {"secret.openai": "new"}
    assert "Could not save" in coordinator.view.message.text()
    assert not submitted


def test_world_apply_failure_retains_world_draft(settings_coordinator):
    from src.core.command import CommandResult

    coordinator, submitted = settings_coordinator
    coordinator.view.controls["world.auto_relations"].setChecked(True)
    coordinator.apply()
    result = CommandResult(
        False, "Database unavailable", data={"command_id": submitted[0].command_id}
    )
    coordinator.on_command_finished(result)
    assert coordinator.draft.changes()["world.auto_relations"] is True
    assert coordinator.view.stack.isEnabled()


def test_external_contextual_change_creates_conflict(settings_coordinator):
    coordinator, _ = settings_coordinator
    coordinator.view.controls["SpellCheck/language"].setText("de-DE")
    coordinator.set_contextual("SpellCheck/language", "fr-FR")
    assert coordinator.draft.conflicts == {"SpellCheck/language": "fr-FR"}
    assert coordinator.view.controls["SpellCheck/language"].text() == "de-DE"


def test_stale_world_snapshot_cannot_replace_active_draft(settings_coordinator):
    coordinator, _ = settings_coordinator
    previous = deepcopy(coordinator.world_values)
    coordinator.on_snapshot({"token": "old", "database": "old", "values": {}})
    assert coordinator.world_values == previous


def test_world_scope_apply_preserves_kraken_draft(settings_coordinator, db_service):
    coordinator, submitted = settings_coordinator
    coordinator.view.controls["longform_auto_refresh"].setChecked(False)
    coordinator.view.controls["world.auto_relations"].setChecked(True)
    coordinator.apply(world_only=True)
    result = submitted[0].execute(db_service)
    result.data["command_id"] = submitted[0].command_id
    coordinator.on_command_finished(result)
    assert coordinator.draft.changes() == {"longform_auto_refresh": False}


def test_invalid_calendar_blocks_local_writes(settings_coordinator, local):
    coordinator, submitted = settings_coordinator
    coordinator.view.controls["longform_auto_refresh"].setChecked(False)
    coordinator.view.calendar.leap_table.item(0, 0).setText("invalid")
    coordinator.apply()
    assert not submitted
    assert local.snapshot()["longform_auto_refresh"] is True
    assert "whole numbers" in coordinator.view.message.text()


def test_workspace_reset_runs_after_shutdown_state_is_saved(local):
    local.request_workspace_reset()
    local.settings.setValue("workspace_layout", "saved on shutdown")
    local.apply_pending_workspace_reset()
    assert not local.settings.contains("workspace_layout")
    local.settings.setValue("workspace_layout", "new session")
    local.apply_pending_workspace_reset()
    assert local.settings.value("workspace_layout") == "new session"


def test_populated_tag_world_loads_and_tag_colors_undo_exactly(db_service):
    """Basic tag records omit colour; snapshot loading must enrich them explicitly."""
    from src.core.events import Event
    from src.services.settings_snapshot import SettingsSnapshotWorker

    event = Event(name="Tagged event", lore_date=1.0)
    db_service.insert_event(event)
    db_service.assign_tag_to_event(event.id, "Northwatch")
    endpoint = SettingsSnapshotWorker(lambda: db_service)
    results = []
    endpoint.loaded.connect(results.append)
    endpoint.load({"token": "current", "database": db_service.db_path})
    payload = results[0]
    assert "error" not in payload
    assert payload["tags"][0]["name"] == "Northwatch"
    assert payload["tags"][0]["count"] == 1
    assert payload["values"]["world.tag_colors"]["Northwatch"]
    original = db_service.get_tag_by_name("Northwatch")["color"]
    command = ApplyWorldSettingsCommand(
        {"world.tag_colors": {"Northwatch": "#123456"}},
        {"world.tag_colors": payload["values"]["world.tag_colors"]},
    )
    assert command.execute(db_service).success
    command.undo(db_service)
    assert db_service.get_tag_by_name("Northwatch")["color"] == original


def test_world_name_is_visible_before_snapshot_arrives(settings_coordinator):
    coordinator, _ = settings_coordinator
    assert coordinator.view.scope.itemText(1) == "This World — Test World"


def test_missing_calendar_does_not_create_pending_edit(qtbot, init_theme_manager):
    from src.gui.widgets.settings_forms import CalendarSettingsForm

    form = CalendarSettingsForm(None)
    qtbot.addWidget(form)
    assert form.draft_config() is None
    form.name_edit.setText("New calendar")
    assert form.draft_config()["name"] == "New calendar"


def test_plaintext_is_retained_if_secure_store_cannot_be_read(local, monkeypatch):
    local.settings.setValue("SpellCheck/api_key", "previous")
    monkeypatch.setattr("src.services.secret_store.read_api_key", lambda _: None)
    write = Mock(return_value=True)
    monkeypatch.setattr("src.services.secret_store.set_api_key", write)
    assert local.migrate_credentials()
    assert not write.called
    assert local.settings.value("SpellCheck/api_key") == "previous"


def test_graph_edits_preserve_styles_for_unused_types(qtbot, init_theme_manager):
    from src.gui.widgets.settings_forms import LexiconSettingsForm

    original = {
        "nodes": {
            "Unused": {"custom": "retained"},
            "Character": {"custom": "also retained"},
        },
        "edges": {"unused": {"width": 2}},
    }
    form = LexiconSettingsForm(
        {
            "values": {"world.lexicon": original},
            "entity_types": ["Character"],
            "relation_types": [],
        }
    )
    qtbot.addWidget(form)
    form._node_rows["Character"]["border_width"].setValue(3)
    changed = form.get_lexicon_config()
    assert changed["nodes"]["Unused"] == original["nodes"]["Unused"]
    assert changed["nodes"]["Character"]["custom"] == "also retained"
    assert changed["edges"] == original["edges"]


def test_world_failure_rolls_back_earlier_metadata_writes(db_service):
    SettingsRepository(db_service.require_connection()).ensure_policy({})
    db_service.create_tag("Arc")
    before = world_snapshot(db_service)
    command = ApplyWorldSettingsCommand(
        {"world.theme": "light_mode", "world.tag_colors": {"Arc": "invalid"}},
        {
            "world.theme": before["world.theme"],
            "world.tag_colors": before["world.tag_colors"],
        },
    )
    with pytest.raises(ValueError):
        command.execute(db_service)
    assert world_snapshot(db_service) == before


def test_two_portable_worlds_keep_independent_policy(db_service, tmp_path):
    from src.services.db_service import DatabaseService

    first = SettingsRepository(db_service.require_connection())
    first.ensure_policy({"auto_relations": True, "excluded_attributes": ["private"]})
    second_db = DatabaseService(str(tmp_path / "second.kraken"))
    second_db.connect()
    try:
        second = SettingsRepository(second_db.require_connection())
        second.ensure_policy({})
        assert not world_snapshot(second_db)["world.auto_relations"]
        assert world_snapshot(db_service)["world.excluded_attributes"] == ["private"]
        copy = tmp_path / "portable.kraken"
        import sqlite3

        destination = sqlite3.connect(copy)
        second_db.require_connection().backup(destination)
        destination.close()
    finally:
        second_db.close()
    moved = DatabaseService(str(copy))
    moved.connect()
    try:
        assert not world_snapshot(moved)["world.auto_relations"]
        assert (
            SettingsRepository(moved.require_connection()).policy()["migration"]
            == "product-defaults-v1"
        )
    finally:
        moved.close()


def test_partial_local_failure_message_survives_world_ack(
    settings_coordinator, db_service, monkeypatch
):
    coordinator, submitted = settings_coordinator
    coordinator.view.controls["world.auto_relations"].setChecked(True)
    coordinator.view.controls["secret.openai"].setText("pending")
    monkeypatch.setattr("src.services.secret_store.set_api_key", lambda *args: False)
    coordinator.apply()
    result = submitted[0].execute(db_service)
    result.data["command_id"] = submitted[0].command_id
    coordinator.on_command_finished(result)
    assert "Could not save openai" in coordinator.view.message.text()
    assert coordinator.draft.changes() == {"secret.openai": "pending"}


def test_draft_conflict_clears_when_external_value_returns_to_baseline():
    draft = SettingsDraft()
    draft.replace({"language": "auto"})
    draft.values["language"] = "de-DE"
    draft.merge({"language": "fr-FR"})
    assert draft.conflicts
    draft.merge({"language": "auto"})
    assert not draft.conflicts


def test_dependency_mode_draft_conflict_preserves_user_edit(
    settings_coordinator, local
):
    from src.core.timeline_visibility import DEPENDENCY_VISIBILITY_KEY

    coordinator, _ = settings_coordinator
    view = coordinator.view
    assert view is not None
    control = view.controls[DEPENDENCY_VISIBILITY_KEY]
    assert control.currentData() == "selected"
    control.setCurrentIndex(control.findData("off"))
    coordinator.set_contextual(DEPENDENCY_VISIBILITY_KEY, "trail")
    coordinator._sync()
    assert local.snapshot()[DEPENDENCY_VISIBILITY_KEY] == "trail"
    assert control.currentData() == "off"
    assert coordinator.draft.conflicts[DEPENDENCY_VISIBILITY_KEY] == "trail"
    coordinator.draft.resolve(DEPENDENCY_VISIBILITY_KEY, keep_edit=True)
    assert coordinator.draft.changes()[DEPENDENCY_VISIBILITY_KEY] == "off"


@pytest.mark.real_qt_invoke
def test_settings_endpoint_uses_existing_database_thread(qtbot, tmp_path):
    from PySide6.QtCore import QObject, Qt, QThread, Signal

    from src.commands.registry import get_command_types
    from src.services.settings_snapshot import SettingsSnapshotWorker
    from src.services.worker import DatabaseWorker

    class Requests(QObject):
        initialize = Signal()
        load = Signal(dict)
        cleanup = Signal()

    thread = QThread()
    database = str(tmp_path / "threaded.kraken")
    worker = DatabaseWorker(database, get_command_types())
    worker.moveToThread(thread)
    reads = []

    def provider():
        reads.append(QThread.currentThread())
        return worker.db_service

    endpoint = SettingsSnapshotWorker(provider)
    endpoint.moveToThread(thread)
    requests = Requests()
    queued = Qt.ConnectionType.QueuedConnection
    requests.initialize.connect(worker.initialize_db, queued)
    requests.load.connect(endpoint.load, queued)
    requests.cleanup.connect(worker.cleanup, queued)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(endpoint.deleteLater)
    thread.start()
    try:
        with qtbot.waitSignal(worker.initialized, timeout=5000):
            requests.initialize.emit()
        with qtbot.waitSignal(endpoint.loaded, timeout=5000) as response:
            requests.load.emit({"database": database, "token": "current"})
        assert response.args[0]["token"] == "current"
        assert "error" not in response.args[0]
        assert reads == [thread]
    finally:
        with qtbot.waitSignal(worker.cleanup_finished, timeout=5000):
            requests.cleanup.emit()
        thread.quit()
        assert thread.wait(5000)
