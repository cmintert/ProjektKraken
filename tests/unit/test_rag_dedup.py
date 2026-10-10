import logging
from unittest.mock import MagicMock, patch

import pytest

from src.services.rag_service import RAGService


@pytest.fixture
def mock_search_service():
    service = MagicMock()
    # Mock result with "Green Box 224"
    service.search_by_name.return_value = [
        {
            "id": "lexical_uuid-1",
            "object_type": "entity",
            "object_id": "uuid-1",
            "name": "Green Box 224",
            "type": "location",
            "text_content": "Old Description",
        }
    ]
    service.query.return_value = []
    return service


def test_hybrid_merge_uses_world_object_identity_without_mutating_sources():
    service = RAGService(":memory:")
    lexical = [
        {
            "id": "lexical_shared",
            "object_type": "entity",
            "object_id": "shared",
            "name": "Harbor",
        },
        {
            "id": "lexical_other",
            "object_type": "entity",
            "object_id": "other",
            "name": "Harbor",
        },
    ]
    semantic = [
        {
            "id": "embedding_1",
            "object_type": "entity",
            "object_id": "shared",
            "name": "Harbor",
            "score": 0.9,
        },
        {
            "id": "embedding_2",
            "object_type": "event",
            "object_id": "shared",
            "name": "Harbor",
            "score": 0.8,
        },
    ]

    merged = service._merge_results(lexical, semantic, target_k=1)

    assert [(r["object_type"], r["object_id"]) for r in merged] == [
        ("entity", "shared"),
        ("entity", "other"),
        ("event", "shared"),
    ]
    assert [r["_match_type"] for r in merged] == [
        "Direct Mention",
        "Direct Mention",
        "Semantic",
    ]
    assert all("_match_type" not in r for r in lexical + semantic)


def test_hybrid_merge_bounds_semantic_additions_after_unique_mentions():
    service = RAGService(":memory:")
    lexical = [
        {"object_type": "entity", "object_id": "a"},
        {"object_type": "entity", "object_id": "a"},
        {"object_type": "entity", "object_id": "b"},
    ]
    semantic = [
        {"object_type": "entity", "object_id": "a", "score": 0.9},
        {"object_type": "entity", "object_id": "c", "score": 0.8},
        {"object_type": "entity", "object_id": "d", "score": 0.7},
    ]

    merged = service._merge_results(lexical, semantic, target_k=1)

    assert [r["object_id"] for r in merged] == ["a", "b", "c"]


def test_exact_object_exclusion_keeps_same_named_other_object():
    service = RAGService(":memory:")
    results = [
        {"object_type": "entity", "object_id": "current", "name": "Harbor"},
        {"object_type": "entity", "object_id": "other", "name": "Harbor"},
    ]
    with (
        patch.object(service, "search", return_value=results),
        patch.object(service, "_fetch_relations_for_results", return_value={}),
    ):
        context = service.get_context("Harbor", exclude_object=("entity", "current"))

    assert context == "Harbor (Unknown)"


@pytest.mark.parametrize("level", [logging.INFO, logging.DEBUG])
def test_retrieval_query_content_stays_out_of_ordinary_logs(level, caplog):
    secret = "KRT67_SYNTHETIC_PRIVATE_QUERY_7d92"
    search_service = MagicMock()
    search_service.search_by_name.return_value = []
    search_service.query.return_value = [
        {
            "id": "embedding-1",
            "object_type": "entity",
            "object_id": "entity-1",
            "name": secret,
            "score": 0.1,
        }
    ]

    with (
        caplog.at_level(level),
        patch(
            "src.services.rag_service.create_search_service",
            return_value=search_service,
        ),
        patch("sqlite3.connect"),
    ):
        assert RAGService(":memory:").search(secret) == []

    assert secret not in caplog.text
    if level == logging.DEBUG:
        assert "query_chars=" in caplog.text


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
        assert "(location)" in context_dirty

        # Act 2: With exclusion
        context_clean = service.get_context(
            "Tell me about Green Box 224", exclude_names=["Green Box 224"]
        )

        # Assert
        assert "Green Box 224" not in context_clean


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
