import pytest

from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    MonthDefinition,
    WeekDefinition,
)
from src.gui.dialogs.relation_dialog import RelationEditDialog


@pytest.fixture
def converter():
    return CalendarConverter(
        CalendarConfig(
            id="custom",
            name="Custom",
            months=[MonthDefinition(name="Summer", abbreviation="Su", days=40)],
            week=WeekDefinition(day_names=["Day"], day_abbreviations=["D"]),
            year_variants=[],
            epoch_name="Era",
        )
    )


@pytest.mark.parametrize("time", [0.0, -20.25, 125.512345])
@pytest.mark.parametrize("side", ["start", "end"])
def test_now_is_exact_and_preserves_other_boundary(qtbot, converter, time, side):
    other = "end" if side == "start" else "start"
    attributes = {
        "temporal": {
            "schema": 1,
            "behavior": "stateful",
            "start": {"status": "open"},
            "end": {"status": "unknown"},
        },
        "custom": "retained",
    }
    dialog = RelationEditDialog(
        attributes=attributes, calendar_converter=converter, playhead_time=time
    )
    qtbot.addWidget(dialog)
    assert converter.format_datetime(time) in dialog.now_label.text()
    button = dialog.starts_now_button if side == "start" else dialog.ends_now_button
    button.click()
    result = dialog.get_data()[3]
    assert result["temporal"][side] == {"exact": time}
    assert result["temporal"][other] == attributes["temporal"][other]
    assert result["custom"] == "retained"
    reopened = RelationEditDialog(
        attributes=result, calendar_converter=converter, source_event_date=999.0
    )
    qtbot.addWidget(reopened)
    assert reopened.rb_absolute.isChecked()
    assert reopened.get_data()[3]["temporal"] == result["temporal"]


def test_end_now_preserves_dynamic_start_on_reopen(qtbot, converter):
    dialog = RelationEditDialog(
        source_event_date=100.0, calendar_converter=converter, playhead_time=125.5
    )
    qtbot.addWidget(dialog)
    dialog.ends_now_button.click()
    result = dialog.get_data()[3]
    assert result["temporal"]["start"] == {"binding": "source_event"}
    assert result["temporal"]["end"] == {"exact": 125.5}
    reopened = RelationEditDialog(
        attributes=result, source_event_date=110.0, calendar_converter=converter
    )
    qtbot.addWidget(reopened)
    assert reopened.get_data()[3]["temporal"] == result["temporal"]


def test_missing_context_disables_now(qtbot):
    dialog = RelationEditDialog(playhead_time=0.0)
    qtbot.addWidget(dialog)
    assert not dialog.starts_now_button.isEnabled()
    assert not dialog.ends_now_button.isEnabled()


def test_playhead_attributes_survive_command_undo_redo(qtbot, converter, db_service):
    from src.commands.relation_commands import AddRelationCommand, UpdateRelationCommand
    from src.core.entities import Entity

    source = Entity(name="Source", type="Character")
    target = Entity(name="Target", type="Place")
    db_service.insert_entity(source)
    db_service.insert_entity(target)
    dialog = RelationEditDialog(calendar_converter=converter, playhead_time=125.512345)
    qtbot.addWidget(dialog)
    dialog.starts_now_button.click()
    attrs = dialog.get_data()[3]
    add = AddRelationCommand(source.id, target.id, "owns", attrs)
    assert add.execute(db_service).success
    add.undo(db_service)
    assert not db_service.get_relations(source.id)
    assert add.execute(db_service).success
    relation = db_service.get_relations(source.id)[0]
    assert relation["attributes"]["temporal"]["start"] == {"exact": 125.512345}
    dialog.ends_now_button.click()
    update = UpdateRelationCommand(
        relation["id"], target.id, "owns", dialog.get_data()[3]
    )
    assert update.execute(db_service).success
    update.undo(db_service)
    assert db_service.get_relation(relation["id"])["attributes"] == attrs
    assert update.execute(db_service).success
    assert db_service.get_relation(relation["id"])["attributes"]["temporal"]["end"] == {
        "exact": 125.512345
    }


def test_manual_edit_replaces_captured_now(qtbot, converter):
    dialog = RelationEditDialog(calendar_converter=converter, playhead_time=125.5)
    qtbot.addWidget(dialog)
    dialog.starts_now_button.click()
    dialog.valid_from.set_value(130.0)
    dialog.valid_from.value_changed.emit(130.0)
    assert dialog.get_data()[3]["temporal"]["start"] == {"exact": 130.0}
