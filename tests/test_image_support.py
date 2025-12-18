import pytest
from PySide6.QtGui import QImageReader
from src.app.constants import SUPPORTED_IMAGE_FORMATS, IMAGE_FILE_FILTER

def test_webp_is_supported_by_qt():
    """Verify that the running Qt environment supports WebP."""
    supported_formats = [f.data().decode('utf-8') for f in QImageReader.supportedImageFormats()]
    assert 'webp' in supported_formats, "WebP format not supported by Qt installation"

def test_webp_in_constants():
    """Verify that WebP is included in the application constants."""
    assert 'webp' in SUPPORTED_IMAGE_FORMATS
    assert '*.webp' in IMAGE_FILE_FILTER
