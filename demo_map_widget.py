"""
Example demonstrating the MapWidget usage.

This example shows how to:
- Create and display a MapWidget
- Load a map
- Add markers for entities and events
- Handle marker placement
- Calibrate the map scale
"""

import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt

from src.gui.widgets.map_widget import MapWidget
from src.core.maps import GameMap, MapMarker
from src.core.entities import Entity
from src.core.events import Event


def create_sample_map_image():
    """Create a sample map image for demonstration."""
    temp_file = tempfile.NamedTemporaryFile(
        mode="wb", suffix=".png", delete=False
    )
    
    # Create a simple colored pixmap as a placeholder map
    pixmap = QPixmap(1600, 1200)
    pixmap.fill(QColor("#2C5F2D"))  # Forest green
    pixmap.save(temp_file.name, "PNG")
    temp_file.close()
    
    return temp_file.name


class MapDemoWindow(QMainWindow):
    """Demo window showing MapWidget functionality."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Map Widget Demo")
        self.resize(1200, 800)
        
        # Create map widget
        self.map_widget = MapWidget()
        self.setCentralWidget(self.map_widget)
        
        # Connect signals
        self.map_widget.marker_placement_requested.connect(
            self._on_marker_placement
        )
        self.map_widget.calibration_changed.connect(
            self._on_calibration_changed
        )
        
        # Setup demo data
        self._setup_demo()
        
    def _setup_demo(self):
        """Setup demonstration data."""
        # Create a sample map
        self.demo_map_path = create_sample_map_image()
        
        self.game_map = GameMap(
            name="Fantasy Realm",
            image_filename="fantasy_realm.png",
            real_width=1000.0,
            distance_unit="km",
            reference_width=1600,
            reference_height=1200,
        )
        
        # Load the map
        self.map_widget.load_map(self.game_map, self.demo_map_path)
        
        # Create some sample entities
        self.capital = Entity(name="Capital City", type="location")
        self.port = Entity(name="Port Town", type="location")
        self.mountain = Entity(name="Dragon Mountain", type="location")
        
        # Create sample events
        self.battle = Event(name="Great Battle", lore_date=1000.0)
        
        # Add markers for entities
        capital_marker = MapMarker(
            map_id=self.game_map.id,
            object_id=self.capital.id,
            object_type="entity",
            x=0.5,
            y=0.6,
        )
        self.map_widget.add_marker(
            capital_marker,
            "Capital City",
            QColor("#FFD700")  # Gold
        )
        
        port_marker = MapMarker(
            map_id=self.game_map.id,
            object_id=self.port.id,
            object_type="entity",
            x=0.7,
            y=0.8,
        )
        self.map_widget.add_marker(
            port_marker,
            "Port Town",
            QColor("#4169E1")  # Royal blue
        )
        
        mountain_marker = MapMarker(
            map_id=self.game_map.id,
            object_id=self.mountain.id,
            object_type="entity",
            x=0.3,
            y=0.2,
        )
        self.map_widget.add_marker(
            mountain_marker,
            "Dragon Mountain",
            QColor("#8B4513")  # Saddle brown
        )
        
        # Add marker for event
        battle_marker = MapMarker(
            map_id=self.game_map.id,
            object_id=self.battle.id,
            object_type="event",
            x=0.6,
            y=0.4,
        )
        self.map_widget.add_marker(
            battle_marker,
            "Great Battle",
            QColor("#DC143C")  # Crimson
        )
        
        print("Demo setup complete!")
        print(f"- Loaded map: {self.game_map.name}")
        print(f"- Added {len(self.map_widget.markers)} markers")
        print("\nTry these features:")
        print("  - Pan: Drag with left mouse button")
        print("  - Zoom: Mouse wheel")
        print("  - Add Marker: Click 'Add Marker' button, then click on map")
        print("  - Calibrate: Click 'Calibrate Scale' to set real-world dimensions")
        print("  - Reset View: Click 'Reset View' to return to 100% zoom")
        print("  - Fit: Click 'Fit' to fit entire map in window")
        
    def _on_marker_placement(self, x: float, y: float):
        """Handle marker placement request."""
        print(f"Marker placement requested at ({x:.3f}, {y:.3f})")
        
        # Create a new marker
        new_marker = MapMarker(
            map_id=self.game_map.id,
            object_id="new-location",
            object_type="entity",
            x=x,
            y=y,
        )
        
        self.map_widget.add_marker(
            new_marker,
            f"New Location ({x:.2f}, {y:.2f})",
            QColor("#00FF00")  # Lime green
        )
        
    def _on_calibration_changed(self, real_width: float, unit: str):
        """Handle calibration change."""
        print(f"Calibration changed: {real_width} {unit}")
        
    def closeEvent(self, event):
        """Cleanup when closing."""
        # Delete temporary file
        if hasattr(self, 'demo_map_path'):
            Path(self.demo_map_path).unlink(missing_ok=True)
        event.accept()


def main():
    """Run the demo application."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show demo window
    window = MapDemoWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
