"""
Unit Tests for Protocol Interfaces.

Tests the Protocol interfaces defined in src/core/protocols.py to ensure
they properly validate structural subtyping and enforce contracts.
"""

import pytest

from src.core.protocols import MainWindowProtocol, TimelineDataProvider


class TestMainWindowProtocol:
    """Test the MainWindowProtocol interface."""

    def test_valid_implementation(self):
        """Test that a class implementing required methods satisfies the protocol."""

        class ValidMainWindow:
            """Mock MainWindow that implements the protocol."""

            def __init__(self):
                self.worker = object()
                self.command_requested = object()

            def _on_configure_grouping_requested(self):
                pass

            def _on_clear_grouping_requested(self):
                pass

        window = ValidMainWindow()
        assert isinstance(window, MainWindowProtocol)

    def test_missing_method(self):
        """Test that a class missing required methods does not satisfy the protocol."""

        class IncompleteWindow:
            """Mock MainWindow missing required methods."""

            def __init__(self):
                self.worker = object()
                self.command_requested = object()

            def _on_configure_grouping_requested(self):
                pass
            # Missing _on_clear_grouping_requested

        window = IncompleteWindow()
        assert not isinstance(window, MainWindowProtocol)

    def test_missing_attribute(self):
        """Test that a class missing required attributes does not satisfy the protocol."""

        class WindowWithoutWorker:
            """Mock MainWindow missing worker attribute."""

            def __init__(self):
                self.command_requested = object()

            def _on_configure_grouping_requested(self):
                pass

            def _on_clear_grouping_requested(self):
                pass

        window = WindowWithoutWorker()
        assert not isinstance(window, MainWindowProtocol)


class TestTimelineDataProvider:
    """Test the TimelineDataProvider interface."""

    def test_valid_implementation(self):
        """Test that a class implementing required methods satisfies the protocol."""

        class ValidDataProvider:
            """Mock data provider that implements the protocol."""

            def get_group_metadata(self, tag_order, date_range=None):
                return [
                    {
                        "tag_name": "test",
                        "color": "#FF0000",
                        "count": 5,
                        "earliest_date": 0.0,
                        "latest_date": 100.0,
                    }
                ]

            def get_events_for_group(self, tag_name, date_range=None):
                return []

        provider = ValidDataProvider()
        assert isinstance(provider, TimelineDataProvider)

    def test_missing_get_group_metadata(self):
        """Test that a provider missing get_group_metadata does not satisfy the protocol."""

        class IncompleteProvider:
            """Mock provider missing get_group_metadata."""

            def get_events_for_group(self, tag_name, date_range=None):
                return []

        provider = IncompleteProvider()
        assert not isinstance(provider, TimelineDataProvider)

    def test_missing_get_events_for_group(self):
        """Test that a provider missing get_events_for_group does not satisfy the protocol."""

        class IncompleteProvider:
            """Mock provider missing get_events_for_group."""

            def get_group_metadata(self, tag_order, date_range=None):
                return []

        provider = IncompleteProvider()
        assert not isinstance(provider, TimelineDataProvider)

    def test_correct_signatures(self):
        """Test that methods can be called with expected signatures."""

        class ValidDataProvider:
            """Mock data provider with correct signatures."""

            def get_group_metadata(self, tag_order, date_range=None):
                assert isinstance(tag_order, list)
                assert date_range is None or isinstance(date_range, tuple)
                return []

            def get_events_for_group(self, tag_name, date_range=None):
                assert isinstance(tag_name, str)
                assert date_range is None or isinstance(date_range, tuple)
                return []

        provider = ValidDataProvider()

        # Test calling methods with expected arguments
        result1 = provider.get_group_metadata(["tag1", "tag2"])
        assert result1 == []

        result2 = provider.get_group_metadata(["tag1"], (0.0, 100.0))
        assert result2 == []

        result3 = provider.get_events_for_group("tag1")
        assert result3 == []

        result4 = provider.get_events_for_group("tag1", (0.0, 100.0))
        assert result4 == []
