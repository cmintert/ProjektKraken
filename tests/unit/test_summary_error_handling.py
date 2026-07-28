from unittest.mock import MagicMock

import pytest

from src.core.entities import Entity
from src.services.summary_service import SummaryService


@pytest.fixture
def mock_db_service():
    return MagicMock()


@pytest.fixture
def summary_service(mock_db_service):
    return SummaryService(mock_db_service)


@pytest.fixture
def entity():
    return Entity(
        id="ent_1",
        name="Test Entity",
        description=" ".join(f"source-{index}" for index in range(20)),
        type="Location",
    )


def test_generate_summary_timeout(summary_service, entity):
    """Test that TimeoutError raises RuntimeError with friendly message."""
    mock_provider = MagicMock()
    mock_provider.generate.side_effect = TimeoutError("Request timed out")

    summary_service._llm_provider = mock_provider

    with pytest.raises(RuntimeError, match="The AI provider timed out"):
        summary_service.generate_summary(entity)


def test_generate_summary_connection_error(summary_service, entity):
    """Test that ConnectionError raises RuntimeError with friendly message."""
    mock_provider = MagicMock()
    mock_provider.generate.side_effect = ConnectionError("Connection refused")

    summary_service._llm_provider = mock_provider

    with pytest.raises(RuntimeError, match="Could not connect to the AI provider"):
        summary_service.generate_summary(entity)


def test_generate_summary_generic_error(summary_service, entity):
    """Test that generic Exception raises RuntimeError with original message."""
    mock_provider = MagicMock()
    mock_provider.generate.side_effect = Exception("Some random API error")

    summary_service._llm_provider = mock_provider

    with pytest.raises(RuntimeError, match="Generation failed: Some random API error"):
        summary_service.generate_summary(entity)


def test_generate_summary_connection_refused_string(summary_service, entity):
    """Test that 'Connection refused' string in Exception is handled clearly."""
    mock_provider = MagicMock()
    mock_provider.generate.side_effect = Exception(
        "Max retries exceeded with url: ... Connection refused"
    )

    summary_service._llm_provider = mock_provider

    with pytest.raises(
        RuntimeError, match="Connection refused. Please ensure your local AI server"
    ):
        summary_service.generate_summary(entity)
