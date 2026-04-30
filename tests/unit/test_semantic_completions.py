"""Tests for semantic completion feature.

Tests the full signal chain: WikiTextEdit emits prefix -> DataCoordinator
debounces -> Worker queries SearchService -> results merge into completer.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.widgets.wiki_text_edit import WikiTextEdit, WikiTextEditView
from src.services.worker import DatabaseWorker

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def editor(qapp):
    """A WikiTextEdit wrapper with a completer pre-loaded."""
    w = WikiTextEdit()
    w.set_completer(names=["Gandalf", "Frodo", "Sauron"])
    return w


@pytest.fixture
def editor_view(qapp):
    """A raw WikiTextEditView with a completer pre-loaded."""
    v = WikiTextEditView()
    v.set_completer(names=["Gandalf", "Frodo", "Sauron"])
    return v


@pytest.fixture
def worker(monkeypatch):
    """A DatabaseWorker with a mocked db_service."""
    monkeypatch.setattr(
        "src.services.worker.SEMANTIC_COMPLETION_ENABLE_EMBEDDING", True
    )
    monkeypatch.setattr(
        "src.services.worker.SEMANTIC_COMPLETION_PROBE_ON_WINDOWS", False
    )
    w = DatabaseWorker("test.db")
    w.db_service = MagicMock()
    w.db_service.get_connection.return_value = MagicMock()
    return w


# ===========================================================================
# WikiTextEditView.merge_completions
# ===========================================================================


class TestMergeCompletions:
    """Tests for WikiTextEditView.merge_completions."""

    def test_appends_new_names(self, editor_view):
        """Semantic names are appended to the existing completer model."""
        editor_view.merge_completions(["Aragorn", "Legolas"])

        model = editor_view._completer.model()
        names = model.stringList()
        assert "Gandalf" in names
        assert "Frodo" in names
        assert "Sauron" in names
        assert "Aragorn" in names
        assert "Legolas" in names

    def test_deduplicates(self, editor_view):
        """Names already in the completer are not added again."""
        editor_view.merge_completions(["Gandalf", "Aragorn"])

        model = editor_view._completer.model()
        names = model.stringList()
        assert names.count("Gandalf") == 1
        assert "Aragorn" in names

    def test_noop_without_completer(self, qapp):
        """merge_completions does nothing if completer was never set."""
        v = WikiTextEditView()
        assert v._completer is None
        v.merge_completions(["Aragorn"])  # should not raise
        assert v._completer is None

    def test_noop_with_empty_list(self, editor_view):
        """Empty list doesn't change the model."""
        model_before = editor_view._completer.model().stringList()
        editor_view.merge_completions([])
        model_after = editor_view._completer.model().stringList()
        assert model_before == model_after

    def test_set_completer_resets_merged(self, editor_view):
        """Calling set_completer after merge replaces everything (no stale data)."""
        editor_view.merge_completions(["Aragorn"])
        assert "Aragorn" in editor_view._completer.model().stringList()

        editor_view.set_completer(names=["Bilbo"])
        names = editor_view._completer.model().stringList()
        assert names == ["Bilbo"]
        assert "Aragorn" not in names


# ===========================================================================
# WikiTextEdit wrapper proxying
# ===========================================================================


class TestWikiTextEditWrapperProxy:
    """Tests that the WikiTextEdit wrapper proxies the new API."""

    def test_merge_completions_proxied(self, editor):
        """merge_completions on wrapper delegates to inner editor."""
        editor.merge_completions(["Aragorn"])
        model = editor.editor._completer.model()
        assert "Aragorn" in model.stringList()

    def test_completion_prefix_changed_signal_exists(self, editor):
        """WikiTextEdit wrapper exposes completion_prefix_changed signal."""
        # Should be connectable without error
        spy = MagicMock()
        editor.completion_prefix_changed.connect(spy)
        # Emit from inner view, verify wrapper proxies
        editor.editor.completion_prefix_changed.emit("test")
        spy.assert_called_once_with("test")


# ===========================================================================
# WikiTextEditView.completion_prefix_changed signal
# ===========================================================================


class TestCompletionPrefixSignal:
    """Tests for the completion_prefix_changed signal emission."""

    def test_emitted_for_long_prefix(self, editor_view):
        """Signal fires when prefix is >= 3 characters inside [[ ]]."""
        spy = MagicMock()
        editor_view.completion_prefix_changed.connect(spy)

        # Simulate typing "[[Gan" (prefix = "Gan", len 3)
        editor_view.setPlainText("[[Gan")
        cursor = editor_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        editor_view.setTextCursor(cursor)
        editor_view._check_for_completion()

        spy.assert_called_once_with("Gan")

    def test_not_emitted_twice_for_same_prefix(self, editor_view):
        """Signal is not re-emitted when the prefix hasn't changed."""
        spy = MagicMock()
        editor_view.completion_prefix_changed.connect(spy)

        editor_view.setPlainText("[[Gan")
        cursor = editor_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        editor_view.setTextCursor(cursor)

        editor_view._check_for_completion()
        editor_view._check_for_completion()  # same prefix, should not re-emit

        spy.assert_called_once_with("Gan")

    def test_not_emitted_for_short_prefix(self, editor_view):
        """Signal does NOT fire when prefix is < 3 characters."""
        spy = MagicMock()
        editor_view.completion_prefix_changed.connect(spy)

        editor_view.setPlainText("[[Ga")
        cursor = editor_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        editor_view.setTextCursor(cursor)
        editor_view._check_for_completion()

        spy.assert_not_called()

    def test_not_emitted_when_no_bracket(self, editor_view):
        """Signal does NOT fire for regular text without [[."""
        spy = MagicMock()
        editor_view.completion_prefix_changed.connect(spy)

        editor_view.setPlainText("Gandalf")
        cursor = editor_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        editor_view.setTextCursor(cursor)
        editor_view._check_for_completion()

        spy.assert_not_called()

    def test_not_emitted_after_pipe(self, editor_view):
        """Signal does NOT fire when prefix contains pipe (display text)."""
        spy = MagicMock()
        editor_view.completion_prefix_changed.connect(spy)

        editor_view.setPlainText("[[Gandalf|Gan")
        cursor = editor_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        editor_view.setTextCursor(cursor)
        editor_view._check_for_completion()

        spy.assert_not_called()


# ===========================================================================
# DatabaseWorker.query_semantic_suggestions
# ===========================================================================


class TestWorkerSemanticQuery:
    """Tests for DatabaseWorker.query_semantic_suggestions."""

    def test_emits_filtered_results(self, worker):
        """Results below min_score are filtered out; signal carries plain names."""
        mock_results = [
            {"name": "Dragon", "object_type": "entity", "score": 0.92,
             "object_id": "1", "id": "e1", "type": "creature", "metadata": {},
             "text_content": ""},
            {"name": "Dragonfly", "object_type": "entity", "score": 0.70,
             "object_id": "2", "id": "e2", "type": "creature", "metadata": {},
             "text_content": ""},
        ]

        spy = MagicMock()
        worker.semantic_suggestions_ready.connect(spy)

        with patch(
            "src.services.search_service.create_search_service"
        ) as mock_css:
            mock_svc = MagicMock()
            mock_svc.query.return_value = mock_results
            mock_css.return_value = mock_svc

            worker.query_semantic_suggestions("Dragon", 5, 0.85)

        spy.assert_called_once()
        prefix, names = spy.call_args[0]
        assert prefix == "Dragon"
        assert names == ["Dragon"]

    def test_no_emit_without_db(self):
        """Does nothing when db_service is None."""
        w = DatabaseWorker("test.db")
        spy = MagicMock()
        w.semantic_suggestions_ready.connect(spy)
        w.query_semantic_suggestions("test", 5, 0.85)
        spy.assert_not_called()

    def test_caches_search_service(self, worker):
        """SearchService is created once and reused."""
        with patch(
            "src.services.search_service.create_search_service"
        ) as mock_css:
            mock_svc = MagicMock()
            mock_svc.query.return_value = []
            mock_css.return_value = mock_svc

            worker.query_semantic_suggestions("test1", 5, 0.85)
            worker.query_semantic_suggestions("test2", 5, 0.85)

        # create_search_service should only be called once (cached)
        assert mock_css.call_count == 1

    def test_graceful_on_exception(self, worker):
        """Exceptions are caught, nothing emitted."""
        spy = MagicMock()
        worker.semantic_suggestions_ready.connect(spy)

        with patch(
            "src.services.search_service.create_search_service",
            side_effect=RuntimeError("model load failed"),
        ):
            # Clear cache so _get_search_service tries to create a new one
            worker._search_service = None
            worker.query_semantic_suggestions("test", 5, 0.85)

        spy.assert_not_called()

    def test_cache_reset_on_initialize(self, worker):
        """Cache is cleared when initialize_db is called."""
        worker._search_service = MagicMock()

        with patch("src.services.worker.DatabaseService") as MockDB:
            mock_instance = MockDB.return_value
            mock_instance._attachment_repo = MagicMock()
            worker.initialize_db()

        assert worker._search_service is None

    def test_probe_failure_disables_query_safely(self, worker, monkeypatch):
        """A failed Windows probe must skip SearchService creation and emit nothing."""
        monkeypatch.setattr(
            "src.services.worker.SEMANTIC_COMPLETION_PROBE_ON_WINDOWS", True
        )
        monkeypatch.setattr("src.services.worker.sys.platform", "win32")
        worker._semantic_probe_ran = False

        spy = MagicMock()
        worker.semantic_suggestions_ready.connect(spy)

        with patch("src.services.worker.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="probe failed")
            with patch("src.services.search_service.create_search_service") as mock_css:
                worker.query_semantic_suggestions("Dragon", 5, 0.85)

        mock_css.assert_not_called()
        spy.assert_not_called()


# ===========================================================================
# DataCoordinator debounce + routing
# ===========================================================================


class TestDataCoordinatorSemantic:
    """Tests for DataCoordinator.request_semantic_completions and handler."""

    @pytest.fixture
    def coordinator(self, qapp, monkeypatch):
        """A DataCoordinator with a QObject parent that has mocked attributes."""
        from PySide6.QtCore import QObject

        from src.app.coordinators.data_coordinator import DataCoordinator

        monkeypatch.setattr(
            "src.app.coordinators.data_coordinator.SEMANTIC_COMPLETION_ENABLE_EMBEDDING",
            True,
        )

        # BaseCoordinator needs a real QObject as parent
        mw = QObject()
        mw.worker = MagicMock()
        mw.navigation_coordinator = MagicMock()
        mw.event_editor = MagicMock()
        mw.entity_editor = MagicMock()
        coord = DataCoordinator(mw)
        return coord

    def test_request_stores_prefix_and_starts_timer(self, coordinator):
        """request_semantic_completions stores prefix and (re)starts timer."""
        coordinator.request_semantic_completions("Dra")
        assert coordinator._pending_semantic_prefix == "Dra"
        assert coordinator._semantic_debounce.isActive()

    def test_debounce_resets_on_rapid_calls(self, coordinator):
        """Rapid calls restart the debounce; only last prefix is stored."""
        coordinator.request_semantic_completions("Dr")
        coordinator.request_semantic_completions("Dra")
        coordinator.request_semantic_completions("Drag")
        assert coordinator._pending_semantic_prefix == "Drag"

    def test_on_semantic_suggestions_routes_to_event_editor(self, coordinator):
        """Names are routed to event editor's merge_wiki_completions when event selected."""
        coordinator.main_window.navigation_coordinator.selected_type = "event"

        coordinator.on_semantic_suggestions("Dra", ["Dragon", "Drake"])

        coordinator.main_window.event_editor.merge_wiki_completions.assert_called_once_with(
            ["Dragon", "Drake"]
        )
        coordinator.main_window.entity_editor.merge_wiki_completions.assert_not_called()

    def test_on_semantic_suggestions_routes_to_entity_editor(self, coordinator):
        """Names are routed to entity editor's merge_wiki_completions when entity selected."""
        coordinator.main_window.navigation_coordinator.selected_type = "entity"

        coordinator.on_semantic_suggestions("Dra", ["Dragon"])

        coordinator.main_window.entity_editor.merge_wiki_completions.assert_called_once_with(
            ["Dragon"]
        )

    def test_on_semantic_suggestions_noop_on_empty(self, coordinator):
        """Empty list doesn't call merge."""
        coordinator.main_window.navigation_coordinator.selected_type = "event"
        coordinator.on_semantic_suggestions("Dra", [])
        coordinator.main_window.event_editor.merge_wiki_completions.assert_not_called()

    def test_request_noop_when_embedding_disabled(self, qapp, monkeypatch):
        """No semantic debounce/query is scheduled when embedding is disabled."""
        from PySide6.QtCore import QObject

        from src.app.coordinators.data_coordinator import DataCoordinator

        monkeypatch.setattr(
            "src.app.coordinators.data_coordinator.SEMANTIC_COMPLETION_ENABLE_EMBEDDING",
            False,
        )

        mw = QObject()
        mw.worker = MagicMock()
        mw.navigation_coordinator = MagicMock()
        mw.event_editor = MagicMock()
        mw.entity_editor = MagicMock()
        coordinator = DataCoordinator(mw)

        coordinator.request_semantic_completions("Dra")

        assert coordinator._pending_semantic_prefix == ""
        assert not coordinator._semantic_debounce.isActive()
