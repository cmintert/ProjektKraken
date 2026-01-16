"""
Tests for application constants.
"""
import pytest

from src.app.constants import (
    AUTOSAVE_DELAY_MS,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    DOCK_OBJ_AI_SEARCH,
    DOCK_OBJ_ENTITY_INSPECTOR,
    DOCK_OBJ_EVENT_INSPECTOR,
    DOCK_OBJ_GRAPH,
    DOCK_OBJ_LONGFORM,
    DOCK_OBJ_MAP,
    DOCK_OBJ_PROJECT,
    DOCK_OBJ_TIMELINE,
    DOCK_TITLE_AI_SEARCH,
    DOCK_TITLE_ENTITY_INSPECTOR,
    DOCK_TITLE_EVENT_INSPECTOR,
    DOCK_TITLE_GRAPH,
    DOCK_TITLE_LONGFORM,
    DOCK_TITLE_MAP,
    DOCK_TITLE_PROJECT,
    DOCK_TITLE_TIMELINE,
    IMAGE_FILE_FILTER,
    LAYOUT_VERSION,
    SETTINGS_ACTIVE_DB_KEY,
    SETTINGS_AUTO_RELATION_KEY,
    SETTINGS_FILTER_CONFIG_KEY,
    SETTINGS_LAST_ITEM_ID_KEY,
    SETTINGS_LAST_ITEM_TYPE_KEY,
    SETTINGS_LAYOUT_VERSION_KEY,
    SETTINGS_LAYOUTS_KEY,
    STATUS_DB_INIT_FAIL,
    STATUS_ERROR_PREFIX,
    SUPPORTED_IMAGE_FORMATS,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
    WINDOW_TITLE,
)


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
    assert isinstance(SETTINGS_LAYOUT_VERSION_KEY, str)


def test_layout_version():
    """Test layout version constant."""
    assert isinstance(LAYOUT_VERSION, str)
    # Should be in semantic version format (X.Y.Z)
    parts = LAYOUT_VERSION.split(".")
    assert len(parts) == 3
    for part in parts:
        assert part.isdigit()


def test_dock_object_names():
    """Test dock object name constants."""
    dock_names = [
        DOCK_OBJ_PROJECT,
        DOCK_OBJ_EVENT_INSPECTOR,
        DOCK_OBJ_ENTITY_INSPECTOR,
        DOCK_OBJ_TIMELINE,
        DOCK_OBJ_LONGFORM,
        DOCK_OBJ_MAP,
        DOCK_OBJ_AI_SEARCH,
        DOCK_OBJ_GRAPH,
    ]
    
    # All dock names should be unique
    assert len(dock_names) == len(set(dock_names))
    
    # All should end with "Dock"
    for name in dock_names:
        assert isinstance(name, str)
        assert name.endswith("Dock")


def test_dock_titles():
    """Test dock title constants."""
    dock_titles = [
        DOCK_TITLE_PROJECT,
        DOCK_TITLE_EVENT_INSPECTOR,
        DOCK_TITLE_ENTITY_INSPECTOR,
        DOCK_TITLE_TIMELINE,
        DOCK_TITLE_LONGFORM,
        DOCK_TITLE_MAP,
        DOCK_TITLE_AI_SEARCH,
        DOCK_TITLE_GRAPH,
    ]
    
    # All dock titles should be unique
    assert len(dock_titles) == len(set(dock_titles))
    
    # All should be non-empty strings
    for title in dock_titles:
        assert isinstance(title, str)
        assert len(title) > 0


def test_dock_name_title_pairing():
    """Test that dock names and titles have matching counts."""
    dock_names = [
        DOCK_OBJ_PROJECT,
        DOCK_OBJ_EVENT_INSPECTOR,
        DOCK_OBJ_ENTITY_INSPECTOR,
        DOCK_OBJ_TIMELINE,
        DOCK_OBJ_LONGFORM,
        DOCK_OBJ_MAP,
        DOCK_OBJ_AI_SEARCH,
        DOCK_OBJ_GRAPH,
    ]
    
    dock_titles = [
        DOCK_TITLE_PROJECT,
        DOCK_TITLE_EVENT_INSPECTOR,
        DOCK_TITLE_ENTITY_INSPECTOR,
        DOCK_TITLE_TIMELINE,
        DOCK_TITLE_LONGFORM,
        DOCK_TITLE_MAP,
        DOCK_TITLE_AI_SEARCH,
        DOCK_TITLE_GRAPH,
    ]
    
    # Should have same number of names and titles
    assert len(dock_names) == len(dock_titles)


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
        SETTINGS_LAYOUT_VERSION_KEY,
    ]
    
    assert len(settings_keys) == len(set(settings_keys))


def test_constants_are_immutable_types():
    """Test that constants use immutable types where appropriate."""
    # Strings should be immutable (Python strings are always immutable)
    assert isinstance(WINDOW_TITLE, str)
    assert isinstance(DOCK_OBJ_PROJECT, str)
    
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
