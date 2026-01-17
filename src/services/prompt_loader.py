"""
Prompt Template Loader Module.

Provides functionality for loading and managing prompt templates from the filesystem.
Templates consist of YAML metadata headers and prompt content, supporting versioning
and validation.
"""

import logging
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
        """
        Return a concise human-readable representation of the PromptTemplate.

        Returns:
            str: A string in the form "PromptTemplate({template_id} v{version}: {name})".
        """
        return f"PromptTemplate({self.template_id} v{self.version}: {self.name})"


class PromptLoader:
    """
    Loads and manages prompt templates from the filesystem.

    Templates are stored in a directory structure with YAML metadata headers.
    Supports template discovery, versioning, and validation.

    The default templates directory is
    `default_assets/templates/system_prompts/` relative to the package root.
    """

    def __init__(self, templates_dir: Optional[str] = None) -> None:
        """
        Initialize the PromptLoader and set the templates directory.

        If `templates_dir` is provided, uses it; otherwise resolves the default
        templates directory relative to the package root (default_assets/templates/system_prompts).
        Logs the chosen directory and emits a warning if the directory does not exist.

        Parameters:
            templates_dir (Optional[str]): Path to a custom templates directory.
        """
        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            # Default to default_assets/templates/system_prompts
            # Resolve relative to package root (parent of src/)
            package_root = Path(__file__).parent.parent.parent
            self.templates_dir = (
                package_root / "default_assets" / "templates" / "system_prompts"
            )

        logger.debug(f"PromptLoader initialized with directory: {self.templates_dir}")

        # Validate directory exists
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory does not exist: {self.templates_dir}")

    def load_template(
        self, template_id: str, version: Optional[str] = None
    ) -> PromptTemplate:
        """
        Load a specific template by ID and optional version.

        If no version is specified, loads the latest available version.

        Args:
            template_id: Unique identifier for the template
                (e.g., "fantasy_worldbuilder").
            version: Optional version string (e.g., "1.0").
                If None, loads latest.

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
        Discover available prompt templates in the templates directory and return their metadata.

        Scans for files matching the pattern "<template_id>_v<version>.txt", parses each file's metadata header, and collects a summary for each valid template.

        Returns:
            A list of dictionaries, one per discovered template. Each dictionary contains:
                - template_id (str): Template family identifier.
                - version (str): Template semantic version.
                - name (str): Human-readable template name.
                - description (str): Template description if present, otherwise empty string.
                - file_path (str): Filesystem path to the template file.
                - metadata (dict): Parsed metadata dictionary from the template file.
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
                logger.debug(
                    f"Skipping file with invalid name format: {file_path.name}"
                )
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
        Determine the highest available version for a given template ID by scanning template files named "{template_id}_v{version}.txt".

        Parameters:
            template_id (str): Template identifier used in filenames (e.g., "welcome_email" for files like "welcome_email_v1.0.txt").

        Returns:
            latest_version (str): The highest version string found (e.g., "2.0").

        Raises:
            FileNotFoundError: If the templates directory does not exist or no templates are found for the given ID.
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
        Validate a prompt template file's structure and required metadata.

        Checks that the file exists, begins with a metadata header delimited by '---',
        contains non-empty prompt content after the closing '---', and includes the
        required metadata fields: 'version', 'template_id', and 'name'.

        Parameters:
            file_path: Path to the template file to validate.

        Returns:
            (is_valid, error_message): is_valid is True when the file meets format and metadata requirements, False otherwise. error_message is None when valid; otherwise contains a short description of the problem.
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
        Parse a lightweight YAML-like metadata string into a dictionary.

        Supports simple `key: value` pairs and list values written as `[item1, item2]`. Blank lines and lines starting with `#` are ignored; lines without a colon are skipped.

        Parameters:
            yaml_text (str): Metadata text to parse.

        Returns:
            Dict[str, Any]: A mapping of metadata keys to values. Values are strings or lists of strings for bracketed lists.
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

    def load_few_shot(self, filename: str = "few_shot_description.txt") -> str:
        """
        Load few-shot examples from the templates directory.

        Few-shot examples are plain text files (no metadata header) that contain
        example prompts and outputs to guide LLM generation.

        Args:
            filename: Name of the few-shot examples file (default: "few_shot_description.txt").

        Returns:
            str: The content of the few-shot examples file.

        Raises:
            FileNotFoundError: If the few-shot file doesn't exist.
        """
        file_path = self.templates_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"Few-shot examples file not found: {file_path}")

        logger.info(f"Loading few-shot examples from {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return content.strip()
