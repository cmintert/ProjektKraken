from src.core.events import Event
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.timeline import EventItem


class TestEventDuration:

    def test_event_editor_has_duration_field(self, qtbot):
        widget = EventEditorWidget()
        qtbot.addWidget(widget)

        assert hasattr(widget, "duration_widget")

    def test_event_editor_loads_saves_duration(self, qtbot):
        widget = EventEditorWidget()
        qtbot.addWidget(widget)

        event = Event(name="Test Event", lore_date=100.0, lore_duration=5.5)
        widget.load_event(event)

        assert widget.duration_widget.get_value() == 5.5

        # Change value
        widget.duration_widget.set_value(10.0)

        # Check save signal
        with qtbot.waitSignal(widget.save_requested) as blocker:
            widget._on_save()

        data = blocker.args[0]
        assert data["lore_duration"] == 10.0

    def test_event_item_rect_no_duration(self):
        event = Event(name="Point Event", lore_date=100.0, lore_duration=0.0)
        item = EventItem(event, scale_factor=10.0)

        rect = item.boundingRect()
        # Should be the diamond rect (roughly centered on 0,0 with icon size)
        # ICON_SIZE=14, so -7 to +7 roughly plus text width
        assert rect.height() > 14

    def test_event_item_rect_with_duration(self):
        duration = 5.0
        scale = 10.0
        event = Event(name="Span Event", lore_date=100.0, lore_duration=duration)
        item = EventItem(event, scale_factor=scale)

        rect = item.boundingRect()
        expected_width = duration * scale

        assert rect.width() == expected_width
        assert rect.height() == 30  # Fixed height for bar logic
        assert rect.top() == -10
