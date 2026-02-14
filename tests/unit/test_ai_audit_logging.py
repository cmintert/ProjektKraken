"""Unit tests for AI Audit Logging.

Tests the audit logger configuration and the ``log_ai_interaction`` helper
function, verifying that prompts and responses are logged only when auditing
is enabled.
"""

import logging
import os
import tempfile
from unittest.mock import patch

import pytest

from src.core.logging_config import (
    AUDIT_LOG_FILENAME,
    get_audit_logger,
    setup_audit_logging,
)
from src.services.llm_provider import log_ai_interaction


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _clean_audit_logger():
    """Remove all handlers from the audit logger between tests."""
    audit_logger = logging.getLogger("ai_audit")
    # Close existing handlers to release file locks (Windows)
    for handler in audit_logger.handlers[:]:
        handler.close()
    audit_logger.handlers.clear()
    yield
    for handler in audit_logger.handlers[:]:
        handler.close()
    audit_logger.handlers.clear()


@pytest.fixture
def audit_settings():
    """Provide QSettings helpers for toggling audit log on/off."""
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    yield settings
    # Cleanup
    settings.remove("ai_gen_audit_log")


# ============================================================================
# Logger Configuration Tests
# ============================================================================


def test_get_audit_logger_returns_named_logger():
    """get_audit_logger should return the 'ai_audit' logger."""
    audit = get_audit_logger()
    assert audit.name == "ai_audit"


def test_setup_audit_logging_creates_handler():
    """setup_audit_logging should add a handler to the ai_audit logger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.core.logging_config.LOG_DIR", tmpdir):
            setup_audit_logging()

        audit = logging.getLogger("ai_audit")
        assert len(audit.handlers) >= 1


def test_setup_audit_logging_no_propagation():
    """Audit logger should not propagate to the root logger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.core.logging_config.LOG_DIR", tmpdir):
            setup_audit_logging()

    audit = logging.getLogger("ai_audit")
    assert audit.propagate is False


def test_setup_audit_logging_idempotent():
    """Calling setup_audit_logging twice should not duplicate handlers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.core.logging_config.LOG_DIR", tmpdir):
            setup_audit_logging()
            handler_count = len(logging.getLogger("ai_audit").handlers)
            setup_audit_logging()
            assert len(logging.getLogger("ai_audit").handlers) == handler_count


# ============================================================================
# log_ai_interaction Tests
# ============================================================================


def test_log_ai_interaction_disabled_by_default(audit_settings):
    """When audit log is disabled (default), nothing should be logged."""
    audit_settings.setValue("ai_gen_audit_log", False)

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.core.logging_config.LOG_DIR", tmpdir):
            setup_audit_logging()

            log_ai_interaction(
                prompt="Test prompt",
                response_text="Test response",
                model="test-model",
                source="test",
            )

            # Flush and close handlers before checking file
            audit = logging.getLogger("ai_audit")
            for h in audit.handlers:
                h.flush()
                h.close()

            audit_path = os.path.join(tmpdir, AUDIT_LOG_FILENAME)
            # File should not exist (delay=True) because no write happened
            assert not os.path.exists(audit_path)


def test_log_ai_interaction_enabled_writes_to_file(audit_settings):
    """When audit log is enabled, prompt and response should appear in file."""
    audit_settings.setValue("ai_gen_audit_log", True)

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.core.logging_config.LOG_DIR", tmpdir):
            setup_audit_logging()

            log_ai_interaction(
                prompt="Summarize this entity",
                response_text="This is the summary.",
                model="test-model-7b",
                source="SummaryService",
            )

            # Flush and close handlers before reading file
            audit = logging.getLogger("ai_audit")
            for h in audit.handlers:
                h.flush()
                h.close()

            audit_path = os.path.join(tmpdir, AUDIT_LOG_FILENAME)
            assert os.path.exists(audit_path)

            content = open(audit_path, encoding="utf-8").read()
            assert "Summarize this entity" in content
            assert "This is the summary." in content
            assert "test-model-7b" in content
            assert "SummaryService" in content


def test_log_ai_interaction_with_dict_prompt(audit_settings):
    """Dict prompts (system/user) should be formatted properly in the log."""
    audit_settings.setValue("ai_gen_audit_log", True)

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.core.logging_config.LOG_DIR", tmpdir):
            setup_audit_logging()

            prompt = {
                "system": "You are a fantasy writer.",
                "user": "Describe a castle.",
            }
            log_ai_interaction(
                prompt=prompt,
                response_text="A towering stone castle...",
                model="llama-7b",
                source="LLMGenerationWidget",
            )

            # Flush and close handlers before reading file
            audit = logging.getLogger("ai_audit")
            for h in audit.handlers:
                h.flush()
                h.close()

            audit_path = os.path.join(tmpdir, AUDIT_LOG_FILENAME)
            content = open(audit_path, encoding="utf-8").read()
            assert "[system] You are a fantasy writer." in content
            assert "[user] Describe a castle." in content
            assert "A towering stone castle..." in content
            assert "LLMGenerationWidget" in content


def test_log_ai_interaction_contains_separator(audit_settings):
    """Log entries should contain visual separators for readability."""
    audit_settings.setValue("ai_gen_audit_log", True)

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.core.logging_config.LOG_DIR", tmpdir):
            setup_audit_logging()

            log_ai_interaction(
                prompt="Hello",
                response_text="Hi there!",
                model="m",
                source="s",
            )

            audit = logging.getLogger("ai_audit")
            for h in audit.handlers:
                h.flush()
                h.close()

            audit_path = os.path.join(tmpdir, AUDIT_LOG_FILENAME)
            content = open(audit_path, encoding="utf-8").read()
            assert "PROMPT:" in content
            assert "RESPONSE:" in content
            assert "=" * 60 in content
