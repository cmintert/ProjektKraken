"""
Unit tests for Timeline Grouping Commands - Milestone 2.

This module tests command classes for managing timeline grouping configurations,
including undo/redo support.
"""

import pytest

from src.commands.timeline_grouping_commands import (
    ClearTimelineGroupingCommand,
    SetTimelineGroupingCommand,
    UpdateTagColorCommand,
)


@pytest.mark.unit
class TestTimelineGroupingCommands:
    """Tests for timeline grouping command classes."""

    def test_set_timeline_grouping_command_stores_configuration(self, db_service):
        """
        Test that SetTimelineGroupingCommand stores grouping configuration.
        """
        tag_order = ["battle", "political", "important"]

        cmd = SetTimelineGroupingCommand(tag_order=tag_order)
        result = cmd.execute(db_service)

        assert result.success
        assert result.command_name == "SetTimelineGroupingCommand"

        # Verify configuration was stored
        config = db_service.get_timeline_grouping_config()
        assert config["tag_order"] == tag_order
        assert config["mode"] == "DUPLICATE"  # Default mode

    def test_set_timeline_grouping_command_with_first_match_mode(self, db_service):
        """
        Test that SetTimelineGroupingCommand can store FIRST_MATCH mode.
        """
        tag_order = ["tag1", "tag2"]

        cmd = SetTimelineGroupingCommand(tag_order=tag_order, mode="FIRST_MATCH")
        result = cmd.execute(db_service)

        assert result.success

        config = db_service.get_timeline_grouping_config()
        assert config["mode"] == "FIRST_MATCH"

    def test_set_timeline_grouping_command_undo_restores_previous(self, db_service):
        """
        Test that undoing SetTimelineGroupingCommand restores previous configuration.
        """
        # Set initial configuration
        initial_order = ["old1", "old2"]
        db_service.set_timeline_grouping_config(tag_order=initial_order)

        # Execute new command
        new_order = ["new1", "new2", "new3"]
        cmd = SetTimelineGroupingCommand(tag_order=new_order)
        cmd.execute(db_service)

        # Verify new configuration
        config = db_service.get_timeline_grouping_config()
        assert config["tag_order"] == new_order

        # Undo
        cmd.undo(db_service)

        # Verify previous configuration restored
        config = db_service.get_timeline_grouping_config()
        assert config["tag_order"] == initial_order

    def test_set_timeline_grouping_command_undo_when_no_previous_config(
        self, db_service
    ):
        """
        Test that undoing SetTimelineGroupingCommand works when no previous config exists.
        """
        # Execute command with no previous config
        tag_order = ["tag1", "tag2"]
        cmd = SetTimelineGroupingCommand(tag_order=tag_order)
        cmd.execute(db_service)

        # Undo
        cmd.undo(db_service)

        # Configuration should be cleared
        config = db_service.get_timeline_grouping_config()
        assert config is None or config["tag_order"] == []

    def test_clear_timeline_grouping_command_removes_configuration(self, db_service):
        """
        Test that ClearTimelineGroupingCommand removes grouping configuration.
        """
        # Set initial configuration
        db_service.set_timeline_grouping_config(tag_order=["tag1", "tag2"])

        # Execute clear command
        cmd = ClearTimelineGroupingCommand()
        result = cmd.execute(db_service)

        assert result.success
        assert result.command_name == "ClearTimelineGroupingCommand"

        # Verify configuration was cleared
        config = db_service.get_timeline_grouping_config()
        assert config is None or config["tag_order"] == []

    def test_clear_timeline_grouping_command_undo_restores_config(self, db_service):
        """
        Test that undoing ClearTimelineGroupingCommand restores configuration.
        """
        # Set initial configuration
        initial_order = ["tag1", "tag2", "tag3"]
        db_service.set_timeline_grouping_config(
            tag_order=initial_order, mode="FIRST_MATCH"
        )

        # Execute clear command
        cmd = ClearTimelineGroupingCommand()
        cmd.execute(db_service)

        # Verify cleared
        config = db_service.get_timeline_grouping_config()
        assert config is None or config["tag_order"] == []

        # Undo
        cmd.undo(db_service)

        # Verify restored
        config = db_service.get_timeline_grouping_config()
        assert config["tag_order"] == initial_order
        assert config["mode"] == "FIRST_MATCH"

    def test_update_tag_color_command_sets_color(self, db_service):
        """
        Test that UpdateTagColorCommand sets a tag color.
        """
        # Create tag
        db_service.create_tag("test-tag")

        # Execute command
        cmd = UpdateTagColorCommand(tag_name="test-tag", color="#FF0000")
        result = cmd.execute(db_service)

        assert result.success
        assert result.command_name == "UpdateTagColorCommand"

        # Verify color was set
        color = db_service.get_tag_color("test-tag")
        assert color == "#FF0000"

    def test_update_tag_color_command_undo_restores_previous_color(self, db_service):
        """
        Test that undoing UpdateTagColorCommand restores previous color.
        """
        # Create tag with initial color
        db_service.create_tag("test-tag")
        db_service.set_tag_color("test-tag", "#FF0000")

        # Execute command to change color
        cmd = UpdateTagColorCommand(tag_name="test-tag", color="#00FF00")
        cmd.execute(db_service)

        # Verify new color
        assert db_service.get_tag_color("test-tag") == "#00FF00"

        # Undo
        cmd.undo(db_service)

        # Verify previous color restored
        assert db_service.get_tag_color("test-tag") == "#FF0000"

    def test_update_tag_color_command_undo_when_no_previous_color(self, db_service):
        """
        Test that undoing UpdateTagColorCommand works when tag had no color.
        """
        # Create tag without color
        db_service.create_tag("test-tag")

        # Execute command
        cmd = UpdateTagColorCommand(tag_name="test-tag", color="#FF0000")
        cmd.execute(db_service)

        # Undo
        cmd.undo(db_service)

        # Color should be cleared or back to generated
        tag = db_service.get_tag_by_name("test-tag")
        assert tag["color"] is None or tag["color"] != "#FF0000"

    def test_update_tag_color_command_validates_color_format(self, db_service):
        """
        Test that UpdateTagColorCommand validates hex color format.
        """
        db_service.create_tag("test-tag")

        # Invalid color should fail
        cmd = UpdateTagColorCommand(tag_name="test-tag", color="not-a-color")
        result = cmd.execute(db_service)

        assert not result.success
        assert "invalid" in result.message.lower() or "format" in result.message.lower()

    def test_set_timeline_grouping_command_validates_mode(self, db_service):
        """
        Test that SetTimelineGroupingCommand validates mode parameter.
        """
        cmd = SetTimelineGroupingCommand(tag_order=["tag1"], mode="INVALID_MODE")
        result = cmd.execute(db_service)

        assert not result.success
        assert "mode" in result.message.lower() or "invalid" in result.message.lower()

    def test_update_tag_color_command_creates_tag_if_not_exists(self, db_service):
        """
        Test that UpdateTagColorCommand creates tag if it doesn't exist.
        """
        # Execute command for nonexistent tag
        cmd = UpdateTagColorCommand(tag_name="new-tag", color="#FF0000")
        result = cmd.execute(db_service)

        assert result.success

        # Verify tag was created with color
        tag = db_service.get_tag_by_name("new-tag")
        assert tag is not None
        assert tag["color"] == "#FF0000"

    def test_command_execution_state_tracking(self, db_service):
        """
        Test that commands track their execution state correctly.
        """
        cmd = SetTimelineGroupingCommand(tag_order=["tag1"])

        # Before execution
        assert not cmd.is_executed

        # After execution
        cmd.execute(db_service)
        assert cmd.is_executed

        # After undo
        cmd.undo(db_service)
        assert not cmd.is_executed

    def test_multiple_undo_redo_cycles(self, db_service):
        """
        Test that commands can be undone and redone multiple times.
        """
        tag_order = ["tag1", "tag2"]
        cmd = SetTimelineGroupingCommand(tag_order=tag_order)

        # Execute
        cmd.execute(db_service)
        config = db_service.get_timeline_grouping_config()
        assert config["tag_order"] == tag_order

        # Undo
        cmd.undo(db_service)
        config = db_service.get_timeline_grouping_config()
        assert config is None or config["tag_order"] == []

        # Redo (re-execute)
        cmd.execute(db_service)
        config = db_service.get_timeline_grouping_config()
        assert config["tag_order"] == tag_order

        # Undo again
        cmd.undo(db_service)
        config = db_service.get_timeline_grouping_config()
        assert config is None or config["tag_order"] == []
