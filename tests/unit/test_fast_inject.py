"""
Unit tests for Fast Inject Core Module.
"""

import json
from pathlib import Path

import pytest
from src.core.entities import Entity
from src.core.events import Event
from src.core.fast_inject import FastInjectManager, FastInjectTemplate


@pytest.fixture
def temp_world_dir(tmp_path):
    """Create a temporary world directory structure."""
    world_dir = tmp_path / "test_world"
    world_dir.mkdir()
    (world_dir / "fastinject").mkdir()
    return world_dir


@pytest.fixture
def manager(temp_world_dir):
    """Create a FastInjectManager instance."""
    return FastInjectManager(temp_world_dir)


def test_template_serialization():
    """Test to_dict and from_dict."""
    original = FastInjectTemplate(
        name="Test Template",
        description="Desc",
        tags=["Tag1", "Tag2"],
        attributes={"Attr1": "Val1", "Attr2": 10},
        target_type="entity",
    )

    data = original.to_dict()
    restored = FastInjectTemplate.from_dict(data)

    assert restored.name == original.name
    assert restored.description == original.description
    assert restored.tags == original.tags
    assert restored.attributes == original.attributes
    assert restored.target_type == original.target_type


def test_save_and_load_templates(manager):
    """Test saving and loading templates from disk."""
    t1 = FastInjectTemplate(name="Wiki Template", tags=["Wiki"])
    t2 = FastInjectTemplate(name="Novel Template", tags=["Draft"])

    manager.save_template(t1)
    manager.save_template(t2)

    loaded = manager.load_templates()
    assert len(loaded) == 2

    names = [t.name for t in loaded]
    assert "Wiki Template" in names
    assert "Novel Template" in names


def test_create_from_target():
    """Test creating a template from an existing Entity."""
    entity = Entity(
        name="Source Entity",
        type="Character",
        attributes={"Strength": 10, "City": "Berlin", "_internal": 123},
    )
    entity.tags = ["Hero", "Warrior"]

    manager = FastInjectManager(Path("."))
    template = manager.create_template_from_target(
        entity, name="Hero Template", include_tags=True, include_attributes=None  # All
    )

    assert template.name == "Hero Template"
    assert "Hero" in template.tags
    assert "Warrior" in template.tags
    assert template.attributes["Strength"] == 10
    assert template.attributes["City"] == "Berlin"
    assert "_internal" not in template.attributes  # Internal filtered
    assert template.target_type == "entity"


def test_create_from_target_event():
    """Test creating a template from an existing Event."""
    event = Event(name="Source Event", lore_date=100.0)
    event.attributes = {"Casualties": "None"}
    event.tags = ["Battle"]

    manager = FastInjectManager(Path("."))
    template = manager.create_template_from_target(event, "Battle Template")

    assert template.target_type == "event"
    assert "Battle" in template.tags
    assert template.attributes["Casualties"] == "None"


def test_apply_template_no_overwrite():
    """Test applying template without overwriting existing keys."""
    manager = FastInjectManager(Path("."))
    entity = Entity(name="Target", type="Character", attributes={"Gold": 100})
    entity.tags = ["OldTag"]

    template = FastInjectTemplate(
        name="Rich Template", tags=["Rich"], attributes={"Gold": 9999, "Silver": 500}
    )

    manager.apply_template(entity, template, overwrite=False)

    # Tags merged
    assert "OldTag" in entity.tags
    assert "Rich" in entity.tags

    # Gold preserved (no overwrite)
    assert entity.attributes["Gold"] == 100
    # Silver added
    assert entity.attributes["Silver"] == 500


def test_apply_template_with_overwrite():
    """Test applying template with overwrite."""
    manager = FastInjectManager(Path("."))
    entity = Entity(name="Target", type="Character", attributes={"Gold": 100})

    template = FastInjectTemplate(name="Rich Template", attributes={"Gold": 9999})

    manager.apply_template(entity, template, overwrite=True)

    assert entity.attributes["Gold"] == 9999


def test_variable_resolution():
    """Test finding and replacing variables."""
    manager = FastInjectManager(Path("."))
    template = FastInjectTemplate(
        name="Var Template",
        attributes={
            "Location": "Near {{CITY}}",
            "Details": {"Boss": "{{BOSS_NAME}}"},
            "Static": "Fixed",
        },
    )

    # Test find
    vars_found = manager.find_variables(template)
    assert "CITY" in vars_found
    assert "BOSS_NAME" in vars_found
    assert len(vars_found) == 2

    # Test apply
    entity = Entity(name="Target", type="Location")
    variables = {"CITY": "London", "BOSS_NAME": "Big Bad"}

    manager.apply_template(entity, template, variables=variables)

    assert entity.attributes["Location"] == "Near London"
    assert entity.attributes["Details"]["Boss"] == "Big Bad"
    assert entity.attributes["Static"] == "Fixed"


def test_import_template(manager, tmp_path):
    """Test importing an external file."""
    # Create external file
    external_dir = tmp_path / "downloads"
    external_dir.mkdir()
    ext_file = external_dir / "external.fastinject"

    t = FastInjectTemplate(name="External", tags=["Imported"])
    with open(ext_file, "w") as f:
        json.dump(t.to_dict(), f)

    # Import
    imported = manager.import_template(ext_file)

    assert imported is not None
    assert imported.name == "External"
    assert (
        imported.source_path.parent == manager.templates_dir
    )  # Moved to project folder
    assert (manager.templates_dir / "External.fastinject").exists()
