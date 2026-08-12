from unittest.mock import MagicMock, patch

import pytest

from src.app.ai_search_manager import AISearchManager


@pytest.fixture
def mock_window():
    window = MagicMock()
    # Ensure window has necessary attributes
    window.db_path = "dummy.db"
    return window


@pytest.fixture
def manager(mock_window):
    search_manager = AISearchManager(mock_window)
    yield search_manager
    search_manager.shutdown()


@patch("src.services.semantic_search_worker.RAGService")
def test_perform_semantic_search_uses_rag(
    mock_rag_cls, manager, mock_window, qtbot
):
    """Test that perform_semantic_search uses RAGService when db_path is available."""
    # Setup
    mock_service = MagicMock()
    mock_rag_cls.return_value = mock_service
    # RAGService mock needs to allow instantiation

    expected_results = [{"id": 1, "name": "Test Entity", "score": 0.9}]
    mock_service.search.return_value = expected_results

    # Execute
    query = "Find test"
    manager.perform_semantic_search(query, "entity", 5)

    qtbot.waitUntil(
        lambda: mock_window.ai_search_panel.set_results.called,
        timeout=2000,
    )

    # Verify RAGService creation
    # Since we import RAGService inside the method, patching src.app.ai_search_manager.RAGService
    # might fail if it's not a module-level import.
    # However, 'from ... import RAGService' inside function creates a local name.
    # Patching 'src.services.rag_service.RAGService' (source) is safer.

    mock_rag_cls.assert_called_with("dummy.db")
    mock_service.search.assert_called_with(query=query, top_k=5, object_type="entity")

    # Verify results passed to panel
    mock_window.ai_search_panel.set_searching.assert_any_call(True)
    mock_window.ai_search_panel.set_results.assert_called_with(expected_results)
    mock_window.ai_search_panel.set_searching.assert_any_call(False)


def test_missing_db_path_reports_unavailable_world(manager, mock_window):
    """A search without an active world fails without touching a database."""
    # Simulate missing db_path on window
    if hasattr(mock_window, "db_path"):
        del mock_window.db_path

    manager.perform_semantic_search("Query", "event", 3)

    mock_window.ai_search_panel.set_status.assert_called_once_with(
        "Search failed: no active world database is available"
    )
    mock_window.ai_search_panel.set_searching.assert_not_called()


def test_rebuild_search_index_dispatches_to_worker(manager, mock_window):
    """Index rebuilds use the queued worker path instead of the GUI thread."""
    manager.rebuild_search_index("all")

    mock_window.status_bar.showMessage.assert_called_with(
        "Rebuilding all index...", 0
    )
    mock_window.worker_manager.rebuild_index_requested.emit.assert_called_once_with(
        "all", []
    )


def test_loading_v1_preferences_persists_v2_template_migration(
    manager, mock_window
):
    """The app manager upgrades legacy selections through the worker path."""
    manager.on_ai_preferences_loaded(
        {
            "version": 1,
            "selected_template_id": "description_default",
            "entity_prompt_draft": "Keep this draft",
        }
    )

    saved = mock_window.worker_manager.save_ai_preferences_requested.emit.call_args[0][0]
    assert saved["version"] == 2
    assert saved["selected_entity_template_id"] == "create_complete_description"
    assert saved["entity_prompt_draft"] == "Keep this draft"
