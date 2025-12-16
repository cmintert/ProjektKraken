"""Unit tests for map widget."""

import pytest
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication
from src.gui.widgets.map_widget import (
    MapWidget,
    MapGraphicsView,
    MarkerItem,
    CalibrationDialog,
)
from src.core.maps import GameMap, MapMarker


@pytest.fixture
def map_widget(qapp):
    """Create a MapWidget instance for testing."""
    widget = MapWidget()
    return widget


@pytest.fixture
def test_pixmap():
    """Create a simple test pixmap."""
    pixmap = QPixmap(1000, 800)
    pixmap.fill(QColor("#808080"))
    return pixmap


@pytest.fixture
def temp_map_image():
    """Create a temporary map image file."""
    temp_file = tempfile.NamedTemporaryFile(
        mode="wb", suffix=".png", delete=False
    )
    # Create a simple pixmap
    pixmap = QPixmap(1000, 800)
    pixmap.fill(QColor("#404040"))
    pixmap.save(temp_file.name, "PNG")
    temp_file.close()
    
    yield temp_file.name
    
    # Cleanup
    Path(temp_file.name).unlink(missing_ok=True)


class TestMapWidget:
    """Tests for MapWidget."""

    def test_widget_creation(self, map_widget):
        """Test that widget is created successfully."""
        assert map_widget is not None
        assert map_widget.current_map is None
        assert len(map_widget.markers) == 0

    def test_load_map(self, map_widget, temp_map_image):
        """Test loading a map into the widget."""
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=800,
        )
        
        map_widget.load_map(game_map, temp_map_image)
        
        assert map_widget.current_map == game_map
        assert hasattr(map_widget.scene, 'map_pixmap_item')
        
    def test_add_marker(self, map_widget, temp_map_image):
        """Test adding a marker to the map."""
        # Load map first
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=800,
        )
        map_widget.load_map(game_map, temp_map_image)
        
        # Add marker
        marker = MapMarker(
            map_id=game_map.id,
            object_id="entity-123",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        
        map_widget.add_marker(marker, "Test Location", QColor("#FF0000"))
        
        assert marker.id in map_widget.markers
        assert len(map_widget.markers) == 1
        
    def test_remove_marker(self, map_widget, temp_map_image):
        """Test removing a marker from the map."""
        # Load map and add marker
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=800,
        )
        map_widget.load_map(game_map, temp_map_image)
        
        marker = MapMarker(
            map_id=game_map.id,
            object_id="entity-123",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        map_widget.add_marker(marker, "Test Location")
        
        # Remove marker
        map_widget.remove_marker(marker.id)
        
        assert marker.id not in map_widget.markers
        assert len(map_widget.markers) == 0
        
    def test_clear_markers(self, map_widget, temp_map_image):
        """Test clearing all markers."""
        # Load map
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=800,
        )
        map_widget.load_map(game_map, temp_map_image)
        
        # Add multiple markers
        for i in range(5):
            marker = MapMarker(
                map_id=game_map.id,
                object_id=f"entity-{i}",
                object_type="entity",
                x=0.2 * i,
                y=0.2 * i,
            )
            map_widget.add_marker(marker, f"Location {i}")
            
        assert len(map_widget.markers) == 5
        
        # Clear all
        map_widget.clear_markers()
        
        assert len(map_widget.markers) == 0
        
    def test_update_marker_position(self, map_widget, temp_map_image):
        """Test updating a marker's position."""
        # Load map and add marker
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=800,
        )
        map_widget.load_map(game_map, temp_map_image)
        
        marker = MapMarker(
            map_id=game_map.id,
            object_id="entity-123",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        map_widget.add_marker(marker, "Test Location")
        
        # Update position
        map_widget.update_marker_position(marker.id, 0.7, 0.3)
        
        marker_item = map_widget.markers[marker.id]
        assert marker_item.marker.x == 0.7
        assert marker_item.marker.y == 0.3
        
    def test_set_available_maps(self, map_widget):
        """Test setting available maps in dropdown."""
        map_names = ["World Map", "Region Map", "City Map"]
        map_widget.set_available_maps(map_names)
        
        assert map_widget.map_combo.count() == 3
        assert map_widget.map_combo.itemText(0) == "World Map"
        assert map_widget.map_combo.itemText(1) == "Region Map"
        assert map_widget.map_combo.itemText(2) == "City Map"


class TestMapGraphicsView:
    """Tests for MapGraphicsView."""

    def test_view_creation(self, qapp):
        """Test that view is created successfully."""
        view = MapGraphicsView()
        assert view is not None
        assert view._mode == "pan"
        assert view._zoom_factor == 1.0
        
    def test_set_mode(self, qapp):
        """Test setting interaction mode."""
        view = MapGraphicsView()
        
        # Test pan mode
        view.set_mode("pan")
        assert view._mode == "pan"
        
        # Test add marker mode
        view.set_mode("add_marker")
        assert view._mode == "add_marker"
        
    def test_reset_zoom(self, qapp):
        """Test resetting zoom."""
        view = MapGraphicsView()
        
        # Zoom in
        view.scale(2.0, 2.0)
        view._zoom_factor = 2.0
        
        # Reset
        view.reset_zoom()
        
        assert view._zoom_factor == 1.0


class TestMarkerItem:
    """Tests for MarkerItem."""

    def test_marker_item_creation(self, qapp):
        """Test creating a marker item."""
        marker = MapMarker(
            map_id="map-123",
            object_id="entity-456",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        
        item = MarkerItem(marker, "Test City", QColor("#FF0000"))
        
        assert item.marker == marker
        assert item.object_name == "Test City"
        assert item.label.toPlainText() == "Test City"


class TestCalibrationDialog:
    """Tests for CalibrationDialog."""

    def test_dialog_creation(self, qapp):
        """Test creating calibration dialog."""
        dialog = CalibrationDialog()
        assert dialog is not None
        
    def test_dialog_with_existing_map(self, qapp):
        """Test dialog with existing map data."""
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=500.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=800,
        )
        
        dialog = CalibrationDialog(game_map)
        
        assert dialog.real_width_spin.value() == 500.0
        assert dialog.unit_combo.currentText() == "km"
        
    def test_get_calibration(self, qapp):
        """Test getting calibration values."""
        dialog = CalibrationDialog()
        dialog.real_width_spin.setValue(250.0)
        dialog.unit_combo.setCurrentText("mi")
        
        real_width, unit = dialog.get_calibration()
        
        assert real_width == 250.0
        assert unit == "mi"
