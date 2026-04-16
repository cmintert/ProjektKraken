"""Unit tests for per-world AI audit log with rating support.

Covers:
- Routing audit entries to the per-world file via ``audit_path``
- ``RATING:`` line included in log entries
- ``COMMENT:`` line included when a comment is provided
- Fallback to global logger when ``audit_path`` is omitted
- ``SummaryService`` passes ``audit_path`` derived from ``db_path``
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from src.services.llm_provider import log_ai_interaction

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _audit_enabled(qapp):
    """Enable audit logging in QSettings for each test, then restore."""
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.setValue("ai_gen_audit_log", True)
    yield
    settings.setValue("ai_gen_audit_log", False)


# ============================================================================
# Tests
# ============================================================================


def test_writes_to_world_path():
    """log_ai_interaction with audit_path should call get_audit_logger_for_path."""
    fake_logger = MagicMock(spec=logging.Logger)

    with patch(
        "src.core.logging_config.get_audit_logger_for_path",
        return_value=fake_logger,
    ) as mock_get:
        log_ai_interaction(
            prompt="Test prompt",
            response_text="Test response",
            model="test-model",
            source="test",
            audit_path="/worlds/MyWorld/ai_audit_log.txt",
        )

    mock_get.assert_called_once_with("/worlds/MyWorld/ai_audit_log.txt")
    fake_logger.info.assert_called_once()


def test_includes_rating_positive_in_entry():
    """RATING line should say '👍 positive' when rating=1."""
    fake_logger = MagicMock(spec=logging.Logger)

    with patch(
        "src.core.logging_config.get_audit_logger_for_path",
        return_value=fake_logger,
    ):
        log_ai_interaction(
            prompt="p",
            response_text="r",
            model="m",
            source="s",
            rating=1,
            audit_path="/worlds/X/ai_audit_log.txt",
        )

    logged_text = fake_logger.info.call_args[0][0]
    assert "RATING:" in logged_text
    assert "positive" in logged_text


def test_includes_rating_negative_in_entry():
    """RATING line should say '👎 negative' when rating=-1."""
    fake_logger = MagicMock(spec=logging.Logger)

    with patch(
        "src.core.logging_config.get_audit_logger_for_path",
        return_value=fake_logger,
    ):
        log_ai_interaction(
            prompt="p",
            response_text="r",
            model="m",
            source="s",
            rating=-1,
            audit_path="/worlds/X/ai_audit_log.txt",
        )

    logged_text = fake_logger.info.call_args[0][0]
    assert "RATING:" in logged_text
    assert "negative" in logged_text


def test_includes_comment_in_entry():
    """COMMENT line should appear when rating_comment is provided."""
    fake_logger = MagicMock(spec=logging.Logger)

    with patch(
        "src.core.logging_config.get_audit_logger_for_path",
        return_value=fake_logger,
    ):
        log_ai_interaction(
            prompt="p",
            response_text="r",
            model="m",
            source="s",
            rating=1,
            rating_comment="Great tone",
            audit_path="/worlds/X/ai_audit_log.txt",
        )

    logged_text = fake_logger.info.call_args[0][0]
    assert "COMMENT:" in logged_text
    assert "Great tone" in logged_text


def test_falls_back_to_global_when_no_path():
    """Without audit_path, the global get_audit_logger should be used."""
    fake_global_logger = MagicMock(spec=logging.Logger)

    with patch(
        "src.core.logging_config.get_audit_logger",
        return_value=fake_global_logger,
    ) as mock_global:
        log_ai_interaction(
            prompt="p",
            response_text="r",
            model="m",
            source="s",
        )

    mock_global.assert_called_once()
    fake_global_logger.info.assert_called_once()


def test_summary_service_passes_audit_path():
    """SummaryService.generate_summary should pass audit_path derived from db_path."""
    from src.services.summary_service import SummaryService

    db_path = "/worlds/Test/test.kraken"
    expected_audit_path = os.path.join("/worlds/Test", "ai_audit_log.txt")

    # Minimal mock db_service
    mock_db = MagicMock()
    mock_db.db_path = db_path

    service = SummaryService(mock_db)

    # Mock entity
    from src.core.entities import Entity

    entity = Entity(
        id=1,
        name="Aldric",
        type="Person",
        description="A knight.",
        attributes={},
    )

    # Mock provider
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {"text": "A brave knight.", "model": "mock"}
    service._llm_provider = mock_provider

    with patch("src.services.summary_service.log_ai_interaction") as mock_log, patch(
        "src.services.reasoning_filter.filter_reasoning_tags", side_effect=lambda x: x
    ):
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.setValue("ai_gen_filter_reasoning", True)

        service.generate_summary(entity)

    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs.get("audit_path") == expected_audit_path
