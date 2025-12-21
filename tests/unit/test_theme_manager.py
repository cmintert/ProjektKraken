import logging
from unittest.mock import mock_open, patch

import pytest

from src.core.theme_manager import ThemeManager


@pytest.fixture
def clean_theme_manager():
    """
    Provides a clean ThemeManager instance for testing.

    Note: After tests using this fixture, the singleton is restored
    to ensure other tests have a properly initialized ThemeManager.
    """
    # Save the current instance
    original_instance = ThemeManager._instance

    # Reset singleton for test
    ThemeManager._instance = None
    tm = ThemeManager(theme_file="dummy_themes.json")

    yield tm

    # Restore the original instance
    ThemeManager._instance = original_instance


def test_singleton(clean_theme_manager):
    tm1 = ThemeManager()
    tm2 = ThemeManager()
    assert tm1 is tm2


def test_default_theme_fallback(clean_theme_manager):
    # Ensure fallback theme is loaded if file missing
    with patch("os.path.exists", return_value=False):
        clean_theme_manager._load_themes()
        theme = clean_theme_manager.get_theme()
        assert theme["app_bg"] == "#2B2B2B"  # Default Dark Mode


def test_load_themes_success(clean_theme_manager):
    mock_json = (
        '{"dark_mode": {"app_bg": "#000000"}, "light_mode": {"app_bg": "#FFFFFF"}}'
    )
    with patch("builtins.open", mock_open(read_data=mock_json)):
        with patch("os.path.exists", return_value=True):
            clean_theme_manager._load_themes()
            assert clean_theme_manager.themes["dark_mode"]["app_bg"] == "#000000"


def test_apply_theme_success(clean_theme_manager):
    class MockApp:
        def __init__(self):
            self.style = ""

        def setStyleSheet(self, s):
            self.style = s

    app = MockApp()
    template = "QWidget {{ background-color: {app_bg}; }}"

    # Mock theme data
    clean_theme_manager.themes = {"dark_mode": {"app_bg": "#123456"}}
    clean_theme_manager.apply_theme(app, template)

    assert "background-color: #123456;" in app.style


def test_apply_theme_error(clean_theme_manager, caplog):
    app = None  # Won't be used
    template = "QWidget {{ color: {missing_key}; }}"

    clean_theme_manager.themes = {"dark_mode": {"app_bg": "#000"}}

    with caplog.at_level(logging.ERROR):
        clean_theme_manager.apply_theme(app, template)

    assert "Theme Error: Missing key" in caplog.text
