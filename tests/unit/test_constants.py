"""
Tests for application constants.
"""

from src.app.constants import (
    AUTOSAVE_DELAY_MS,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    IMAGE_FILE_FILTER,
    SETTINGS_ACTIVE_DB_KEY,
    SETTINGS_AUTO_RELATION_KEY,
    SETTINGS_FILTER_CONFIG_KEY,
    SETTINGS_LAST_ITEM_ID_KEY,
    SETTINGS_LAST_ITEM_TYPE_KEY,
    SETTINGS_LAYOUTS_KEY,
    SETTINGS_WORKSPACE_LAYOUT_KEY,
    STATUS_DB_INIT_FAIL,
    STATUS_ERROR_PREFIX,
    SUPPORTED_IMAGE_FORMATS,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
    WINDOW_TITLE,
)
from src.gui.workspace import WORKSPACE_LAYOUT_VERSION


def test_window_constants():
    """Test window configuration constants are defined correctly."""
    assert isinstance(WINDOW_TITLE, str)
    assert "Kraken" in WINDOW_TITLE
    assert isinstance(DEFAULT_WINDOW_WIDTH, int)
    assert isinstance(DEFAULT_WINDOW_HEIGHT, int)
    assert DEFAULT_WINDOW_WIDTH > 0
    assert DEFAULT_WINDOW_HEIGHT > 0


def test_settings_keys():
    """Test settings key constants are properly defined."""
    assert isinstance(WINDOW_SETTINGS_KEY, str)
    assert isinstance(WINDOW_SETTINGS_APP, str)
    assert isinstance(SETTINGS_ACTIVE_DB_KEY, str)
    assert isinstance(SETTINGS_LAYOUTS_KEY, str)
    assert isinstance(SETTINGS_LAST_ITEM_ID_KEY, str)
    assert isinstance(SETTINGS_LAST_ITEM_TYPE_KEY, str)
    assert isinstance(SETTINGS_AUTO_RELATION_KEY, str)
    assert isinstance(SETTINGS_FILTER_CONFIG_KEY, str)
    assert isinstance(SETTINGS_WORKSPACE_LAYOUT_KEY, str)


def test_workspace_layout_version():
    """Workspace layout state uses a positive integer schema version."""
    assert isinstance(WORKSPACE_LAYOUT_VERSION, int)
    assert WORKSPACE_LAYOUT_VERSION > 0


def test_status_messages():
    """Test status message constants."""
    assert isinstance(STATUS_DB_INIT_FAIL, str)
    assert isinstance(STATUS_ERROR_PREFIX, str)
    assert len(STATUS_DB_INIT_FAIL) > 0
    assert len(STATUS_ERROR_PREFIX) > 0


def test_image_format_constants():
    """Test image format constants."""
    assert isinstance(SUPPORTED_IMAGE_FORMATS, list)
    assert len(SUPPORTED_IMAGE_FORMATS) > 0

    # All formats should be lowercase strings
    for fmt in SUPPORTED_IMAGE_FORMATS:
        assert isinstance(fmt, str)
        assert fmt.islower()

    # Should include common formats
    assert "png" in SUPPORTED_IMAGE_FORMATS
    assert "jpg" in SUPPORTED_IMAGE_FORMATS or "jpeg" in SUPPORTED_IMAGE_FORMATS


def test_image_file_filter():
    """Test image file filter constant."""
    assert isinstance(IMAGE_FILE_FILTER, str)
    assert "Images" in IMAGE_FILE_FILTER

    # Should contain format wildcards
    for fmt in SUPPORTED_IMAGE_FORMATS:
        assert f"*.{fmt}" in IMAGE_FILE_FILTER


def test_autosave_delay():
    """Test autosave delay constant."""
    assert isinstance(AUTOSAVE_DELAY_MS, int)
    assert AUTOSAVE_DELAY_MS > 0
    # Should be a reasonable delay (not too short, not too long)
    assert 100 <= AUTOSAVE_DELAY_MS <= 10000


def test_window_dimensions_reasonable():
    """Test that default window dimensions are reasonable."""
    # Should be at least 640x480
    assert DEFAULT_WINDOW_WIDTH >= 640
    assert DEFAULT_WINDOW_HEIGHT >= 480

    # Should not be excessively large
    assert DEFAULT_WINDOW_WIDTH <= 4000
    assert DEFAULT_WINDOW_HEIGHT <= 4000

    # Should have reasonable aspect ratio
    aspect_ratio = DEFAULT_WINDOW_WIDTH / DEFAULT_WINDOW_HEIGHT
    assert 1.0 <= aspect_ratio <= 2.5


def test_settings_keys_unique():
    """Test that all settings keys are unique."""
    settings_keys = [
        SETTINGS_ACTIVE_DB_KEY,
        SETTINGS_LAYOUTS_KEY,
        SETTINGS_LAST_ITEM_ID_KEY,
        SETTINGS_LAST_ITEM_TYPE_KEY,
        SETTINGS_AUTO_RELATION_KEY,
        SETTINGS_FILTER_CONFIG_KEY,
        SETTINGS_WORKSPACE_LAYOUT_KEY,
    ]

    assert len(settings_keys) == len(set(settings_keys))


def test_constants_are_immutable_types():
    """Test that constants use immutable types where appropriate."""
    # Strings should be immutable (Python strings are always immutable)
    assert isinstance(WINDOW_TITLE, str)
    assert isinstance(SETTINGS_WORKSPACE_LAYOUT_KEY, str)

    # Numbers should be immutable
    assert isinstance(DEFAULT_WINDOW_WIDTH, int)
    assert isinstance(AUTOSAVE_DELAY_MS, int)

    # Lists are mutable but that's acceptable for SUPPORTED_IMAGE_FORMATS
    # as long as it's not modified at runtime


def test_window_settings_format():
    """Test window settings key format."""
    # Should be proper organization name format
    assert WINDOW_SETTINGS_KEY.replace(" ", "") == WINDOW_SETTINGS_KEY
    assert WINDOW_SETTINGS_APP.replace(" ", "") == WINDOW_SETTINGS_APP
