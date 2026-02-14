"""Unit tests for RAG similarity threshold filtering.

Tests that RAGService filters out low-score semantic results
to prevent noisy/irrelevant context injection.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.rag_service import RAGService


@pytest.fixture
def mock_search_service_with_scores():
    """Create a mock search service returning results with varying scores."""
    service = MagicMock()
    service.search_by_name.return_value = []
    service.query.return_value = [
        {
            "id": "emb-1",
            "object_id": "uuid-1",
            "name": "Relevant Entity",
            "type": "character",
            "score": 0.85,
            "text_content": "Name: Relevant Entity\n\nDescription: Very relevant.",
        },
        {
            "id": "emb-2",
            "object_id": "uuid-2",
            "name": "Marginal Entity",
            "type": "location",
            "score": 0.30,
            "text_content": "Name: Marginal Entity\n\nDescription: Somewhat relevant.",
        },
        {
            "id": "emb-3",
            "object_id": "uuid-3",
            "name": "Noise Entity",
            "type": "item",
            "score": 0.10,
            "text_content": "Name: Noise Entity\n\nDescription: Irrelevant noise.",
        },
    ]
    return service


def test_rag_filters_low_score_results(mock_search_service_with_scores):
    """Test that results below min_score threshold are filtered out."""
    with (
        patch(
            "src.services.rag_service.create_search_service",
            return_value=mock_search_service_with_scores,
        ),
        patch("sqlite3.connect"),
    ):
        # Use a threshold of 0.25 (default)
        service = RAGService(":memory:")
        context = service.get_context("Tell me about characters")

        # High-score result should be present
        assert "Relevant Entity" in context
        # Marginal result (0.30) is above default threshold (0.25)
        assert "Marginal Entity" in context
        # Low-score result (0.10) should be filtered out
        assert "Noise Entity" not in context


def test_rag_custom_threshold(mock_search_service_with_scores):
    """Test that custom min_score threshold is respected."""
    with (
        patch(
            "src.services.rag_service.create_search_service",
            return_value=mock_search_service_with_scores,
        ),
        patch("sqlite3.connect"),
    ):
        # Use a high threshold that only keeps the best result
        service = RAGService(":memory:", min_score=0.50)
        context = service.get_context("Tell me about characters")

        assert "Relevant Entity" in context
        # Both lower-score results should be filtered
        assert "Marginal Entity" not in context
        assert "Noise Entity" not in context


def test_rag_zero_threshold_keeps_all(mock_search_service_with_scores):
    """Test that min_score=0.0 keeps all results."""
    with (
        patch(
            "src.services.rag_service.create_search_service",
            return_value=mock_search_service_with_scores,
        ),
        patch("sqlite3.connect"),
    ):
        service = RAGService(":memory:", min_score=0.0)
        context = service.get_context("Tell me about characters")

        assert "Relevant Entity" in context
        assert "Marginal Entity" in context
        assert "Noise Entity" in context


def test_rag_lexical_results_bypass_threshold(mock_search_service_with_scores):
    """Test that lexical (direct mention) results are not filtered by score."""
    mock_search_service_with_scores.search_by_name.return_value = [
        {
            "id": "uuid-lexical",
            "name": "Direct Match",
            "type": "character",
            "text_content": "Name: Direct Match\n\nDescription: Exact name hit.",
        }
    ]

    with (
        patch(
            "src.services.rag_service.create_search_service",
            return_value=mock_search_service_with_scores,
        ),
        patch("sqlite3.connect"),
    ):
        # Even with high threshold, lexical results should appear
        service = RAGService(":memory:", min_score=0.99)
        context = service.get_context("Direct Match")

        assert "Direct Match" in context
        assert "(character)" in context
