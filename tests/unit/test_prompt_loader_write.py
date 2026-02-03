
import pytest

from src.services.prompt_loader import PromptLoader


@pytest.fixture
def temp_templates_dir(tmp_path):
    """Create a temporary templates directory."""
    templates_dir = tmp_path / "templates" / "system_prompts"
    templates_dir.mkdir(parents=True)
    return templates_dir


@pytest.fixture
def loader(temp_templates_dir):
    """Create PromptLoader instance with temp directory."""
    return PromptLoader(templates_dir=str(temp_templates_dir))


def test_save_new_template(loader):
    """Test saving a new template creates the file correctly."""
    template_id = "test_new"
    content = "This is a test prompt."
    metadata = {"name": "Test Template", "description": "A test"}

    filename = loader.save_template(template_id, content, metadata)

    # Verify filename
    assert filename == "test_new_v1.0.txt"

    # Verify file existence
    file_path = loader.templates_dir / filename
    assert file_path.exists()

    # Verify content
    loaded = loader.load_template(template_id, "1.0")
    assert loaded.content == content
    assert loaded.name == "Test Template"
    assert loaded.version == "1.0"


def test_save_existing_template_increments_version(loader):
    """Test saving an existing template increments the version."""
    template_id = "test_v"
    loader.save_template(template_id, "v1", {"name": "V1"})

    # Save again (should be v1.1)
    loader.save_template(template_id, "v2", {"name": "V2"})

    v2_path = loader.templates_dir / "test_v_v1.1.txt"
    assert v2_path.exists()

    loaded = loader.load_template(template_id)
    assert loaded.version == "1.1"
    assert loaded.content == "v2"


def test_save_specific_version(loader):
    """Test saving with a specific version in metadata."""
    template_id = "test_custom_v"
    loader.save_template(template_id, "content", {"name": "N", "version": "2.5"})

    path = loader.templates_dir / "test_custom_v_v2.5.txt"
    assert path.exists()


def test_delete_template(loader):
    """Test deleting a template removes all versions."""
    template_id = "test_del"
    loader.save_template(template_id, "v1", {"name": "N"})
    loader.save_template(template_id, "v2", {"name": "N", "version": "2.0"})

    assert (loader.templates_dir / "test_del_v1.0.txt").exists()
    assert (loader.templates_dir / "test_del_v2.0.txt").exists()

    deleted = loader.delete_template(template_id)

    assert len(deleted) == 2
    assert not (loader.templates_dir / "test_del_v1.0.txt").exists()
    assert not (loader.templates_dir / "test_del_v2.0.txt").exists()


def test_delete_nonexistent_template(loader):
    """Test deleting a non-existent template returns empty list."""
    deleted = loader.delete_template("ghost")
    assert deleted == []


def test_serialize_metadata_format(loader):
    """Test metadata serialization format."""
    metadata = {
        "template_id": "t1",
        "version": "1.0",
        "name": "Test",
        "tags": ["a", "b"],
    }
    serialized = loader._serialize_metadata(metadata)

    assert "template_id: t1" in serialized
    assert "version: 1.0" in serialized
    assert "name: Test" in serialized
    assert "tags: [a, b]" in serialized
