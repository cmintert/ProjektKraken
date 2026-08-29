"""Guard the public surface and growth budget of transitional choke points."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TypedDict

import pytest

PROJECT_ROOT = Path(__file__).parents[2]


class ChokePointBaseline(TypedDict):
    """Recorded public API and approximate size for one choke point."""

    line_count: int
    public_api: frozenset[str]


# Deleting public API is permitted so capability extraction can shrink these
# facades. Additions require an explicit baseline update and architecture review.
CHOKE_POINT_BASELINES: dict[str, ChokePointBaseline] = {
    "src/app/map_handler.py": {
        "line_count": 2736,
        "public_api": frozenset(
            """
            class:MapHandler
            method:MapHandler.load_maps method:MapHandler.on_map_selected
            method:MapHandler.reload_markers
            method:MapHandler.reload_markers_for_current_map
            method:MapHandler.create_map method:MapHandler.delete_map
            method:MapHandler.create_marker method:MapHandler.on_marker_dropped
            method:MapHandler.on_feature_drawn
            method:MapHandler.on_feature_style_changed
            method:MapHandler.on_feature_geometry_changed
            method:MapHandler.delete_marker method:MapHandler.on_marker_clicked
            method:MapHandler.on_marker_color_changed
            method:MapHandler.on_marker_visual_style_changed
            method:MapHandler.on_marker_appearance_changed
            method:MapHandler.on_marker_position_changed
            method:MapHandler.on_maps_ready method:MapHandler.on_markers_ready
            method:MapHandler.on_trajectories_ready
            method:MapHandler.on_map_scale_changed
            method:MapHandler.on_map_settings_changed
            method:MapHandler.on_set_master_map_requested
            method:MapHandler.on_register_detail_map_requested
            method:MapHandler.on_detail_map_clicked
            method:MapHandler.on_footprint_edit_confirmed
            method:MapHandler.on_layer_tree_changed
            method:MapHandler.on_layer_opacity_changed
            method:MapHandler.on_layer_renamed
            method:MapHandler.on_layer_feature_deleted
            method:MapHandler.on_layer_properties_changed
            method:MapHandler.create_raster_layer
            method:MapHandler.delete_raster_layer
            method:MapHandler.load_raster_layers
            method:MapHandler.on_raster_stroke_completed
            method:MapHandler.on_command_effects
            method:MapHandler.has_pending_raster_strokes
            method:MapHandler.on_raster_palette_edit
            method:MapHandler.on_raster_query_requested
            method:MapHandler.on_raster_query_cleared
            method:MapHandler.on_raster_value_probed
            method:MapHandler.on_raster_stats_requested
            method:MapHandler.on_raster_gradient_sub_mode_changed
            method:MapHandler.on_raster_notes_requested
            method:MapHandler.on_playhead_changed
            method:MapHandler.on_raster_snapshot_requested
            method:MapHandler.on_raster_snapshot_selected
            method:MapHandler.on_raster_base_edit_requested
            method:MapHandler.on_raster_snapshot_edit_requested
            method:MapHandler.on_raster_snapshot_delete_requested
            """.split()
        ),
    },
    "src/services/worker.py": {
        "line_count": 1990,
        "public_api": frozenset(
            """
            class:DatabaseWorker
            method:DatabaseWorker.initialize_db method:DatabaseWorker.cleanup
            method:DatabaseWorker.initialize_history
            method:DatabaseWorker.clear_command_history
            method:DatabaseWorker.load_timeline_grouping_config
            method:DatabaseWorker.save_world_theme
            method:DatabaseWorker.load_embedding_stats
            method:DatabaseWorker.load_events method:DatabaseWorker.load_entities
            method:DatabaseWorker.load_maps method:DatabaseWorker.load_markers
            method:DatabaseWorker.load_trajectories
            method:DatabaseWorker.load_feature_geometry_states
            method:DatabaseWorker.load_event_details
            method:DatabaseWorker.load_event_authoring_context
            method:DatabaseWorker.load_entity_details
            method:DatabaseWorker.load_entity_authoring_context
            method:DatabaseWorker.load_attachments
            method:DatabaseWorker.load_longform_sequence
            method:DatabaseWorker.load_calendar_config
            method:DatabaseWorker.run_command method:DatabaseWorker.run_undo
            method:DatabaseWorker.run_redo method:DatabaseWorker.load_current_time
            method:DatabaseWorker.save_current_time
            method:DatabaseWorker.load_ai_generation_preferences
            method:DatabaseWorker.save_ai_generation_preferences
            method:DatabaseWorker.save_graph_lexicon
            method:DatabaseWorker.load_grouping_dialog_data
            method:DatabaseWorker.index_object
            method:DatabaseWorker.rebuild_search_index
            method:DatabaseWorker.apply_filter
            method:DatabaseWorker.resolve_entity_state
            method:DatabaseWorker.load_graph_data
            method:DatabaseWorker.query_semantic_suggestions
            method:DatabaseWorker.load_completer_data
            method:DatabaseWorker.run_import
            method:DatabaseWorker.run_markdown_import
            method:DatabaseWorker.run_markdown_batch_import
            method:DatabaseWorker.prepare_single_obsidian_export
            method:DatabaseWorker.run_single_obsidian_export
            method:DatabaseWorker.run_obsidian_vault_export
            method:DatabaseWorker.generate_summary
            method:DatabaseWorker.refresh_ai_settings
            method:DatabaseWorker.validate_world
            method:DatabaseWorker.analyze_temporal
            method:DatabaseWorker.prepare_intelligence_analysis
            """.split()
        ),
    },
    "src/app/connection_manager.py": {
        "line_count": 1237,
        "public_api": frozenset(
            """
            class:ConnectionManager method:ConnectionManager.connect_all
            method:ConnectionManager.connect_data_handler
            method:ConnectionManager.connect_unified_list
            method:ConnectionManager.connect_editors
            method:ConnectionManager.connect_timeline
            method:ConnectionManager.connect_longform_editor
            method:ConnectionManager.connect_map_widget
            method:ConnectionManager.connect_ai_search_panel
            method:ConnectionManager.connect_graph_widget
            method:ConnectionManager.connect_analysis_panel
            """.split()
        ),
    },
    "src/app/main_window.py": {
        "line_count": 1242,
        "public_api": frozenset(
            """
            class:GlobalShortcutFilter method:GlobalShortcutFilter.eventFilter
            class:MainWindow method:MainWindow.load_longform_sequence
            method:MainWindow.check_unsaved_changes
            method:MainWindow.update_status_message
            method:MainWindow.clear_status_message
            method:MainWindow.show_error_message method:MainWindow.on_db_initialized
            method:MainWindow.toggle_auto_relation_setting
            method:MainWindow.toggle_longform_auto_refresh
            method:MainWindow.on_grouping_config_loaded
            method:MainWindow.closeEvent method:MainWindow.get_group_metadata
            method:MainWindow.get_events_for_group method:MainWindow.load_maps
            method:MainWindow.on_grouping_dialog_data_loaded
            method:MainWindow.show_filter_dialog method:MainWindow.clear_filter
            """.split()
        ),
    },
    "src/services/db_service.py": {
        "line_count": 2029,
        "public_api": frozenset(
            """
            class:DatabaseService method:DatabaseService.connect
            method:DatabaseService.close method:DatabaseService.is_connected
            method:DatabaseService.get_connection method:DatabaseService.map_repo
            method:DatabaseService.trajectory_repo
            method:DatabaseService.feature_geometry_repo
            method:DatabaseService.get_attachment_repo
            method:DatabaseService.transaction
            method:DatabaseService.ensure_fresh_view
            method:DatabaseService.insert_event method:DatabaseService.get_event
            method:DatabaseService.get_all_events method:DatabaseService.get_events
            method:DatabaseService.delete_event
            method:DatabaseService.insert_entity method:DatabaseService.get_entity
            method:DatabaseService.get_all_entities
            method:DatabaseService.get_entities method:DatabaseService.delete_entity
            method:DatabaseService.insert_relation
            method:DatabaseService.reconcile_mentions
            method:DatabaseService.restore_mentions
            method:DatabaseService.get_all_relations
            method:DatabaseService.get_relations_for_item
            method:DatabaseService.delete_relations_for_item
            method:DatabaseService.get_relations
            method:DatabaseService.get_incoming_relations
            method:DatabaseService.get_relation
            method:DatabaseService.delete_relation
            method:DatabaseService.update_relation method:DatabaseService.get_name
            method:DatabaseService.insert_events_bulk
            method:DatabaseService.insert_entities_bulk
            method:DatabaseService.insert_calendar_config
            method:DatabaseService.get_calendar_config
            method:DatabaseService.get_all_calendar_configs
            method:DatabaseService.get_active_calendar_config
            method:DatabaseService.delete_calendar_config
            method:DatabaseService.set_active_calendar_config
            method:DatabaseService.get_current_time
            method:DatabaseService.set_current_time
            method:DatabaseService.get_world_theme
            method:DatabaseService.set_world_theme
            method:DatabaseService.get_ai_generation_preferences
            method:DatabaseService.set_ai_generation_preferences
            method:DatabaseService.insert_map method:DatabaseService.get_map
            method:DatabaseService.get_all_maps method:DatabaseService.delete_map
            method:DatabaseService.insert_marker method:DatabaseService.get_marker
            method:DatabaseService.get_markers_for_map
            method:DatabaseService.get_markers_for_object
            method:DatabaseService.get_marker_by_composite
            method:DatabaseService.delete_marker
            method:DatabaseService.get_all_tags
            method:DatabaseService.get_tags_with_events
            method:DatabaseService.get_active_tags
            method:DatabaseService.get_tag_by_name
            method:DatabaseService.create_tag method:DatabaseService.delete_tag
            method:DatabaseService.assign_tag_to_event
            method:DatabaseService.assign_tag_to_entity
            method:DatabaseService.remove_tag_from_event
            method:DatabaseService.remove_tag_from_entity
            method:DatabaseService.get_tags_for_event
            method:DatabaseService.get_tags_for_entity
            method:DatabaseService.get_entity_tag_memberships
            method:DatabaseService.get_events_by_tag
            method:DatabaseService.get_entities_by_tag
            method:DatabaseService.get_events_grouped_by_tags
            method:DatabaseService.get_group_counts
            method:DatabaseService.get_group_metadata
            method:DatabaseService.get_events_for_group
            method:DatabaseService.set_tag_color
            method:DatabaseService.get_tag_color
            method:DatabaseService.filter_ids_by_tags
            method:DatabaseService.get_objects_by_ids
            method:DatabaseService.set_timeline_grouping_config
            method:DatabaseService.get_timeline_grouping_config
            method:DatabaseService.clear_timeline_grouping_config
            method:DatabaseService.get_graph_lexicon
            method:DatabaseService.set_graph_lexicon
            method:DatabaseService.insert_trajectory
            method:DatabaseService.get_trajectories_by_map
            method:DatabaseService.get_trajectory_snapshots_by_map
            method:DatabaseService.get_trajectories_by_marker
            method:DatabaseService.get_marker_trajectory_snapshot
            method:DatabaseService.set_marker_trajectory
            method:DatabaseService.restore_marker_trajectory_snapshot
            method:DatabaseService.register_backup_service
            method:DatabaseService.get_db_file_path method:DatabaseService.vacuum
            method:DatabaseService.get_embedding_stats
            """.split()
        ),
    },
}


def _public_api(path: Path) -> set[str]:
    """Return public top-level definitions and direct class methods from *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    definitions: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            definitions.add(f"class:{node.name}")
            definitions.update(
                f"method:{node.name}.{method.name}"
                for method in node.body
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not method.name.startswith("_")
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not (
            node.name.startswith("_")
        ):
            definitions.add(f"function:{node.name}")

    return definitions


def _unexpected_public_api(
    actual: set[str], baseline: ChokePointBaseline
) -> set[str]:
    """Return additions only, so a facade can shrink during extraction."""
    return actual - baseline["public_api"]


@pytest.mark.parametrize("relative_path, baseline", CHOKE_POINT_BASELINES.items())
def test_choke_point_public_api_does_not_grow(
    relative_path: str, baseline: ChokePointBaseline
) -> None:
    """Require an intentional baseline update before expanding a choke point."""
    actual = _public_api(PROJECT_ROOT / relative_path)
    additions = _unexpected_public_api(actual, baseline)

    assert not additions, (
        f"{relative_path} gained public API: {sorted(additions)}. "
        "Extract the capability instead, or deliberately update this baseline "
        "with an architecture review."
    )


def test_choke_point_public_api_allows_removal() -> None:
    """Keep capability extraction from being blocked by the addition-only gate."""
    baseline = CHOKE_POINT_BASELINES["src/app/map_handler.py"]
    after_extraction = set(baseline["public_api"])
    after_extraction.remove("method:MapHandler.load_maps")

    assert not _unexpected_public_api(after_extraction, baseline)


@pytest.mark.parametrize("relative_path, baseline", CHOKE_POINT_BASELINES.items())
def test_choke_point_size_stays_within_growth_budget(
    relative_path: str, baseline: ChokePointBaseline
) -> None:
    """Allow reductions but flag growth beyond the five-percent warning budget."""
    current_lines = len(
        (PROJECT_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
    )
    baseline_lines = baseline["line_count"]
    maximum_lines = int(baseline_lines * 1.05)

    assert current_lines <= maximum_lines, (
        f"{relative_path} grew from {baseline_lines} to {current_lines} lines "
        f"(warning budget: {maximum_lines}). Extract or move the capability, or "
        "deliberately update this baseline after architecture review."
    )
