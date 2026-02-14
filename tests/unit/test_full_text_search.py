import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.unified_list import UnifiedListWidget


@pytest.fixture
def app(qapp):
    return qapp


@pytest.fixture
def list_widget(app):
    widget = UnifiedListWidget()
    return widget


def test_search_matches_description(list_widget):
    event = Event(
        name="Generic Event",
        lore_date=100.0,
        description="Hidden Secret in description",
    )
    list_widget.set_data([event], [])

    model = list_widget._proxy_model
    list_widget.search_bar.setText("Secret")
    assert model.rowCount() == 1

    list_widget.search_bar.setText("Nothing")
    assert model.rowCount() == 0


def test_search_matches_tags(list_widget):
    event = Event(name="Tagged Event", lore_date=100.0)
    event.tags = ["urgent", "classified"]
    list_widget.set_data([event], [])

    model = list_widget._proxy_model
    list_widget.search_bar.setText("urgent")
    assert model.rowCount() == 1

    list_widget.search_bar.setText("random")
    assert model.rowCount() == 0


def test_search_matches_attributes(list_widget):
    entity = Entity(name="Attrib Entity", type="character")
    entity.attributes = {"alias": "The Shadow", "power": 9000}
    list_widget.set_data([], [entity])

    model = list_widget._proxy_model
    list_widget.search_bar.setText("Shadow")
    assert model.rowCount() == 1

    # Integers are not searched in current implementation
    list_widget.search_bar.setText("9000")
    assert model.rowCount() == 0


def test_search_matches_type(list_widget):
    entity = Entity(name="Dragon", type="monster")
    list_widget.set_data([], [entity])

    model = list_widget._proxy_model
    list_widget.search_bar.setText("monster")
    assert model.rowCount() == 1
