"""Integration-focused tests for per-world AI audit events."""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _audit_enabled(qapp):
    """Enable audit logging for each test, then restore the setting."""
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.setValue("ai_gen_audit_log", True)
    yield
    settings.setValue("ai_gen_audit_log", False)


def test_summary_service_logs_generation_and_automatic_review():
    """Automatic summaries should emit linked generation and review events."""
    from src.core.entities import Entity
    from src.services.summary_service import SummaryService

    db_path = "/worlds/Test/test.kraken"
    expected_audit_path = os.path.join("/worlds/Test", "ai_audit_log.jsonl")
    mock_db = MagicMock()
    mock_db.db_path = db_path
    service = SummaryService(mock_db)
    entity = Entity(
        id=1,
        name="Aldric",
        type="Person",
        description="A knight.",
        attributes={},
    )
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {
        "text": "Knight.",
        "model": "mock",
        "usage": {"total_tokens": 8},
    }
    mock_provider.metadata.return_value = {"provider_id": "mock-provider"}
    service._llm_provider = mock_provider

    with patch(
        "src.services.summary_service.log_generation_event"
    ) as generation_log, patch(
        "src.services.summary_service.log_review_event"
    ) as review_log, patch(
        "src.services.reasoning_filter.filter_reasoning_tags",
        side_effect=lambda text: text,
    ):
        service.generate_summary(entity)

    generation_log.assert_called_once()
    review_log.assert_called_once()
    generation_kwargs = generation_log.call_args.kwargs
    review_kwargs = review_log.call_args.kwargs
    assert generation_kwargs["audit_path"] == expected_audit_path
    assert generation_kwargs["response"]["text"] == "Knight."
    assert generation_kwargs["interaction_id"] == review_kwargs["interaction_id"]
    assert review_kwargs["action"] == "automatic"
    assert review_kwargs["reviewed_text"] == "Knight."
