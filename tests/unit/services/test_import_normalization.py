"""Tests for import normalization logic."""

import pytest

from src.services.import_normalization import normalize_name


@pytest.mark.unit
class TestImportNormalization:
    """Tests for the normalize_name function."""

    def test_normalize_basic(self):
        """Should lowercase and trim simple strings."""
        assert normalize_name("Test") == "test"
        assert normalize_name("  Test  ") == "test"

    def test_normalize_internal_whitespace(self):
        """Should collapse multiple internal spaces."""
        assert normalize_name("Gandalf   the   Grey") == "gandalf the grey"
        assert normalize_name("  Gandalf    the    Grey  ") == "gandalf the grey"

    def test_normalize_empty(self):
        """Should return empty string for empty/whitespace input."""
        assert normalize_name("") == ""
        assert normalize_name("   ") == ""
        assert normalize_name(None) == ""

    def test_normalize_special_chars(self):
        """Should preserve special characters but lowercase them."""
        assert normalize_name("Björn-Ironside!") == "björn-ironside!"
