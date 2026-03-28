"""Regression tests for MapWidget mixin decomposition.

Verifies that all mixin methods are correctly resolved on MapWidget
via Python's MRO, and that the mixin architecture hasn't broken
any fundamental method availability.
"""

import pytest

from src.gui.mixins.map_calibration_mixin import MapCalibrationMixin
from src.gui.mixins.map_dialog_mixin import MapDialogMixin
from src.gui.mixins.map_drawing_mixin import MapDrawingMixin
from src.gui.mixins.map_layer_mixin import MapLayerMixin
from src.gui.mixins.map_trajectory_mixin import MapTrajectoryMixin
from src.gui.widgets.map_widget import MapWidget


class TestMixinMRO:
    """Verify MapWidget inherits from all 5 mixins in correct order."""

    def test_inherits_map_layer_mixin(self):
        assert issubclass(MapWidget, MapLayerMixin)

    def test_inherits_map_trajectory_mixin(self):
        assert issubclass(MapWidget, MapTrajectoryMixin)

    def test_inherits_map_drawing_mixin(self):
        assert issubclass(MapWidget, MapDrawingMixin)

    def test_inherits_map_calibration_mixin(self):
        assert issubclass(MapWidget, MapCalibrationMixin)

    def test_inherits_map_dialog_mixin(self):
        assert issubclass(MapWidget, MapDialogMixin)

    def test_mro_order(self):
        """Mixins must come before QWidget in MRO."""
        mro_names = [c.__name__ for c in MapWidget.__mro__]
        qwidget_idx = mro_names.index("QWidget")
        for mixin_name in [
            "MapLayerMixin",
            "MapTrajectoryMixin",
            "MapDrawingMixin",
            "MapCalibrationMixin",
            "MapDialogMixin",
        ]:
            mixin_idx = mro_names.index(mixin_name)
            assert mixin_idx < qwidget_idx, (
                f"{mixin_name} must come before QWidget in MRO"
            )


class TestLayerMixinMethods:
    """Verify all MapLayerMixin methods are accessible on MapWidget."""

    EXPECTED_METHODS = [
        "rebuild_layer_model",
        "_ensure_layer_model",
        "_default_group",
        "_feature_type_to_layer_type",
        "_register_layer_node",
        "_unregister_layer_node",
        "_on_marker_clicked_select_layer",
        "_on_layer_panel_selected",
        "_on_create_group",
        "_on_create_layer",
        "_on_delete_layer",
        "_collect_leaf_ids",
        "_remove_children_graphics",
        "_on_layer_renamed",
        "_on_layer_opacity_changed",
        "get_layer_model",
    ]

    @pytest.mark.parametrize("method_name", EXPECTED_METHODS)
    def test_method_exists(self, method_name):
        assert hasattr(MapWidget, method_name), f"Missing: {method_name}"
        assert callable(getattr(MapWidget, method_name))


class TestTrajectoryMixinMethods:
    """Verify all MapTrajectoryMixin methods are accessible on MapWidget."""

    EXPECTED_METHODS = [
        "set_trajectories",
        "_update_marker_indicators",
        "_on_add_keyframe",
        "_iter_trajectory_positions",
        "_update_trajectory_positions",
        "on_time_changed",
        "on_current_time_changed",
        "_update_time_display",
        "_on_marker_clicked_internal",
        "_update_trajectory_visualization",
        "_emit_keyframe_upsert",
        "_show_onboarding_dialog",
        "_on_keyframe_moved",
        "_enter_clock_mode",
        "_commit_clock_mode",
        "_cancel_clock_mode",
        "_clear_clock_mode_visuals",
        "_handle_clock_mode_time_change",
        "_on_clock_mode_requested",
        "_on_keyframe_delete_requested",
    ]

    @pytest.mark.parametrize("method_name", EXPECTED_METHODS)
    def test_method_exists(self, method_name):
        assert hasattr(MapWidget, method_name), f"Missing: {method_name}"
        assert callable(getattr(MapWidget, method_name))


class TestDrawingMixinMethods:
    """Verify all MapDrawingMixin methods are accessible on MapWidget."""

    EXPECTED_METHODS = [
        "_on_draw_path_clicked",
        "_on_draw_region_clicked",
        "_on_drawing_finished",
        "_on_drawing_cancelled",
    ]

    @pytest.mark.parametrize("method_name", EXPECTED_METHODS)
    def test_method_exists(self, method_name):
        assert hasattr(MapWidget, method_name), f"Missing: {method_name}"
        assert callable(getattr(MapWidget, method_name))


class TestCalibrationMixinMethods:
    """Verify all MapCalibrationMixin methods are accessible on MapWidget."""

    EXPECTED_METHODS = [
        "_configure_map_width",
        "_handle_calibration_request",
        "_on_calibration_measurement_finished",
    ]

    @pytest.mark.parametrize("method_name", EXPECTED_METHODS)
    def test_method_exists(self, method_name):
        assert hasattr(MapWidget, method_name), f"Missing: {method_name}"
        assert callable(getattr(MapWidget, method_name))


class TestDialogMixinMethods:
    """Verify all MapDialogMixin methods are accessible on MapWidget."""

    EXPECTED_METHODS = [
        "set_cached_items",
        "_select_or_create_object",
        "_create_new_entity_inline",
        "_create_new_event_inline",
        "_on_create_map_clicked",
        "_on_delete_map_clicked",
        "_on_create_marker_requested",
        "_on_delete_marker_requested",
    ]

    @pytest.mark.parametrize("method_name", EXPECTED_METHODS)
    def test_method_exists(self, method_name):
        assert hasattr(MapWidget, method_name), f"Missing: {method_name}"
        assert callable(getattr(MapWidget, method_name))

    def test_sentinel_values(self):
        """Sentinel class attributes must be accessible."""
        assert hasattr(MapWidget, "_NEW_ENTITY_SENTINEL")
        assert hasattr(MapWidget, "_NEW_EVENT_SENTINEL")


class TestMapWidgetOwnMethods:
    """Verify that MapWidget retains its own orchestration methods."""

    OWN_METHODS = [
        "__init__",
        "minimumSizeHint",
        "sizeHint",
        "_on_selection_changed",
        "_on_snap_toggled",
        "_on_finish_sketch",
        "_on_geometry_changed",
        "set_maps",
        "select_map",
        "_on_map_selected",
        "get_selected_map_id",
        "_on_marker_moved",
        "_on_mouse_coordinates_changed",
        "load_map",
        "add_marker",
        "update_marker_position",
        "remove_marker",
        "clear_markers",
        "_apply_mode_indicator_style",
        "_update_mode_indicator",
        "set_calendar_converter",
        "keyPressEvent",
        "_update_overlay_position",
        "_update_finish_sketch_position",
        "resizeEvent",
    ]

    @pytest.mark.parametrize("method_name", OWN_METHODS)
    def test_method_exists(self, method_name):
        assert hasattr(MapWidget, method_name), f"Missing: {method_name}"


class TestFeatureTypeMapping:
    """Verify _feature_type_to_layer_type works as a static method."""

    def test_path_mapping(self):
        assert MapWidget._feature_type_to_layer_type("path") == "path"

    def test_region_mapping(self):
        assert MapWidget._feature_type_to_layer_type("region") == "region"

    def test_point_mapping(self):
        assert MapWidget._feature_type_to_layer_type("point") == "marker"

    def test_unknown_defaults_to_marker(self):
        assert MapWidget._feature_type_to_layer_type("unknown") == "marker"
