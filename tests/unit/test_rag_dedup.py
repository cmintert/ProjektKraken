from unittest.mock import MagicMock, patch

import pytest

from src.services.rag_service import RAGService


@pytest.fixture
def mock_search_service():
    service = MagicMock()
    # Mock result with "Green Box 224"
    service.search_by_name.return_value = [
        {
            "id": "uuid-1",
            "name": "Green Box 224",
            "type": "location",
            "text_content": "Old Description",
        }
    ]
    service.query.return_value = []
    return service


def test_rag_deduplication(mock_search_service):
    """Test that exclude_names filters out direct mentions."""
    # Setup
    with (
        patch(
            "src.services.rag_service.create_search_service",
            return_value=mock_search_service,
        ),
        patch("sqlite3.connect"),
    ):

        service = RAGService(":memory:")

        # Act 1: Without exclusion
        context_dirty = service.get_context(
            "Tell me about Green Box 224", exclude_names=[]
        )
        assert "Green Box 224" in context_dirty
        assert "(Direct Mention)" in context_dirty

        # Act 2: With exclusion
        context_clean = service.get_context(
            "Tell me about Green Box 224", exclude_names=["Green Box 224"]
        )

        # Assert
        assert "Green Box 224" not in context_clean
        assert "(Direct Mention)" not in context_clean


def test_rag_case_insensitive_deduplication(mock_search_service):
    """Test that exclusion is case-insensitive."""
    with (
        patch(
            "src.services.rag_service.create_search_service",
            return_value=mock_search_service,
        ),
        patch("sqlite3.connect"),
    ):

        service = RAGService(":memory:")
        context = service.get_context("prompt", exclude_names=["green box 224"])

        assert "Green Box 224" not in context
