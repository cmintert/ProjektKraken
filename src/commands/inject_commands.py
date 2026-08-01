"""Inject Template Command Module.

Handles application of Fast Inject templates via the Command pattern, supporting
Undo/Redo operations.
"""

import copy
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from src.commands.base_command import BaseCommand, CommandResult
from src.core.entities import Entity
from src.core.events import Event
from src.core.fast_inject import FastInjectManager, FastInjectTemplate
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class InjectTemplateCommand(BaseCommand):
    """Applies a FastInjectTemplate to an Entity or Event.

    Supports Undo by restoring the previous state of modified attributes/tags.
    """

    def __init__(
        self,
        target: Optional[Union[Entity, Event]],
        template: FastInjectTemplate,
        manager: Optional[FastInjectManager],
        overwrite: bool = False,
        variables: Optional[Dict[str, str]] = None,
        target_id: str = "",
        target_type: str = "",
    ) -> None:
        """Initialize the command.

        Args:
            target: The Entity or Event to modify.
            template: The template to apply.
            manager: FastInjectManager instance (for variable resolution logic,
                     though primarily used for core logic application).
                     Actually we delegate logic to manager, but we track
                     state diffs here.
            overwrite: Whether to overwrite existing attributes.
            variables: Variable replacement map.

        """
        super().__init__()
        self.target = target
        self.template = template
        self.manager = manager
        self.overwrite = overwrite
        self.variables = variables or {}

        # Undo State
        self._previous_tags: List[str] = []
        self._previous_attributes: Dict[str, object] = {}
        self._previous_type: Optional[str] = None
        # We only need to backup attributes that are going to be changed or added
        # But for simplicity and robustness, creating a snapshot of attributes
        # that overlap with the template + all tags is safer.

        if target is not None:
            self._target_id = target.id
            self._target_type_str = (
                "entity" if isinstance(target, Entity) else "event"
            )
        else:
            self._target_id = target_id
            self._target_type_str = target_type

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the injection.

        Args:
            db_service: Database service (needed for saving the Modified target).

        Returns:
            CommandResult: Success or failure.

        """
        try:
            target = (
                db_service.get_entity(self._target_id)
                if self._target_type_str == "entity"
                else db_service.get_event(self._target_id)
            )
            if target is None:
                raise ValueError(f"Target not found: {self._target_id}")
            self.target = target
            manager = self.manager or FastInjectManager(
                Path(db_service.get_db_file_path()).parent
            )
            # 1. Snapshot State for Undo
            self._previous_tags = copy.deepcopy(target.tags)
            self._previous_type = target.type

            # Smart snapshot: only backup attributes that might be touched
            # However, since 'overwrite' logic is inside manager,
            # we can just blindly backup keys present in template.
            self._previous_attributes = {}
            for key in self.template.attributes.keys():
                if key in target.attributes:
                    self._previous_attributes[key] = copy.deepcopy(
                        target.attributes[key]
                    )

            # 2. Apply Template (In Memory)
            # using manager to reuse variable resolution business logic
            manager.apply_template(
                target,
                self.template,
                overwrite=self.overwrite,
                variables=self.variables,
            )

            # 3. Persist Changes
            if isinstance(target, Entity):
                db_service.insert_entity(target)
            elif isinstance(target, Event):
                db_service.insert_event(target)

            self._is_executed = True

            return CommandResult(
                success=True,
                message=(
                    f"Applied template '{self.template.name}' to {target.name}"
                ),
                command_name="InjectTemplateCommand",
            )

        except Exception as e:
            return CommandResult(
                success=False, message=str(e), command_name="InjectTemplateCommand"
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the injection.

        Args:
            db_service: Database service.

        """
        if not self._is_executed:
            return

        try:
            target = (
                db_service.get_entity(self._target_id)
                if self._target_type_str == "entity"
                else db_service.get_event(self._target_id)
            )
            if target is None:
                raise ValueError(f"Target not found: {self._target_id}")
            self.target = target
            # 1. Restore Tags
            target.tags = self._previous_tags

            if self._previous_type is not None:
                target.type = self._previous_type

            # 2. Restore Attributes
            # We need to act carefully:
            # A) If key was in _previous_attributes, restore its value.
            # B) If key was NOT in _previous_attributes (it was added new), remove it.

            keys_to_remove = []

            # Identify keys added by template
            for key in self.template.attributes.keys():
                if key not in self._previous_attributes:
                    keys_to_remove.append(key)
                else:
                    target.attributes[key] = self._previous_attributes[key]

            for key in keys_to_remove:
                target.attributes.pop(key, None)

            # 3. Persist Reversion
            if isinstance(target, Entity):
                db_service.insert_entity(target)
            elif isinstance(target, Event):
                db_service.insert_event(target)

            self._is_executed = False

        except Exception as e:
            # Log error but can't really fail an undo gracefully
            logger.error(f"Undo failed for InjectTemplateCommand: {e}", exc_info=True)

    def to_dict(self) -> Dict:
        """Serialize command to dictionary.

        Returns:
            Dict: Dictionary containing command data for reconstruction.

        """
        return {
            "target_id": self._target_id,
            "target_type": self._target_type_str,
            "template": self.template.to_dict(),
            "overwrite": self.overwrite,
            "variables": self.variables,
            "previous_tags": self._previous_tags,
            "previous_attributes": self._previous_attributes,
            "previous_type": self._previous_type,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "InjectTemplateCommand":
        """Deserialize a worker-safe template application command.

        Args:
            data: Dictionary containing command data.

        Returns:
            Reconstructed command using canonical worker-side target loading.

        """
        command = cls(
            target=None,
            template=FastInjectTemplate.from_dict(data["template"]),
            manager=None,
            overwrite=bool(data.get("overwrite", False)),
            variables=dict(data.get("variables", {})),
            target_id=str(data["target_id"]),
            target_type=str(data["target_type"]),
        )
        command._previous_tags = list(data.get("previous_tags", []))
        command._previous_attributes = dict(
            data.get("previous_attributes", {})
        )
        command._previous_type = data.get("previous_type")
        command._is_executed = bool(data.get("is_executed", False))
        return command
