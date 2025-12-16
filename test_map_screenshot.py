"""Generate a screenshot of the map widget for documentation."""

import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QColor, QPainter, QPen, QFont
from PySide6.QtCore import Qt, QTimer

from src.gui.widgets.map_widget import MapWidget
from src.core.maps import GameMap, MapMarker


def create_demo_map_image():
    """Create a visually interesting demo map."""
    pixmap = QPixmap(1600, 1200)
    pixmap.fill(QColor("#87CEEB"))  # Sky blue (ocean)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Draw land mass
    painter.setBrush(QColor("#90EE90"))  # Light green
    painter.setPen(QPen(QColor("#228B22"), 3))  # Forest green border
    
    # Create a rough continent shape
    from PySide6.QtGui import QPolygonF
    from PySide6.QtCore import QPointF
    
    continent = QPolygonF([
        QPointF(400, 200),
        QPointF(800, 150),
        QPointF(1200, 300),
        QPointF(1300, 600),
        QPointF(1100, 900),
        QPointF(700, 1000),
        QPointF(400, 800),
        QPointF(300, 500),
    ])
    painter.drawPolygon(continent)
    
    # Draw mountains
    painter.setBrush(QColor("#A0522D"))  # Sienna (brown)
    for x, y in [(500, 400), (900, 350), (700, 600)]:
        painter.drawEllipse(x-30, y-30, 60, 60)
    
    # Draw a river
    painter.setPen(QPen(QColor("#4169E1"), 5))  # Royal blue
    from PySide6.QtGui import QPainterPath
    path = QPainterPath()
    path.moveTo(600, 300)
    path.quadTo(700, 500, 800, 700)
    painter.drawPath(path)
    
    painter.end()
    
    temp_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False)
    pixmap.save(temp_file.name, "PNG")
    temp_file.close()
    
    return temp_file.name


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Create map widget
    widget = MapWidget()
    widget.resize(1400, 900)
    
    # Create and load map
    map_path = create_demo_map_image()
    game_map = GameMap(
        name="Continent of Aldoria",
        image_filename="aldoria.png",
        real_width=2000.0,
        distance_unit="km",
        reference_width=1600,
        reference_height=1200,
    )
    
    widget.load_map(game_map, map_path)
    
    # Add markers
    markers_data = [
        ("Goldspire (Capital)", 0.55, 0.55, "#FFD700"),
        ("Port Meridian", 0.65, 0.75, "#4169E1"),
        ("Iron Peak Mountains", 0.38, 0.35, "#8B4513"),
        ("Whispering Woods", 0.50, 0.65, "#228B22"),
        ("Battle of Crimson Fields", 0.60, 0.45, "#DC143C"),
    ]
    
    for name, x, y, color in markers_data:
        marker = MapMarker(
            map_id=game_map.id,
            object_id=f"obj-{name}",
            object_type="entity",
            x=x,
            y=y,
        )
        widget.add_marker(marker, name, QColor(color))
    
    # Show widget
    widget.show()
    
    # Take screenshot after a short delay
    def take_screenshot():
        pixmap = widget.grab()
        pixmap.save("/tmp/map_widget_screenshot.png", "PNG")
        print("Screenshot saved to /tmp/map_widget_screenshot.png")
        
        # Cleanup
        Path(map_path).unlink(missing_ok=True)
        app.quit()
    
    QTimer.singleShot(500, take_screenshot)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
