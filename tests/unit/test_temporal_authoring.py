"""End-to-end coverage for advanced date authoring and separate source claims."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QDialog, QWidget

from src.commands.event_commands import UpdateEventCommand
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.events import Event
from src.core.temporal_authoring import author_temporal_evidence, with_explicit_limits
from src.core.temporal_expression import expression_from_attributes
from src.gui.dialogs.temporal_evidence_dialog import TemporalEvidenceDialog
from src.gui.widgets.event_editor import EventEditorWidget

pytestmark = pytest.mark.ci_fast


def test_limits_do_not_invent_duration_or_nominal_containment():
    parser = DateParser(CalendarConfig.create_default())
    expression = parser.parse_expression("c. 961")
    bounded = with_explicit_limits(expression, parser, "959", "963")
    bounds = bounded.resolve_bounds(parser.converter)
    assert bounds.hard_start == parser.converter.start_of_year(959)
    assert bounds.hard_end == parser.converter.start_of_year(964)
    assert bounded.original_text == "c. 961"
    with pytest.raises(ValueError):
        with_explicit_limits(expression, parser, "965", "963")


@pytest.mark.parametrize(
    "text", ["963", "17 May 963", "17 May 963 14:30", "17 May 963 14:30:20"]
)
def test_reopened_limit_text_retains_inclusive_period(text):
    from src.core.temporal_authoring import explicit_limit_text

    parser = DateParser(CalendarConfig.create_default())
    bounds = parser.parse_expression(text).resolve_bounds(parser.converter)
    for upper, coordinate in ((False, bounds.hard_start), (True, bounds.hard_end)):
        rendered = explicit_limit_text(coordinate, parser.converter, upper=upper)
        reopened = parser.parse_expression(rendered).resolve_bounds(parser.converter)
        assert (reopened.hard_end if upper else reopened.hard_start) == pytest.approx(
            coordinate, abs=1e-9
        )


def test_ordering_only_metadata_does_not_reinterpret_a_legacy_date():
    parser = DateParser(CalendarConfig.create_default())
    metadata = author_temporal_evidence(
        {},
        parser,
        [],
        -1,
        [{"anchor_a": "event:a", "relation": "before", "anchor_b": "event:b"}],
    )
    assert expression_from_attributes({"_temporal_v2": metadata}) is None


def test_evidence_dialog_rejects_ordering_cycle(qtbot):
    parser = DateParser(CalendarConfig.create_default())
    dialog = TemporalEvidenceDialog("a", {}, parser, [("b", "Succession", "event")])
    qtbot.addWidget(dialog)
    dialog._add_order(
        {"anchor_a": "event:a", "relation": "before", "anchor_b": "event:b"}
    )
    dialog._add_order(
        {"anchor_a": "event:b", "relation": "before", "anchor_b": "event:a"}
    )
    dialog._accept_valid()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "cycle" in dialog.error.text()


def test_preferred_source_survives_editor_save_reload_export_and_undo(
    qtbot, db_service, monkeypatch
):
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    parser = DateParser(config)
    original = parser.parse_expression("961")
    event = Event(
        name="Execution",
        lore_date=0,
        attributes={"_temporal_v2": {"schema": 1, "expression": original.to_dict()}},
    )
    db_service.insert_event(event)
    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    editor = EventEditorWidget(parent)
    editor.set_calendar_converter(CalendarConverter(config))
    editor.load_event(event)

    def edit(dialog):
        dialog._add_claim("Chronicle A, page 12", "961")
        dialog._add_claim("Chronicle B, page 43", "964")
        dialog.preferred.setCurrentIndex(2)
        dialog._accept_valid()
        return dialog.result()

    monkeypatch.setattr(TemporalEvidenceDialog, "exec", edit)
    editor._edit_temporal_evidence()
    assert editor.temporal_widget.date_start.txt_date.text() == "964"
    with qtbot.waitSignal(editor.save_requested) as intent:
        editor._on_save()
    command = UpdateEventCommand(event.id, intent.args[0])
    assert command.execute(db_service).success
    saved = Event.from_dict(db_service.get_event(event.id).to_dict())
    metadata = saved.attributes["_temporal_v2"]
    assert [claim["expression"]["year"] for claim in metadata["claims"]] == [961, 964]
    assert metadata["preferred_claim_id"] == metadata["claims"][1]["id"]
    assert metadata["expression"]["explicit_outer_start"] is None
    assert saved.lore_duration == 0
    reopened = EventEditorWidget(parent)
    reopened.set_calendar_converter(CalendarConverter(config))
    reopened.load_event(saved)
    assert reopened.temporal_widget.date_start.txt_date.text() == "964"
    assert "2 claims" in reopened.temporal_evidence_button.text()
    command.undo(db_service)
    assert (
        expression_from_attributes(db_service.get_event(event.id).attributes).year
        == 961
    )


def test_claim_removal_preserves_identity_and_explicit_bounds(qtbot):
    parser = DateParser(CalendarConfig.create_default())
    metadata = author_temporal_evidence(
        {}, parser, [("A", "961"), ("B", "c. 964")], 1, []
    )
    expression = with_explicit_limits(
        parser.parse_expression("c. 964"), parser, "963", "965"
    )
    metadata["claims"][1]["expression"] = expression.to_dict()
    dialog = TemporalEvidenceDialog("a", metadata, parser, [])
    qtbot.addWidget(dialog)
    dialog.claims.setCurrentCell(0, 0)
    dialog._remove_claim()
    dialog._accept_valid()
    assert dialog.result() == QDialog.DialogCode.Accepted
    result = dialog.result_metadata
    assert result["claims"] == [metadata["claims"][1]]
    assert result["preferred_claim_id"] == metadata["claims"][1]["id"]
    assert result["expression"] == expression.to_dict()


def test_conflicting_sources_are_distinct_from_coarse_precision():
    from src.core.temporal_authoring import conflicting_claims

    parser = DateParser(CalendarConfig.create_default())
    coarse = author_temporal_evidence({}, parser, [("A", "961")], -1, [])
    assert not conflicting_claims(coarse, parser.converter)
    conflict = author_temporal_evidence(
        coarse, parser, [("A", "961"), ("B", "964")], -1, []
    )
    assert conflicting_claims(conflict, parser.converter)


def test_anchor_deletion_requires_dependency_confirmation_and_undo(db_service):
    from src.commands.event_commands import DeleteEventCommand

    anchor = Event(name="Execution", lore_date=1)
    follower = Event(
        name="Succession",
        lore_date=2,
        attributes={
            "_temporal_v2": {
                "schema": 1,
                "constraints": [
                    {
                        "anchor_a": "event:succession",
                        "relation": "after",
                        "anchor_b": f"event:{anchor.id}",
                    }
                ],
            }
        },
    )
    db_service.insert_event(anchor)
    db_service.insert_event(follower)
    rejected = DeleteEventCommand(anchor.id).execute(db_service)
    assert not rejected.success
    assert db_service.get_event(anchor.id) is not None
    confirmed = DeleteEventCommand.from_dict(
        DeleteEventCommand(anchor.id, rejected.data["temporal_dependencies"]).to_dict()
    )
    assert confirmed.execute(db_service).success
    assert db_service.get_event(anchor.id) is None
    assert db_service.get_event(follower.id).attributes == follower.attributes
    confirmed.undo(db_service)
    assert db_service.get_event(anchor.id) is not None


@pytest.mark.parametrize("confirmed", [False, True])
def test_deletion_confirmation_only_retries_after_user_choice(
    qtbot, monkeypatch, confirmed
):
    from PySide6.QtWidgets import QMessageBox

    from src.app.command_coordinator import CommandCoordinator
    from src.core.command import CommandResult

    window = QWidget()
    qtbot.addWidget(window)
    coordinator = CommandCoordinator(window)
    choices = []

    def answer(dialog):
        choices.append(dialog.detailedText())
        return (
            QMessageBox.StandardButton.Yes
            if confirmed
            else QMessageBox.StandardButton.Cancel
        )

    monkeypatch.setattr(QMessageBox, "exec", answer)
    requests = []
    coordinator.command_requested.connect(requests.append)
    coordinator.on_command_result(
        CommandResult(
            success=False,
            command_name="DeleteEventCommand",
            data={
                "temporal_dependencies": ["Event b: Succession"],
                "event_id": "a",
                "event_name": "Execution",
            },
        )
    )
    assert choices == ["Event b: Succession"]
    assert len(requests) == int(confirmed)
    assert coordinator.undo_stack == []


def test_relative_anchor_bounds_keep_only_evidence_and_no_false_identity():
    from src.core.temporal_expression import ResolvedTemporalBounds
    from src.core.temporal_window import resolve_temporal_window

    anchors = {"event:a": ResolvedTemporalBounds(100, 110, anchor_id="event:a")}
    for relation, expected in (("before", (None, 115)), ("after", (105, None))):
        window = resolve_temporal_window(
            {
                "temporal": {
                    "start": {
                        "anchor": {
                            "anchor_id": "event:a",
                            "relation": relation,
                            "offset_days": 5,
                        }
                    },
                    "end": {"status": "open"},
                }
            },
            anchors=anchors,
        )
        assert window.start_bounds is not None
        assert (
            window.start_bounds.hard_start,
            window.start_bounds.hard_end,
        ) == expected
        assert window.start_bounds.anchor_id is None


def test_graph_filters_time_before_deriving_connected_nodes(db_service):
    from copy import deepcopy

    from src.core.entities import Entity
    from src.core.graph_temporal import GraphTemporalMode
    from src.services.graph_data_service import GraphDataService

    a, b = Entity(name="A", type="person"), Entity(name="B", type="house")
    db_service.insert_entity(a)
    db_service.insert_entity(b)
    db_service.insert_relation(
        a.id, b.id, "Prima", attributes={"valid_from": 10, "valid_to": 20}
    )
    before = deepcopy(db_service.get_all_relations())
    service = GraphDataService()
    nodes, edges = service.get_graph_data(
        db_service,
        include_rel_types=["Prima"],
        lore_time=25,
        temporal_mode=GraphTemporalMode.AT_PLAYHEAD,
    )
    assert nodes == edges == []
    for mode in (
        GraphTemporalMode.HISTORY_TO_PLAYHEAD,
        GraphTemporalMode.ALL_RELATIONS,
    ):
        nodes, edges = service.get_graph_data(
            db_service, include_rel_types=["Prima"], lore_time=25, temporal_mode=mode
        )
        assert len(nodes) == 2 and len(edges) == 1
    assert db_service.get_all_relations() == before


def test_graph_hidden_uncertainty_can_be_revealed_and_selected(qtbot, monkeypatch):
    from src.gui.widgets.graph_view import GraphWidget

    graph = GraphWidget()
    qtbot.addWidget(graph)
    graph._all_nodes = [
        {"id": identity, "name": identity, "object_type": "entity"}
        for identity in ("a", "b")
    ]
    graph._all_edges = [
        {
            "id": "r",
            "source_id": "a",
            "target_id": "b",
            "rel_type": "Prima",
            "validity_status": "possible",
        }
    ]
    graph._is_renderer_ready = True
    render = MagicMock()
    monkeypatch.setattr(graph._web_view, "update_graph_data", render)
    graph.show_possible.setChecked(False)
    graph._refresh_display_locally()
    assert "1 hidden" in graph.temporal_count.text()
    assert render.call_args.args[1] == []
    graph._on_graph_node_clicked("entity", "a")
    assert "0 hidden" in graph.temporal_count.text()
    assert render.call_args.args[1][0]["validity_status"] == "possible"
    graph.show_possible.setChecked(True)
    graph._refresh_display_locally()
    assert len(render.call_args.args[1]) == 1


def test_random_custom_calendar_precision_invariants():
    import random

    from src.core.calendar import LeapYearRule, MonthDefinition, YearVariant
    from src.core.temporal_expression import TemporalExpression, TemporalPrecision

    rng = random.Random(961)
    for _ in range(35):
        config = CalendarConfig.create_default()
        config.months = [
            MonthDefinition(f"M{i}", f"M{i}", rng.randint(5, 45))
            for i in range(rng.randint(2, 16))
        ]
        config.leap_year_rules = [LeapYearRule(interval=3, month_index=0, extra_days=2)]
        config.year_variants = [
            YearVariant(year=4, months=[MonthDefinition("Variant", "V", 19)])
        ]
        converter = CalendarConverter(config)
        for year in (-3, 0, 1, 3, 4, 5):
            expression = TemporalExpression(
                config.id, year, precision=TemporalPrecision.YEAR
            )
            saved = expression.to_dict()
            bounds = expression.resolve_bounds(converter)
            assert bounds.hard_start < bounds.hard_end
            converter.from_float(expression.representative_time(converter))
            assert expression.to_dict() == saved
            months = config.get_months_for_year(year)
            for month in range(1, len(months) + 1):
                assert converter.start_of_next_month(year, month) == (
                    converter.start_of_month(year, month + 1)
                    if month < len(months)
                    else converter.start_of_next_year(year)
                )
