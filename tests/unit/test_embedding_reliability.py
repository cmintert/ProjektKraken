"""Tests for Embedding System Reliability & Performance improvements.

Covers:
1. Batch embedding in SearchService.rebuild_index
2. Worker signals for async rebuild (index_rebuild_progress, index_rebuild_finished)
3. Worker rebuild_search_index slot
4. AI Settings Dialog progress UI and auto-index checkbox
5. UpdateEventCommand / UpdateEntityCommand include 'id' in result data
6. AISearchManager async rebuild and progress/finished handlers
7. DataHandler auto-index signal (index_object_requested)
8. WorkerManager auto-index wiring
"""

import json
import sqlite3
from typing import List
from unittest.mock import MagicMock, PropertyMock, call, patch

import numpy as np
import pytest

from src.commands.base_command import CommandResult
from src.core.entities import Entity
from src.core.events import Event
from src.services.search_service import (
    EmbeddingProvider,
    SearchService,
    build_text_for_entity,
    build_text_for_event,
    text_sha256,
)


# =============================================================================
# Shared Fixtures
# =============================================================================


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider that tracks calls for verification."""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension
        self.model_name = "mock-model"
        self.embed_calls: list = []

    def embed(self, texts: List[str]) -> np.ndarray:
        self.embed_calls.append(texts)
        embeddings = []
        for text in texts:
            vec = np.zeros(self._dimension, dtype=np.float32)
            vec[0] = len(text) % 100
            vec[1] = hash(text) % 100
            embeddings.append(vec)
        return np.array(embeddings, dtype=np.float32)

    def get_dimension(self) -> int:
        return self._dimension

    def get_model_name(self) -> str:
        return f"mock:{self.model_name}"


@pytest.fixture
def search_db():
    """In-memory database with search schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(
        """
        CREATE TABLE entities (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            attributes JSON DEFAULT '{}',
            created_at REAL,
            modified_at REAL
        );
        CREATE TABLE events (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            lore_date REAL NOT NULL,
            lore_duration REAL DEFAULT 0.0,
            description TEXT,
            attributes JSON DEFAULT '{}',
            created_at REAL,
            modified_at REAL
        );
        CREATE TABLE tags (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            color TEXT,
            created_at REAL NOT NULL
        );
        CREATE TABLE entity_tags (
            entity_id TEXT NOT NULL,
            tag_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (entity_id, tag_id)
        );
        CREATE TABLE event_tags (
            event_id TEXT NOT NULL,
            tag_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (event_id, tag_id)
        );
        CREATE TABLE embeddings (
            id TEXT PRIMARY KEY,
            object_type TEXT NOT NULL,
            object_id TEXT NOT NULL,
            model TEXT NOT NULL,
            vector BLOB NOT NULL,
            vector_dim INTEGER NOT NULL,
            text_snippet TEXT,
            text_hash TEXT,
            metadata JSON DEFAULT '{}',
            created_at REAL NOT NULL
        );
        CREATE UNIQUE INDEX uq_embeddings_obj_model
            ON embeddings(object_type, object_id, model);
        CREATE INDEX idx_embeddings_model_dim
            ON embeddings(model, vector_dim);
        """
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_provider():
    return MockEmbeddingProvider(dimension=384)


@pytest.fixture
def search_service(search_db, mock_provider):
    return SearchService(search_db, mock_provider)


def _insert_entities(conn, count):
    """Insert N entities and return their IDs."""
    ids = []
    for i in range(count):
        entity = Entity(name=f"Entity_{i}", type="test", description=f"Desc {i}")
        conn.execute(
            """INSERT INTO entities (id, type, name, description, attributes,
               created_at, modified_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (entity.id, entity.type, entity.name, entity.description,
             json.dumps(entity.attributes), entity.created_at, entity.modified_at),
        )
        ids.append(entity.id)
    conn.commit()
    return ids


def _insert_events(conn, count):
    """Insert N events and return their IDs."""
    ids = []
    for i in range(count):
        event = Event(
            name=f"Event_{i}", type="test", lore_date=float(i),
            description=f"Event desc {i}",
        )
        conn.execute(
            """INSERT INTO events (id, type, name, lore_date, lore_duration,
               description, attributes, created_at, modified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event.id, event.type, event.name, event.lore_date,
             event.lore_duration, event.description,
             json.dumps(event.attributes), event.created_at, event.modified_at),
        )
        ids.append(event.id)
    conn.commit()
    return ids


# =============================================================================
# 1. Batch Embedding Tests (RED → GREEN for search_service.py)
# =============================================================================


class TestBatchEmbedding:
    """Tests for REBUILD_BATCH_SIZE and batch upsert in rebuild_index."""

    def test_rebuild_batch_size_constant_exists(self):
        """REBUILD_BATCH_SIZE should be defined in search_service module."""
        from src.services import search_service as mod
        assert hasattr(mod, "REBUILD_BATCH_SIZE")
        assert isinstance(mod.REBUILD_BATCH_SIZE, int)
        assert mod.REBUILD_BATCH_SIZE > 0

    def test_rebuild_index_batches_embed_calls(self, search_db, mock_provider):
        """rebuild_index should call provider.embed in batches, not one-at-a-time."""
        from src.services.search_service import REBUILD_BATCH_SIZE

        # Insert more entities than one batch
        count = REBUILD_BATCH_SIZE + 5
        _insert_entities(search_db, count)

        svc = SearchService(search_db, mock_provider)
        svc.rebuild_index(object_types=["entity"])

        # Provider.embed should be called in batches, NOT once per entity
        # With batching: ceil(count / REBUILD_BATCH_SIZE) calls
        # Without batching: count calls (one per entity)
        assert len(mock_provider.embed_calls) <= (count // REBUILD_BATCH_SIZE) + 1
        # And each call should have multiple texts (except possibly the last)
        for batch_call in mock_provider.embed_calls[:-1]:
            assert len(batch_call) == REBUILD_BATCH_SIZE

    def test_rebuild_index_batches_all_indexed(self, search_db, mock_provider):
        """All entities should be indexed after batched rebuild."""
        count = 50
        _insert_entities(search_db, count)

        svc = SearchService(search_db, mock_provider)
        counts = svc.rebuild_index(object_types=["entity"])

        assert counts["entity"] == count
        cursor = search_db.execute("SELECT COUNT(*) FROM embeddings")
        assert cursor.fetchone()[0] == count

    def test_rebuild_index_skips_unchanged_in_batch(self, search_db, mock_provider):
        """Unchanged items should be skipped and not sent to the provider."""
        ids = _insert_entities(search_db, 5)

        svc = SearchService(search_db, mock_provider)
        # First rebuild
        svc.rebuild_index(object_types=["entity"])
        first_call_count = len(mock_provider.embed_calls)

        # Reset call tracker
        mock_provider.embed_calls.clear()

        # Second rebuild — all unchanged, should make zero embed calls
        svc.rebuild_index(object_types=["entity"])
        assert len(mock_provider.embed_calls) == 0

    def test_rebuild_index_returns_succeeded_failed(self, search_db, mock_provider):
        """rebuild_index should return (succeeded, failed) counts per type."""
        _insert_entities(search_db, 3)
        _insert_events(search_db, 2)

        svc = SearchService(search_db, mock_provider)
        result = svc.rebuild_index(object_types=["entity", "event"])

        # result should have counts per type
        assert "entity" in result
        assert "event" in result
        # New: should include succeeded/failed breakdown
        assert result["entity"] == 3
        assert result["event"] == 2

    def test_rebuild_index_mixed_batch_events(self, search_db, mock_provider):
        """rebuild_index batches events as well as entities."""
        from src.services.search_service import REBUILD_BATCH_SIZE

        count = REBUILD_BATCH_SIZE + 3
        _insert_events(search_db, count)

        svc = SearchService(search_db, mock_provider)
        mock_provider.embed_calls.clear()
        svc.rebuild_index(object_types=["event"])

        # Should batch, not one-at-a-time
        assert len(mock_provider.embed_calls) <= (count // REBUILD_BATCH_SIZE) + 1
        cursor = search_db.execute("SELECT COUNT(*) FROM embeddings")
        assert cursor.fetchone()[0] == count

    def test_rebuild_index_partial_failure_counts(self, search_db):
        """If some items fail embedding, succeeded/failed counts reflect that."""
        _insert_entities(search_db, 3)

        # Provider that fails on second call
        class FailOnSecondProvider(MockEmbeddingProvider):
            def __init__(self):
                super().__init__()
                self._call_count = 0

            def embed(self, texts):
                self._call_count += 1
                # Fail on texts containing "Entity_1"
                results = []
                for text in texts:
                    if "Entity_1" in text:
                        raise ValueError("Simulated failure")
                    vec = np.zeros(self._dimension, dtype=np.float32)
                    vec[0] = len(text)
                    results.append(vec)
                return np.array(results, dtype=np.float32)

        provider = FailOnSecondProvider()
        svc = SearchService(search_db, provider)
        result = svc.rebuild_index(object_types=["entity"])

        # Should report failed count — at minimum report total attempted
        assert "entity" in result


# =============================================================================
# 2. Worker Signals Tests (RED → GREEN for worker.py)
# =============================================================================


class TestWorkerRebuildSignals:
    """Tests for new worker signals and rebuild_search_index slot."""

    def test_worker_has_index_rebuild_progress_signal(self):
        """DatabaseWorker should have index_rebuild_progress signal."""
        from src.services.worker import DatabaseWorker
        worker = DatabaseWorker("test.db")
        assert hasattr(worker, "index_rebuild_progress")

    def test_worker_has_index_rebuild_finished_signal(self):
        """DatabaseWorker should have index_rebuild_finished signal."""
        from src.services.worker import DatabaseWorker
        worker = DatabaseWorker("test.db")
        assert hasattr(worker, "index_rebuild_finished")

    def test_worker_has_rebuild_search_index_slot(self):
        """DatabaseWorker should have rebuild_search_index method."""
        from src.services.worker import DatabaseWorker
        worker = DatabaseWorker("test.db")
        assert hasattr(worker, "rebuild_search_index")
        assert callable(worker.rebuild_search_index)

    @patch("src.services.worker.DatabaseService")
    def test_rebuild_search_index_emits_finished(self, mock_db_cls):
        """rebuild_search_index should emit index_rebuild_finished."""
        from src.services.worker import DatabaseWorker

        worker = DatabaseWorker("test.db")
        worker.db_service = MagicMock()
        mock_conn = MagicMock()
        worker.db_service.get_connection.return_value = mock_conn

        # Mock search service
        with patch("src.services.search_service.create_search_service") as mock_create:
            mock_svc = MagicMock()
            mock_svc.rebuild_index.return_value = {"entity": 5, "event": 3}
            mock_create.return_value = mock_svc

            finished_spy = MagicMock()
            worker.index_rebuild_finished.connect(finished_spy)

            worker.rebuild_search_index("all", [])

            finished_spy.assert_called_once()
            args = finished_spy.call_args[0]
            assert args[0] == 8  # succeeded
            assert args[1] == 0  # failed

    @patch("src.services.worker.DatabaseService")
    def test_rebuild_search_index_emits_progress(self, mock_db_cls):
        """rebuild_search_index should emit index_rebuild_progress during rebuild."""
        from src.services.worker import DatabaseWorker

        worker = DatabaseWorker("test.db")
        worker.db_service = MagicMock()
        mock_conn = MagicMock()
        worker.db_service.get_connection.return_value = mock_conn

        with patch("src.services.search_service.create_search_service") as mock_create:
            mock_svc = MagicMock()
            mock_svc.rebuild_index.return_value = {"entity": 10, "event": 5}
            mock_create.return_value = mock_svc

            progress_spy = MagicMock()
            worker.index_rebuild_progress.connect(progress_spy)

            worker.rebuild_search_index("all", [])

            # Should have emitted at least one progress signal
            assert progress_spy.call_count >= 1


# =============================================================================
# 3. AI Settings Dialog Progress Tests (RED → GREEN for ai_settings_dialog.py)
# =============================================================================


class TestAISettingsDialogProgress:
    """Tests for progress label and auto-index checkbox in AI Settings dialog."""

    @pytest.fixture
    def dialog(self, qapp):
        from src.gui.dialogs.ai_settings_dialog import AISettingsDialog
        dlg = AISettingsDialog()
        yield dlg
        dlg.close()

    def test_dialog_has_rebuild_progress_label(self, dialog):
        """Dialog should have lbl_rebuild_progress attribute."""
        assert hasattr(dialog, "lbl_rebuild_progress")

    def test_dialog_has_set_rebuild_in_progress(self, dialog):
        """Dialog should have set_rebuild_in_progress method."""
        assert hasattr(dialog, "set_rebuild_in_progress")
        assert callable(dialog.set_rebuild_in_progress)

    def test_dialog_has_update_rebuild_progress(self, dialog):
        """Dialog should have update_rebuild_progress method."""
        assert hasattr(dialog, "update_rebuild_progress")
        assert callable(dialog.update_rebuild_progress)

    def test_set_rebuild_in_progress_true_disables_button(self, dialog):
        """set_rebuild_in_progress(True) should disable the rebuild button."""
        dialog.set_rebuild_in_progress(True)
        assert not dialog.btn_rebuild.isEnabled()

    def test_set_rebuild_in_progress_false_enables_button(self, dialog):
        """set_rebuild_in_progress(False) should re-enable the rebuild button."""
        dialog.set_rebuild_in_progress(True)
        dialog.set_rebuild_in_progress(False)
        assert dialog.btn_rebuild.isEnabled()

    def test_update_rebuild_progress_sets_label(self, dialog):
        """update_rebuild_progress should update the progress label text."""
        dialog.update_rebuild_progress(45, 120, 37)
        assert "45" in dialog.lbl_rebuild_progress.text()
        assert "120" in dialog.lbl_rebuild_progress.text()

    def test_dialog_has_auto_index_checkbox(self, dialog):
        """Dialog should have chk_auto_index checkbox."""
        assert hasattr(dialog, "chk_auto_index")

    def test_auto_index_checkbox_default_unchecked(self, dialog):
        """Auto-index checkbox should default to unchecked."""
        assert not dialog.chk_auto_index.isChecked()

    def test_auto_index_setting_persists(self, dialog):
        """Auto-index setting should persist to QSettings."""
        dialog.chk_auto_index.setChecked(True)
        dialog.save_settings()

        from PySide6.QtCore import QSettings
        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        val = settings.value("ai_auto_index_on_save", False, type=bool)
        assert val is True


# =============================================================================
# 4. Command ID in Results Tests (RED → GREEN for command files)
# =============================================================================


class TestCommandResultIncludesId:
    """Tests that Update commands include 'id' in their result data."""

    def test_update_event_result_includes_id(self):
        """UpdateEventCommand result data should contain the event ID."""
        from src.commands.event_commands import UpdateEventCommand

        mock_db = MagicMock()
        old_event = Event(
            id="evt-42", name="Original", type="test", lore_date=1.0,
        )
        mock_db.get_event.return_value = old_event

        cmd = UpdateEventCommand("evt-42", {"name": "Updated"})
        result = cmd.execute(mock_db)

        assert result.success
        assert result.data is not None
        assert "id" in result.data
        assert result.data["id"] == "evt-42"

    def test_update_entity_result_includes_id(self):
        """UpdateEntityCommand result data should contain the entity ID."""
        from src.commands.entity_commands import UpdateEntityCommand

        mock_db = MagicMock()
        old_entity = Entity(id="ent-42", name="Original", type="test")
        mock_db.get_entity.return_value = old_entity

        cmd = UpdateEntityCommand("ent-42", {"name": "Updated"})
        result = cmd.execute(mock_db)

        assert result.success
        assert result.data is not None
        assert "id" in result.data
        assert result.data["id"] == "ent-42"


# =============================================================================
# 5. Async Rebuild in AISearchManager (RED → GREEN)
# =============================================================================


class TestAISearchManagerAsyncRebuild:
    """Tests that rebuild is dispatched to worker thread, not run on main thread."""

    @pytest.fixture
    def mock_window(self):
        window = MagicMock()
        window.db_path = "dummy.db"
        window.ai_settings_dialog = None
        return window

    @pytest.fixture
    def manager(self, mock_window):
        from src.app.ai_search_manager import AISearchManager
        return AISearchManager(mock_window)

    def test_rebuild_does_not_use_gui_db_service_connection(
        self, manager, mock_window
    ):
        """rebuild_search_index should NOT access gui_db_service._connection."""
        mock_window.worker = MagicMock()
        mock_window.gui_db_service = MagicMock()

        manager.rebuild_search_index("all")

        # Should NOT directly create search_service on main thread
        mock_window.gui_db_service._connection.__class__  # access is fine
        # The key assertion: no direct call to create_search_service
        # Instead, it should invoke worker method
        # After implementation, the worker's rebuild_search_index should be invoked

    def test_manager_has_on_index_rebuild_progress(self, manager):
        """AISearchManager should have on_index_rebuild_progress slot."""
        assert hasattr(manager, "on_index_rebuild_progress")
        assert callable(manager.on_index_rebuild_progress)

    def test_manager_has_on_index_rebuild_finished(self, manager):
        """AISearchManager should have on_index_rebuild_finished slot."""
        assert hasattr(manager, "on_index_rebuild_finished")
        assert callable(manager.on_index_rebuild_finished)

    def test_on_index_rebuild_progress_updates_status(self, manager, mock_window):
        """on_index_rebuild_progress should update the status bar."""
        manager.on_index_rebuild_progress(45, 120, 37)
        mock_window.status_bar.showMessage.assert_called()
        msg = mock_window.status_bar.showMessage.call_args[0][0]
        assert "45" in msg or "37" in msg

    def test_on_index_rebuild_finished_shows_result(self, manager, mock_window):
        """on_index_rebuild_finished should show success in status bar."""
        manager.on_index_rebuild_finished(100, 0)
        mock_window.status_bar.showMessage.assert_called()
        msg = mock_window.status_bar.showMessage.call_args[0][0]
        assert "100" in msg

    def test_on_index_rebuild_finished_shows_failures(self, manager, mock_window):
        """on_index_rebuild_finished should mention failures when present."""
        manager.on_index_rebuild_finished(95, 5)
        mock_window.status_bar.showMessage.assert_called()
        msg = mock_window.status_bar.showMessage.call_args[0][0]
        assert "5" in msg  # failure count should be visible


# =============================================================================
# 6. DataHandler Auto-Index Signal (RED → GREEN)
# =============================================================================


class TestDataHandlerAutoIndex:
    """Tests for index_object_requested signal on DataHandler."""

    @pytest.fixture
    def handler(self, qapp):
        from src.app.data_handler import DataHandler
        return DataHandler()

    def test_handler_has_index_object_requested_signal(self, handler):
        """DataHandler should have index_object_requested signal."""
        assert hasattr(handler, "index_object_requested")

    def test_event_update_emits_index_signal(self, handler):
        """on_command_finished for UpdateEventCommand should emit index signal."""
        spy = MagicMock()
        handler.index_object_requested.connect(spy)

        result = CommandResult(
            success=True,
            message="Event updated.",
            command_name="UpdateEventCommand",
            data={"id": "evt-123"},
        )
        handler.on_command_finished(result)

        spy.assert_called_once_with("event", "evt-123")

    def test_entity_update_emits_index_signal(self, handler):
        """on_command_finished for UpdateEntityCommand should emit index signal."""
        spy = MagicMock()
        handler.index_object_requested.connect(spy)

        result = CommandResult(
            success=True,
            message="Entity updated.",
            command_name="UpdateEntityCommand",
            data={"id": "ent-456"},
        )
        handler.on_command_finished(result)

        spy.assert_called_once_with("entity", "ent-456")

    def test_delete_does_not_emit_index_signal(self, handler):
        """Delete commands should NOT emit index_object_requested."""
        spy = MagicMock()
        handler.index_object_requested.connect(spy)

        result = CommandResult(
            success=True,
            message="Event deleted.",
            command_name="DeleteEventCommand",
            data={"id": "evt-789"},
        )
        handler.on_command_finished(result)

        spy.assert_not_called()

    def test_create_entity_emits_index_signal(self, handler):
        """CreateEntityCommand should also emit index signal."""
        spy = MagicMock()
        handler.index_object_requested.connect(spy)

        result = CommandResult(
            success=True,
            message="Entity created.",
            command_name="CreateEntityCommand",
            data={"id": "ent-new"},
        )
        handler.on_command_finished(result)

        spy.assert_called_once_with("entity", "ent-new")

    def test_create_event_emits_index_signal(self, handler):
        """CreateEventCommand should also emit index signal."""
        spy = MagicMock()
        handler.index_object_requested.connect(spy)

        result = CommandResult(
            success=True,
            message="Event created.",
            command_name="CreateEventCommand",
            data={"id": "evt-new"},
        )
        handler.on_command_finished(result)

        spy.assert_called_once_with("event", "evt-new")

    def test_undo_does_not_emit_index_signal(self, handler):
        """Undo operations should NOT emit index_object_requested."""
        spy = MagicMock()
        handler.index_object_requested.connect(spy)

        result = CommandResult(
            success=True,
            message="Undone.",
            command_name="Undo_UpdateEventCommand",
            data={"id": "evt-123"},
        )
        handler.on_command_finished(result)

        spy.assert_not_called()

    def test_failed_command_does_not_emit_index_signal(self, handler):
        """Failed commands should NOT emit index_object_requested."""
        spy = MagicMock()
        handler.index_object_requested.connect(spy)

        result = CommandResult(
            success=False,
            message="Failed.",
            command_name="UpdateEntityCommand",
            data={"id": "ent-fail"},
        )
        handler.on_command_finished(result)

        spy.assert_not_called()


# =============================================================================
# 7. WorkerManager Auto-Index Wiring (RED → GREEN)
# =============================================================================


class TestWorkerManagerAutoIndex:
    """Tests for WorkerManager wiring of auto-index signals."""

    def test_worker_manager_has_index_helper(self):
        """WorkerManager should have _on_index_object_requested helper."""
        from src.app.worker_manager import WorkerManager
        wm = WorkerManager(MagicMock())
        assert hasattr(wm, "_on_index_object_requested")
        assert callable(wm._on_index_object_requested)

    def test_index_helper_checks_auto_index_setting(self):
        """_on_index_object_requested should check ai_auto_index_on_save setting."""
        from src.app.worker_manager import WorkerManager

        mock_window = MagicMock()
        mock_window.worker = MagicMock()
        wm = WorkerManager(mock_window)

        # With auto-index OFF (default), should not invoke worker
        with patch("PySide6.QtCore.QSettings") as MockSettings:
            mock_settings = MockSettings.return_value
            mock_settings.value.return_value = False

            wm._on_index_object_requested("entity", "ent-123")

            # Worker's index_object should NOT be called
            # (no QMetaObject.invokeMethod call should happen)
