from unittest.mock import MagicMock, patch

import pytest

from src.services.summary_service import SummaryService


@pytest.fixture
def mock_db_service():
    return MagicMock()


@pytest.fixture
def summary_service(mock_db_service):
    return SummaryService(mock_db_service)


def test_get_provider_fallback_raises_error(summary_service):
    """Test that ValueError is raised if no provider is enabled."""
    with patch("PySide6.QtCore.QSettings") as MockSettings:
        settings = MockSettings.return_value
        settings.value.return_value = False  # All providers disabled

        with pytest.raises(ValueError, match="No AI provider is enabled"):
            summary_service._get_provider()


def test_get_provider_lmstudio(summary_service):
    """Test that LM Studio is selected if enabled."""
    with patch("PySide6.QtCore.QSettings") as MockSettings:
        settings = MockSettings.return_value

        # Mock settings.value to return True for lmstudio, False for others
        # settings.value takes (key, default, type)
        def side_effect(key, default, type=None):
            if key == "ai_gen_lmstudio_enabled":
                return True
            return False

        settings.value.side_effect = side_effect

        with patch("src.services.summary_service.create_provider") as mock_create:
            summary_service._get_provider()
            mock_create.assert_called_with("lmstudio")


def test_get_provider_priority(summary_service):
    """Test that priority is respected (LM Studio > OpenAI)."""
    with patch("PySide6.QtCore.QSettings") as MockSettings:
        settings = MockSettings.return_value

        # Both enabled
        def side_effect(key, default, type=None):
            if key == "ai_gen_lmstudio_enabled":
                return True
            if key == "ai_gen_openai_enabled":
                return True
            return False

        settings.value.side_effect = side_effect

        with patch("src.services.summary_service.create_provider") as mock_create:
            summary_service._get_provider()
            mock_create.assert_called_with("lmstudio")  # Should pick LM Studio
