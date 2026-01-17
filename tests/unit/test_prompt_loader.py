"""
Unit tests for PromptLoader.

Tests template loading, listing, versioning, validation, and error handling.
"""

import pytest

from src.services.prompt_loader import PromptLoader, PromptTemplate


@pytest.fixture
def temp_templates_dir(tmp_path):
    """
    Create a temporary templates directory populated with sample template files for tests.

    Creates three files within a "templates" subdirectory:
    - test_template_v1.0.txt (metadata and multi-line content for version 1.0)
    - test_template_v2.0.txt (metadata and content for version 2.0)
    - other_template_v1.0.txt (a separate template family)

    Parameters:
        tmp_path (pathlib.Path): Base temporary directory provided by pytest.

    Returns:
        pathlib.Path: Path to the created "templates" directory containing the sample files.
    """
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    # Create valid template v1
    v1_content = """---
version: 1.0
template_id: test_template
name: Test Template v1
description: A test template
author: Test Author
created: 2026-01-16
tags: [test, example]
---

This is a test prompt for version 1.0.
It has multiple lines.
"""
    (templates_dir / "test_template_v1.0.txt").write_text(v1_content)

    # Create valid template v2
    v2_content = """---
version: 2.0
template_id: test_template
name: Test Template v2
description: An updated test template
author: Test Author
tags: [test, updated]
---

This is a test prompt for version 2.0.
It has been updated with new content.
"""
    (templates_dir / "test_template_v2.0.txt").write_text(v2_content)

    # Create another template family
    other_content = """---
version: 1.0
template_id: other_template
name: Other Template
description: Another template for testing
---

Different template content.
"""
    (templates_dir / "other_template_v1.0.txt").write_text(other_content)

    return templates_dir


@pytest.fixture
def loader(temp_templates_dir):
    """
    Create a PromptLoader configured to use the provided temporary templates directory.

    Parameters:
        temp_templates_dir (Path): Path to a temporary directory containing template files.

    Returns:
        PromptLoader: An instance configured to load templates from the given directory.
    """
    return PromptLoader(templates_dir=str(temp_templates_dir))


def test_load_template_v1(loader):
    """Test loading a specific version of a template."""
    template = loader.load_template("test_template", version="1.0")

    assert template.template_id == "test_template"
    assert template.version == "1.0"
    assert template.name == "Test Template v1"
    assert "version 1.0" in template.content
    assert "multiple lines" in template.content
    assert template.metadata["author"] == "Test Author"
    assert "test" in template.metadata["tags"]


def test_load_template_latest_version(loader):
    """Test loading the latest version when no version specified."""
    template = loader.load_template("test_template")

    assert template.template_id == "test_template"
    assert template.version == "2.0"  # Latest version
    assert template.name == "Test Template v2"
    assert "version 2.0" in template.content


def test_list_templates(loader):
    """Test listing all available templates."""
    templates = loader.list_templates()

    assert len(templates) == 3

    # Check that all templates are present
    template_ids = [(t["template_id"], t["version"]) for t in templates]
    assert ("test_template", "1.0") in template_ids
    assert ("test_template", "2.0") in template_ids
    assert ("other_template", "1.0") in template_ids

    # Check metadata is included
    test_v1 = next(
        t
        for t in templates
        if t["template_id"] == "test_template" and t["version"] == "1.0"
    )
    assert test_v1["name"] == "Test Template v1"
    assert test_v1["description"] == "A test template"


def test_get_latest_version(loader):
    """Test getting the latest version for a template ID."""
    latest = loader.get_latest_version("test_template")
    assert latest == "2.0"

    other_latest = loader.get_latest_version("other_template")
    assert other_latest == "1.0"


def test_validate_template_valid(loader, temp_templates_dir):
    """Test validation of a valid template."""
    template_path = temp_templates_dir / "test_template_v1.0.txt"
    is_valid, error = loader.validate_template(str(template_path))

    assert is_valid is True
    assert error is None


def test_validate_template_invalid_missing_file(loader):
    """Test validation of a non-existent template."""
    is_valid, error = loader.validate_template("/nonexistent/template.txt")

    assert is_valid is False
    assert "not found" in error.lower()


def test_validate_template_invalid_no_metadata(loader, tmp_path):
    """Test validation of template without metadata header."""
    invalid_file = tmp_path / "invalid.txt"
    invalid_file.write_text("Just content without metadata")

    is_valid, error = loader.validate_template(str(invalid_file))

    assert is_valid is False
    assert "metadata" in error.lower()


def test_validate_template_invalid_missing_closing_delimiter(loader, tmp_path):
    """Test validation of template with incomplete metadata."""
    invalid_file = tmp_path / "invalid.txt"
    invalid_file.write_text("---\nversion: 1.0\n\nNo closing delimiter")

    is_valid, error = loader.validate_template(str(invalid_file))

    assert is_valid is False
    assert "closing" in error.lower() or "invalid" in error.lower()


def test_validate_template_invalid_missing_required_field(loader, tmp_path):
    """Test validation of template missing required metadata field."""
    invalid_file = tmp_path / "invalid.txt"
    content = """---
version: 1.0
name: Test
---

Content here
"""
    invalid_file.write_text(content)

    is_valid, error = loader.validate_template(str(invalid_file))

    assert is_valid is False
    assert "template_id" in error.lower()


def test_validate_template_invalid_no_content(loader, tmp_path):
    """Test validation of template with metadata but no content."""
    invalid_file = tmp_path / "invalid.txt"
    content = """---
version: 1.0
template_id: test
name: Test
---

"""
    invalid_file.write_text(content)

    is_valid, error = loader.validate_template(str(invalid_file))

    assert is_valid is False
    assert "content" in error.lower()


def test_load_nonexistent_template(loader):
    """Test loading a template that doesn't exist."""
    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load_template("nonexistent_template")

    assert "nonexistent_template" in str(exc_info.value)


def test_load_nonexistent_version(loader):
    """Test loading a specific version that doesn't exist."""
    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load_template("test_template", version="99.0")

    assert "99.0" in str(exc_info.value)


def test_metadata_parsing(loader):
    """Test that metadata is correctly extracted and parsed."""
    template = loader.load_template("test_template", version="1.0")

    # Check all metadata fields
    assert template.metadata["version"] == "1.0"
    assert template.metadata["template_id"] == "test_template"
    assert template.metadata["name"] == "Test Template v1"
    assert template.metadata["description"] == "A test template"
    assert template.metadata["author"] == "Test Author"
    assert template.metadata["created"] == "2026-01-16"

    # Check list parsing
    assert isinstance(template.metadata["tags"], list)
    assert "test" in template.metadata["tags"]
    assert "example" in template.metadata["tags"]


def test_list_templates_empty_directory(tmp_path):
    """Test listing templates in an empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    loader = PromptLoader(templates_dir=str(empty_dir))
    templates = loader.list_templates()

    assert templates == []


def test_list_templates_nonexistent_directory(tmp_path):
    """Test listing templates when directory doesn't exist."""
    nonexistent_dir = tmp_path / "nonexistent"

    loader = PromptLoader(templates_dir=str(nonexistent_dir))
    templates = loader.list_templates()

    assert templates == []


def test_default_templates_directory():
    """Test that default templates directory resolves correctly."""
    loader = PromptLoader()

    # Should point to default_assets/templates/system_prompts
    assert loader.templates_dir.name == "system_prompts"
    assert "templates" in str(loader.templates_dir)
    assert "default_assets" in str(loader.templates_dir)


def test_prompt_template_str():
    """Test PromptTemplate string representation."""
    template = PromptTemplate(
        template_id="test",
        version="1.0",
        name="Test Template",
        content="Test content",
        metadata={},
    )

    str_repr = str(template)
    assert "test" in str_repr
    assert "1.0" in str_repr
    assert "Test Template" in str_repr


def test_load_template_strips_whitespace(loader):
    """Test that template content has leading/trailing whitespace stripped."""
    template = loader.load_template("test_template", version="1.0")

    # Content should not start or end with newlines
    assert not template.content.startswith("\n")
    assert not template.content.endswith("\n\n")


def test_list_templates_skips_invalid_filenames(loader, temp_templates_dir):
    """Test that list_templates skips files with invalid naming patterns."""
    # Create files with invalid names
    (temp_templates_dir / "invalid_name.txt").write_text("content")
    (temp_templates_dir / "no_version.txt").write_text("content")

    templates = loader.list_templates()

    # Should still only return the 3 valid templates
    assert len(templates) == 3


def test_get_latest_version_no_templates(loader, tmp_path):
    """Test get_latest_version when no templates exist for ID."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    loader = PromptLoader(templates_dir=str(empty_dir))

    with pytest.raises(FileNotFoundError) as exc_info:
        loader.get_latest_version("nonexistent")

    assert "nonexistent" in str(exc_info.value)


def test_load_real_fantasy_worldbuilder_v1():
    """Test loading the real fantasy_worldbuilder v1 template."""
    # Use default loader which points to actual templates
    loader = PromptLoader()

    # This test will only pass if the templates exist in the repo
    try:
        template = loader.load_template("fantasy_worldbuilder", version="1.0")

        assert template.template_id == "fantasy_worldbuilder"
        assert template.version == "1.0"
        assert "fantasy world-builder" in template.content.lower()
        assert "1.0 = 1 day" in template.content
    except FileNotFoundError:
        pytest.skip("Real templates not found (expected during isolated testing)")


def test_load_real_fantasy_worldbuilder_v2():
    """Test loading the real fantasy_worldbuilder v2 template."""
    loader = PromptLoader()

    try:
        template = loader.load_template("fantasy_worldbuilder", version="2.0")

        assert template.template_id == "fantasy_worldbuilder"
        assert template.version == "2.0"
        assert (
            "OUTPUT FORMAT" in template.content
            or "output format" in template.content.lower()
        )
        assert "json" in template.content.lower()
    except FileNotFoundError:
        pytest.skip("Real templates not found (expected during isolated testing)")


def test_load_few_shot():
    """Test loading few-shot examples."""
    loader = PromptLoader()

    try:
        examples = loader.load_few_shot()

        assert len(examples) > 200
        assert "Example 1" in examples
        assert "Character" in examples or "Location" in examples
        # Should have multiple examples
        assert examples.count("Example") >= 3
    except FileNotFoundError:
        pytest.skip("Few-shot examples not found (expected during isolated testing)")


def test_load_few_shot_custom_filename(temp_templates_dir):
    """Test loading few-shot examples with custom filename."""
    loader = PromptLoader(templates_dir=str(temp_templates_dir))

    # Create a custom few-shot file
    custom_few_shot = temp_templates_dir / "custom_examples.txt"
    custom_few_shot.write_text("Example 1: Test\nExample 2: Another test")

    examples = loader.load_few_shot("custom_examples.txt")

    assert "Example 1" in examples
    assert "Example 2" in examples


def test_load_few_shot_missing_file():
    """Test that loading nonexistent few-shot file raises FileNotFoundError."""
    loader = PromptLoader()

    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load_few_shot("nonexistent_examples.txt")

    assert "nonexistent_examples.txt" in str(exc_info.value)


def test_load_real_description_templates():
    """Test loading the real description templates."""
    loader = PromptLoader()

    try:
        # Test default template
        default = loader.load_template("description_default", version="1.0")
        assert default.template_id == "description_default"
        assert default.version == "1.0"
        assert "world-builder" in default.content.lower()
        assert "200 words" in default.content.lower() or "200" in default.metadata.get(
            "max_words", ""
        )

        # Test concise template
        concise = loader.load_template("description_concise", version="1.0")
        assert concise.template_id == "description_concise"
        assert concise.version == "1.0"
        assert (
            "concise" in concise.content.lower() or "brief" in concise.content.lower()
        )

        # Test detailed template
        detailed = loader.load_template("description_detailed", version="1.0")
        assert detailed.template_id == "description_detailed"
        assert detailed.version == "1.0"
        assert (
            "detailed" in detailed.content.lower()
            or "expansive" in detailed.content.lower()
        )
    except FileNotFoundError:
        pytest.skip("Real templates not found (expected during isolated testing)")
