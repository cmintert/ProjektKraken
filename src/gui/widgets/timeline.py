from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QBrush, QPen, QColor, QPainter


class EventItem(QGraphicsItem):
    """
    Graphical representation of an Event on the timeline.
    """

    def __init__(self, event, scale_factor=10.0):
        super().__init__()
        self.event = event
        self.scale_factor = scale_factor

        # Position based on Lore Date
        self.setPos(event.lore_date * scale_factor, 0)

        # Visual properties
        self.width = 100
        self.height = 50
        self.color = QColor(100, 150, 200)

        # Selection & Transform
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsFocusable
            | QGraphicsItem.ItemIgnoresTransformations
        )

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget=None):
        # Draw Shadow
        rect = self.boundingRect()
        shadow_rect = rect.translated(2, 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 50))
        painter.drawRoundedRect(shadow_rect, 5, 5)

        # Draw Box
        brush = QBrush(self.color)
        if self.isSelected():
            brush.setColor(self.color.lighter(130))

        painter.setBrush(brush)

        # Cosmetic pen for border
        pen = QPen(Qt.white if self.isSelected() else Qt.black)
        pen.setCosmetic(True)
        pen.setWidth(2 if self.isSelected() else 1)
        painter.setPen(pen)

        painter.drawRoundedRect(rect, 5, 5)

        # Draw Text
        # Name
        painter.setPen(QPen(Qt.white))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRectF(5, 5, self.width - 10, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.event.name,
        )

        # Date
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(
            QRectF(5, 25, self.width - 10, 15),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"{self.event.lore_date:,.0f}",
        )

        # Type
        type_color = QColor(200, 200, 200)
        painter.setPen(type_color)
        painter.drawText(
            QRectF(5, 25, self.width - 10, 15),
            Qt.AlignRight | Qt.AlignVCenter,
            self.event.type,
        )


class TimelineScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))


class TimelineWidget(QGraphicsView):
    """
    Widget to visualize events on a timeline.
    """

    event_selected = Signal(str)  # Emits event ID

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = TimelineScene(self)
        self.setScene(self.scene)

        # Navigation
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QPainter.Antialiasing)

        # State
        self.events = []
        self.scale_factor = 20.0  # Pixels per year/unit

    def set_events(self, events):
        """Populates the timeline with events."""
        self.scene.clear()
        self.events = events

        # Draw Axis
        axis_pen = QPen(Qt.white)
        axis_pen.setWidth(2)
        axis_pen.setCosmetic(True)  # Critical for visibility at zoom
        self.scene.addLine(-1e12, 0, 1e12, 0, axis_pen)

        for i, event in enumerate(events):
            item = EventItem(event, self.scale_factor)
            # Temporary Staggering
            y = (i % 5) * 60 + 50  # +50 to be below axis
            item.setY(y)

            self.scene.addItem(item)

        # Fit Logic
        if events:
            self.scene.setSceneRect(self.scene.itemsBoundingRect())
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        """Zoom in/out centered on mouse cursor."""
        # Standard Zoom Factors
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        # Workaround for Qt5/6 compatibility if needed, but PySide6 uses position()
        try:
            target_pos = event.position().toPoint()
        except AttributeError:
            target_pos = event.pos()

        # Save the scene pos under the mouse
        old_pos = self.mapToScene(target_pos)

        # Zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)

        # Get the new position under the mouse
        new_pos = self.mapToScene(target_pos)

        # Move scene to adjust for the zoom center
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.scene.itemAt(self.mapToScene(event.pos()), self.transform())
        if isinstance(item, EventItem):
            self.event_selected.emit(item.event.id)
