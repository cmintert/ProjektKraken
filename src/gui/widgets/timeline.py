from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QBrush, QPen, QColor, QPainter, QPolygonF
import math


class EventItem(QGraphicsItem):
    """
    Diamond-shaped event marker with text label.
    Color-coded by event type.
    """

    COLORS = {
        "generic": QColor("#888888"),
        "cosmic": QColor("#8E44AD"),  # Purple
        "historical": QColor("#F39C12"),  # Orange
        "personal": QColor("#2ECC71"),  # Green
        "session": QColor("#3498DB"),  # Blue
        "combat": QColor("#E74C3C"),  # Red
    }

    def __init__(self, event, scale_factor=10.0):
        super().__init__()
        self.event = event
        self.scale_factor = scale_factor

        # Fixed Visual Size (ItemIgnoresTransformations)
        self.icon_size = 14
        self.padding = 5

        # Determine Color
        self.base_color = self.COLORS.get(event.type, self.COLORS["generic"])

        # Position is handled by parent/layout, but X is strictly date-based
        self.setPos(event.lore_date * scale_factor, 0)

        # Flags: Fixed size on screen
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsFocusable
            | QGraphicsItem.ItemIgnoresTransformations
        )

    def boundingRect(self) -> QRectF:
        # Bounding box includes Diamond + Text
        return QRectF(-self.icon_size, -self.icon_size, 300, self.icon_size * 2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Draw Diamond Icon
        diamond = QPolygonF(
            [
                QPointF(0, -self.icon_size / 2),
                QPointF(self.icon_size / 2, 0),
                QPointF(0, self.icon_size / 2),
                QPointF(-self.icon_size / 2, 0),
            ]
        )

        brush = QBrush(self.base_color)
        if self.isSelected():
            brush.setColor(self.base_color.lighter(130))

        painter.setBrush(brush)

        # Border
        pen = QPen(Qt.white if self.isSelected() else Qt.black)
        pen.setCosmetic(True)  # Keep border crisp
        pen.setWidth(2 if self.isSelected() else 1)
        painter.setPen(pen)

        painter.drawPolygon(diamond)

        # 2. Draw Text Label (to the right)
        text_x = self.icon_size / 2 + self.padding

        # Title
        painter.setPen(QPen(Qt.white))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QPointF(text_x, -2), self.event.name)

        # Date
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        date_str = f"{self.event.lore_date:,.1f}"
        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.drawText(QPointF(text_x, 10), date_str)


class TimelineScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor("#1E1E1E")))  # Dark Aeon-like BG


class TimelineWidget(QGraphicsView):
    event_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = TimelineScene(self)
        self.setScene(self.scene)

        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # Viewport alignment
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.events = []
        self.scale_factor = 20.0

    def drawForeground(self, painter, rect):
        """
        Draws a sticky ruler at the top of the viewport using Screen Coordinates.
        """
        # 1. Switch to Screen Coordinates
        painter.save()
        painter.resetTransform()  # Now we draw in pixels (0,0 is top-left of view)

        viewport_rect = self.viewport().rect()
        w = viewport_rect.width()
        h = 40  # Ruler Height

        # Background
        painter.setBrush(QColor(40, 40, 40))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, w, h)

        # Bottom Line
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.drawLine(0, h, w, h)

        # 2. Determine Time Range visible
        # Map 0 and w to scene coordinates to find "Lore Date" bounds
        left_scene_x = self.mapToScene(0, 0).x()
        right_scene_x = self.mapToScene(w, 0).x()

        start_date = left_scene_x / self.scale_factor
        end_date = right_scene_x / self.scale_factor
        date_range = end_date - start_date

        if date_range <= 0:
            painter.restore()
            return

        # 3. Calculate Step Size (Nice Ticks)
        # We want a tick roughly every 100 pixels
        target_ticks = max(1, w / 100)
        raw_step = date_range / target_ticks

        # Round to nice power of 10
        try:
            exponent = math.floor(math.log10(raw_step))
            step = 10**exponent

            # Refine
            residual = raw_step / step
            if residual > 5:
                step *= 5
            elif residual > 2:
                step *= 2
        except:
            step = 1

        # 4. Draw Ticks
        # Align start to step
        current_date = math.floor(start_date / step) * step

        # Font Settings
        painter.setPen(QColor(200, 200, 200))
        font = painter.font()
        font.setPointSize(9)  # Fixed size
        painter.setFont(font)

        while current_date <= end_date:
            # Map date -> scene x -> screen x
            scene_x = current_date * self.scale_factor
            screen_pos = self.mapFromScene(
                QPointF(scene_x, 0)
            )  # QPointF required for precision?
            screen_x = screen_pos.x()

            # Draw if within bounds (add buffer for text)
            if -50 <= screen_x <= w + 50:
                # Tick Line
                painter.drawLine(int(screen_x), h - 10, int(screen_x), h)

                # Label
                label = f"{current_date:,.0f}"
                if abs(current_date) >= 1e9:
                    label = f"{current_date/1e9:g}B"
                elif abs(current_date) >= 1e6:
                    label = f"{current_date/1e6:g}M"
                elif abs(current_date) >= 1e3:
                    label = f"{current_date/1e3:g}k"

                # Draw Text
                painter.drawText(
                    QRectF(screen_x + 4, 0, 80, h - 2),
                    Qt.AlignBottom | Qt.AlignLeft,
                    label,
                )

                # Vertical Grid (Optional)
                painter.setPen(QColor(255, 255, 255, 10))
                painter.drawLine(
                    int(screen_x), h, int(screen_x), viewport_rect.height()
                )
                painter.setPen(QColor(200, 200, 200))

            current_date += step

        painter.restore()

    def set_events(self, events):
        self.scene.clear()

        # Sort by Date
        sorted_events = sorted(events, key=lambda e: e.lore_date)
        self.events = sorted_events

        # Draw Infinite Axis Line
        axis_pen = QPen(QColor(100, 100, 100))
        axis_pen.setCosmetic(True)
        self.scene.addLine(-1e12, 0, 1e12, 0, axis_pen)

        # Layout Logic: Modulo Stacking
        for i, event in enumerate(sorted_events):
            item = EventItem(event, self.scale_factor)

            # Cyclic Lane assignment
            lane_index = i % 8
            LANE_HEIGHT = 40
            y = (lane_index * LANE_HEIGHT) + 60  # Start below ruler (40px) + Gap

            item.setY(y)

            # Draw Drop Line
            line = self.scene.addLine(
                item.x(), 0, item.x(), y, QPen(QColor(80, 80, 80), 1, Qt.DashLine)
            )
            line.setZValue(-1)

            self.scene.addItem(item)

        if sorted_events:
            self.scene.setSceneRect(self.scene.itemsBoundingRect())
            # Don't autofit every refresh
            if not self.transform().m11() > 0:
                self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        zoom_in = 1.25
        zoom_out = 1 / zoom_in
        factor = zoom_in if event.angleDelta().y() > 0 else zoom_out

        try:
            target = event.position().toPoint()
        except:
            target = event.pos()

        old_pos = self.mapToScene(target)
        self.scale(factor, factor)
        new_pos = self.mapToScene(target)
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.scene.itemAt(self.mapToScene(event.pos()), self.transform())
        # Traverse up if needed
        if isinstance(item, EventItem):
            self.event_selected.emit(item.event.id)

    def focus_event(self, event_id: str):
        """Centers the view on the specified event."""
        for item in self.scene.items():
            if isinstance(item, EventItem) and item.event.id == event_id:
                self.centerOn(item)
                item.setSelected(True)
                return
