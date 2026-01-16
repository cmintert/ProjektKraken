"""
Prompt Template Loader Module.

Provides functionality for loading and managing prompt templates from the filesystem.
Templates consist of YAML metadata headers and prompt content, supporting versioning
and validation.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """
    Data class representing a loaded prompt template.

    Attributes:
        template_id: Unique identifier for the template family.
        version: Semantic version number (e.g., "1.0", "2.0").
        name: Human-readable name of the template.
        content: The actual prompt text content.
        metadata: Dictionary containing all metadata fields.
    """

    template_id: str
    version: str
    name: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Return string representation."""
        return f"PromptTemplate({self.template_id} v{self.version}: {self.name})"


class PromptLoader:
    """
    Loads and manages prompt templates from the filesystem.

    Templates are stored in a directory structure with YAML metadata headers.
    Supports template discovery, versioning, and validation.

    The default templates directory is `src/assets/templates/system_prompts/`
    relative to the package root.
    """

    def __init__(self, templates_dir: Optional[str] = None) -> None:
        """
        Initialize loader with optional custom templates directory.

        Args:
            templates_dir: Optional path to templates directory. If None,
                uses default location: src/assets/templates/system_prompts/
        """
        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            # Default to src/assets/templates/system_prompts
            # Resolve relative to this file's location
            package_root = Path(__file__).parent.parent
            self.templates_dir = (
                package_root / "assets" / "templates" / "system_prompts"
            )

        logger.debug(f"PromptLoader initialized with directory: {self.templates_dir}")

        # Validate directory exists
        if not self.templates_dir.exists():
            logger.warning(
                f"Templates directory does not exist: {self.templates_dir}"
            )

    def load_template(
        self, template_id: str, version: Optional[str] = None
    ) -> PromptTemplate:
        """
        Load a specific template by ID and optional version.

        If no version is specified, loads the latest available version.

        Args:
            template_id: Unique identifier for the template (e.g., "fantasy_worldbuilder").
            version: Optional version string (e.g., "1.0"). If None, loads latest.

        Returns:
            PromptTemplate: The loaded template with metadata and content.

        Raises:
            FileNotFoundError: If template file doesn't exist.
            ValueError: If template format is invalid.
        """
        # Determine version to load
        if version is None:
            version = self.get_latest_version(template_id)
            logger.debug(f"No version specified, using latest: {version}")

        # Construct filename: {template_id}_v{version}.txt
        filename = f"{template_id}_v{version}.txt"
        file_path = self.templates_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"Template file not found: {file_path} "
                f"(template_id={template_id}, version={version})"
            )

        logger.info(f"Loading template: {template_id} v{version} from {file_path}")

        # Validate and load
        is_valid, error_msg = self.validate_template(str(file_path))
        if not is_valid:
            raise ValueError(f"Invalid template format: {error_msg}")

        # Parse template file
        metadata, content = self._parse_template_file(str(file_path))

        # Create PromptTemplate object
        template = PromptTemplate(
            template_id=metadata.get("template_id", template_id),
            version=metadata.get("version", version),
            name=metadata.get("name", f"Template {template_id}"),
            content=content.strip(),
            metadata=metadata,
        )

        logger.debug(f"Successfully loaded template: {template}")
        return template

    def list_templates(self) -> List[Dict[str, Any]]:
        """
        List all available templates with metadata.

        Scans the templates directory and returns a list of template
        information dictionaries.

        Returns:
            List[Dict]: List of dictionaries with template metadata.
                Each dict contains: template_id, version, name, file_path, metadata.
                Returns empty list if directory doesn't exist.
        """
        if not self.templates_dir.exists():
            logger.warning(
                f"Cannot list templates, directory missing: {self.templates_dir}"
            )
            return []

        templates = []
        pattern = re.compile(r"(.+)_v([\d.]+)\.txt$")

        for file_path in self.templates_dir.glob("*.txt"):
            match = pattern.match(file_path.name)
            if not match:
                logger.debug(f"Skipping file with invalid name format: {file_path.name}")
                continue

            template_id, version = match.groups()

            try:
                # Parse metadata only (quick scan)
                metadata, _ = self._parse_template_file(str(file_path))

                templates.append(
                    {
                        "template_id": metadata.get("template_id", template_id),
                        "version": metadata.get("version", version),
                        "name": metadata.get("name", f"Template {template_id}"),
                        "description": metadata.get("description", ""),
                        "file_path": str(file_path),
                        "metadata": metadata,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to parse template {file_path.name}: {e}")
                continue

        logger.debug(f"Found {len(templates)} templates")
        return templates

    def get_latest_version(self, template_id: str) -> str:
        """
        Get the latest version number for a template ID.

        Args:
            template_id: The template identifier to search for.

        Returns:
            str: The latest version number (e.g., "2.0").

        Raises:
            FileNotFoundError: If no templates found for the given ID.
        """
        if not self.templates_dir.exists():
            raise FileNotFoundError(
                f"Templates directory not found: {self.templates_dir}"
            )

        pattern = re.compile(rf"^{re.escape(template_id)}_v([\d.]+)\.txt$")
        versions = []

        for file_path in self.templates_dir.glob("*.txt"):
            match = pattern.match(file_path.name)
            if match:
                versions.append(match.group(1))

        if not versions:
            raise FileNotFoundError(
                f"No templates found for template_id: {template_id}"
            )

        # Sort versions using simple string comparison
        # For semantic versioning, this works if versions are like "1.0", "2.0"
        # More complex: could use packaging.version for full semver support
        versions.sort(key=lambda v: [int(x) for x in v.split(".")])
        latest = versions[-1]

        logger.debug(f"Latest version of {template_id}: {latest}")
        return latest

    def validate_template(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate template format and metadata.

        Checks for:
        - File existence
        - Valid YAML metadata header
        - Required metadata fields (version, template_id, name)
        - Presence of content after metadata

        Args:
            file_path: Path to the template file to validate.

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
                is_valid is True if template is valid, False otherwise.
                error_message is None if valid, otherwise contains error description.
        """
        path = Path(file_path)

        # Check file exists
        if not path.exists():
            return False, f"File not found: {file_path}"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for metadata delimiter
            if not content.startswith("---"):
                return False, "Missing metadata header (must start with '---')"

            # Split metadata and content
            parts = content.split("---", 2)
            if len(parts) < 3:
                return False, "Invalid metadata format (missing closing '---')"

            metadata_text = parts[1].strip()
            prompt_content = parts[2].strip()

            # Check for content
            if not prompt_content:
                return False, "Missing prompt content after metadata"

            # Parse metadata (simple YAML-like parsing)
            metadata = self._parse_yaml_metadata(metadata_text)

            # Check required fields
            required_fields = ["version", "template_id", "name"]
            for field in required_fields:
                if field not in metadata:
                    return False, f"Missing required metadata field: {field}"

            return True, None

        except Exception as e:
            return False, f"Error reading/parsing template: {str(e)}"

    def _parse_template_file(self, file_path: str) -> Tuple[Dict[str, Any], str]:
        """
        Parse a template file into metadata and content.

        Args:
            file_path: Path to the template file.

        Returns:
            Tuple[Dict, str]: (metadata_dict, content_text)

        Raises:
            ValueError: If file format is invalid.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.startswith("---"):
            raise ValueError("Template must start with '---' metadata delimiter")

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError("Invalid template format: missing closing '---'")

        metadata_text = parts[1].strip()
        prompt_content = parts[2].strip()

        metadata = self._parse_yaml_metadata(metadata_text)

        return metadata, prompt_content

    def _parse_yaml_metadata(self, yaml_text: str) -> Dict[str, Any]:
        """
        Parse YAML-like metadata into a dictionary.

        Simple parser for basic YAML structures without external dependencies.
        Supports: key: value, key: [list, items], basic strings.

        Args:
            yaml_text: YAML-formatted metadata text.

        Returns:
            Dict[str, Any]: Parsed metadata dictionary.
        """
        metadata = {}

        for line in yaml_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            # Parse lists: [item1, item2, item3]
            if value.startswith("[") and value.endswith("]"):
                list_content = value[1:-1]
                items = [item.strip() for item in list_content.split(",")]
                metadata[key] = items
            else:
                # Regular value
                metadata[key] = value

        return metadata
