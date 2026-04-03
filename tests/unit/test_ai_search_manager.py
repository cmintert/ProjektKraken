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
    return AISearchManager(mock_window)


@patch("src.services.rag_service.RAGService")
def test_perform_semantic_search_uses_rag(mock_rag_cls, manager, mock_window):
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


@patch("src.services.search_service.create_search_service")
def test_fallback_when_no_db_path(mock_create_service, manager, mock_window):
    """Test fallback to raw SearchService when db_path is missing."""
    # Simulate missing db_path on window
    if hasattr(mock_window, "db_path"):
        del mock_window.db_path

    # Setup mock fallback service
    mock_search_service = MagicMock()
    mock_create_service.return_value = mock_search_service
    expected_results = [{"id": 2, "name": "Fallback", "score": 0.5}]
    mock_search_service.query.return_value = expected_results

    # Execute
    manager.perform_semantic_search("Query", "event", 3)

    # Verify fallback usage
    mock_create_service.assert_called()
    mock_search_service.query.assert_called_with(
        text="Query", object_type="event", top_k=3
    )

    # Verify results passed to panel
    mock_window.ai_search_panel.set_results.assert_called_with(expected_results)


@patch("src.services.search_service.create_search_service")
def test_rebuild_search_index_handles_import_error(
    mock_create_service, manager, mock_window
):
    """rebuild_search_index shows a clear error when sentence-transformers is missing."""
    mock_create_service.side_effect = ImportError(
        "sentence-transformers is not installed. "
        "Semantic search requires it. "
        "Run: pip install sentence-transformers"
    )
    mock_window.gui_db_service._connection = MagicMock()

    manager.rebuild_search_index("all")

    # Status bar and panel should show the user-friendly first line
    mock_window.status_bar.showMessage.assert_called()
    call_args = mock_window.status_bar.showMessage.call_args[0]
    assert "sentence-transformers" in call_args[0]
    mock_window.ai_search_panel.set_status.assert_called()
