"""Fast Inject Core Module.

Handles logic for defining, loading, saving, and applying "Fast Inject" templates.
Templates allow rapid application of tags and attributes to Entities and Events.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.core.entities import Entity
from src.core.events import Event

logger = logging.getLogger(__name__)


@dataclass
class FastInjectTemplate:
    """Represents a reusable template of tags and attributes."""

    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    type_value: Optional[str] = None  # Specific type to apply
    target_type: str = "any"  # "entity", "event", or "any"
    version: str = "1.0"
    source_path: Optional[Path] = None  # Not serialized, used for UI tracking

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON storage."""
        return {
            "meta": {
                "name": self.name,
                "description": self.description,
                "target_type": self.target_type,
                "version": self.version,
            },
            "inject": {
                "tags": self.tags,
                "attributes": self.attributes,
                "type_value": self.type_value,
            },
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], path: Optional[Path] = None
    ) -> "FastInjectTemplate":
        """Create from dictionary."""
        meta = data.get("meta", {})
        inject = data.get("inject", {})
        return cls(
            name=meta.get("name", "Unnamed Template"),
            description=meta.get("description", ""),
            target_type=meta.get("target_type", "any"),
            version=meta.get("version", "1.0"),
            tags=inject.get("tags", []),
            attributes=inject.get("attributes", {}),
            type_value=inject.get("type_value"),
            source_path=path,
        )


class FastInjectManager:
    """Manages loading, validation, and application of Fast Inject templates."""

    def __init__(self, world_path: Path) -> None:
        """Initialize manager for a specific world.

        Args:
            world_path: Root directory of the world.

        """
        self.world_path = world_path
        self.templates_dir = world_path / "fastinject"
        self._templates: List[FastInjectTemplate] = []

    def ensure_directory(self) -> None:
        """Ensure the fastinject directory exists."""
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def load_templates(self) -> List[FastInjectTemplate]:
        """Load all valid .fastinject files from the directory.

        Returns:
            List of loaded templates.

        """
        self.ensure_directory()
        self._templates = []

        for file_path in self.templates_dir.glob("*.fastinject"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                template = FastInjectTemplate.from_dict(data, path=file_path)
                self._templates.append(template)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load template {file_path}: {e}")

        # Sort by name
        self._templates.sort(key=lambda t: t.name.lower())
        return self._templates

    def save_template(self, template: FastInjectTemplate) -> Path:
        """Save a template to disk.

        Args:
            template: The template to save.

        Returns:
            Path to the saved file.

        """
        self.ensure_directory()

        # Sanitize filename
        safe_name = "".join(
            c for c in template.name if c.isalnum() or c in (" ", "_", "-")
        ).strip()
        filename = f"{safe_name}.fastinject"
        file_path = self.templates_dir / filename

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(template.to_dict(), f, indent=2)

        template.source_path = file_path
        return file_path

    def delete_template(self, template: FastInjectTemplate) -> None:
        """Delete a template file."""
        if template.source_path and template.source_path.exists():
            template.source_path.unlink()
            if template in self._templates:
                self._templates.remove(template)

    def import_template(self, source_path: Path) -> FastInjectTemplate:
        """Import a template from an external location into the project.

        Args:
            source_path: Path to the .fastinject file to import.

        Returns:
            The imported FastInjectTemplate.

        Raises:
            FileNotFoundError: If source file doesn't exist.
            json.JSONDecodeError: If file is not valid JSON.
            ValueError: If file is not a valid template.

        """
        import shutil

        # Security: Resolve and validate existence
        source_path = source_path.resolve()

        if not source_path.exists():
            raise FileNotFoundError(f"Template file not found: {source_path}")

        if not source_path.is_file():
            raise ValueError(f"Template path is not a file: {source_path}")

        # Load and validate the template
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        template = FastInjectTemplate.from_dict(data)

        # Ensure target directory exists
        self.ensure_directory()

        # Determine target filename based on template name (handle duplicates)
        # Sanitize filename
        safe_name = "".join(
            c for c in template.name if c.isalnum() or c in (" ", "_", "-")
        ).strip()
        target_filename = f"{safe_name}.fastinject"
        target_path = self.templates_dir / target_filename

        # If file exists, add a suffix
        counter = 1
        while target_path.exists():
            target_filename = f"{safe_name}_{counter}.fastinject"
            target_path = self.templates_dir / target_filename
            counter += 1

        # Copy the file
        shutil.copy2(source_path, target_path)
        template.source_path = target_path

        # Add to cache
        self._templates.append(template)
        self._templates.sort(key=lambda t: t.name.lower())

        logger.info(f"Imported template '{template.name}' to {target_path}")
        return template

    def create_template_from_target(
        self,
        target: Union[Entity, Event],
        name: str,
        description: str = "",
        include_tags: bool = True,
        include_attributes: List[str] = None,
        include_type: bool = False,
    ) -> FastInjectTemplate:
        """Create a new template object from an existing target.

        Args:
            target: Entity or Event to copy from.
            name: Name for the new template.
            description: Description.
            include_tags: Whether to include all tags.
            include_attributes: List of attribute keys to include.
                                None means all (excluding internal).
            include_type: Whether to include the target's type.

        Returns:
            New FastInjectTemplate object (not saved to disk yet).

        """
        tags = target.tags.copy() if include_tags else []

        # Filter attributes
        attrs = {}
        source_attrs = target.attributes.copy()

        # Exclude internal keys
        source_attrs.pop("_tags", None)

        if include_attributes is None:
            # Include all non-internal
            for k, v in source_attrs.items():
                if not k.startswith("_"):
                    attrs[k] = v
        else:
            # Include only specific keys
            for k in include_attributes:
                if k in source_attrs:
                    attrs[k] = source_attrs[k]

        target_type_str = "object"
        if isinstance(target, Entity):
            target_type_str = "entity"
        elif isinstance(target, Event):
            target_type_str = "event"

        type_val = target.type if include_type and hasattr(target, "type") else None

        return FastInjectTemplate(
            name=name,
            description=description,
            tags=tags,
            attributes=attrs,
            type_value=type_val,
            target_type=target_type_str,
        )

    def find_variables(self, template: FastInjectTemplate) -> List[str]:
        """Scan template values for {{VAR_NAME}} patterns.

        Returns:
            List of unique variable names found.

        """
        vars_found = set()
        # Match {{VAR}} or {{VAR:Opt1|Opt2}}
        # Group 1 is the VAR name
        pattern = re.compile(r"\{\{([A-Za-z0-9_]+)(?::[^}]+)?\}\}")

        def scan_value(val: Any) -> None:
            if isinstance(val, str):
                for match in pattern.findall(val):
                    # findall returns just the group 1 (var name) if 1 capturing group exists?
                    # Yes, findall returns list of groups.
                    # Since we have one capturing group ([A-Za-z0-9_]+), it returns strings.
                    vars_found.add(match)
            elif isinstance(val, dict):
                for v in val.values():
                    scan_value(v)
            elif isinstance(val, list):
                for v in val:
                    scan_value(v)

        for val in template.attributes.values():
            scan_value(val)

        # Also scan type_value if it's a string
        if isinstance(template.type_value, str):
            scan_value(template.type_value)

        # Also scan tags?? Tags are list of strings.
        if template.tags:
            scan_value(template.tags)

        return sorted(list(vars_found))

    def apply_template(
        self,
        target: Union[Entity, Event],
        template: FastInjectTemplate,
        overwrite: bool = False,
        variables: Dict[str, str] = None,
    ) -> None:
        """Apply tags and attributes to a target object.
        NOTE: This modifies the object in memory. Database save must be called
        separately.

        Args:
            target: The Entity or Event to modify.
            template: The template to apply.
            overwrite: If True, existing attribute keys are overwritten.
            variables: Dict of variable names to replacement values.

        """
        logger.info(
            f"Applying template '{template.name}' to target '{target.name if hasattr(target, 'name') else 'Unknown'}'"
        )
        logger.debug(f"Variables provided: {variables}")
        vars_map = variables or {}

        # Helper to resolve variables
        def resolve_vars(val: Any) -> Any:
            if isinstance(val, str):
                # We need to replace {{VAR}} AND {{VAR:Options}} with the value.
                # Since simple .replace() won't match the variable options,
                # we should use regex sub.

                pattern = re.compile(r"\{\{([A-Za-z0-9_]+)(?::[^}]+)?\}\}")

                def replacer(match: re.Match) -> str:
                    var_name = match.group(1)
                    return str(vars_map.get(var_name, match.group(0)))

                return pattern.sub(replacer, val)
            elif isinstance(val, list):
                return [resolve_vars(v) for v in val]
            elif isinstance(val, dict):
                return {k: resolve_vars(v) for k, v in val.items()}
            return val

        # 1. Apply Tags (Merge sets)
        if template.tags:
            current_tags = set(target.tags)
            new_tags = set(template.tags)
            target.tags = list(current_tags | new_tags)

        # 2. Apply Attributes
        for key, raw_val in template.attributes.items():
            # Resolve variables first
            final_val = resolve_vars(raw_val)

            # Check existence
            if key in target.attributes and not overwrite:
                # Conflict - skip
                continue

            target.attributes[key] = final_val

        # 3. Apply Type
        if template.type_value and hasattr(target, "type"):
            target.type = resolve_vars(template.type_value)
