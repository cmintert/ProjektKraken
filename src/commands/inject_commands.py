"""Inject Template Command Module.

Handles application of Fast Inject templates via the Command pattern, supporting
Undo/Redo operations.
"""

import copy
from typing import Dict, Union

from src.commands.base_command import BaseCommand, CommandResult
from src.core.entities import Entity
from src.core.events import Event
from src.core.fast_inject import FastInjectManager, FastInjectTemplate
from src.services.db_service import DatabaseService


class InjectTemplateCommand(BaseCommand):
    """Applies a FastInjectTemplate to an Entity or Event.

    Supports Undo by restoring the previous state of modified attributes/tags.
    """

    def __init__(
        self,
        target: Union[Entity, Event],
        template: FastInjectTemplate,
        manager: FastInjectManager,
        overwrite: bool = False,
        variables: Dict[str, str] = None,
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
        self._previous_tags = []
        self._previous_attributes = {}
        self._previous_type = None
        # We only need to backup attributes that are going to be changed or added
        # But for simplicity and robustness, creating a snapshot of attributes
        # that overlap with the template + all tags is safer.

        self._target_id = target.id
        self._target_type_str = "entity" if isinstance(target, Entity) else "event"

    def execute(self, db_service: DatabaseService) -> Union[bool, CommandResult]:
        """Executes the injection.

        Args:
            db_service: Database service (needed for saving the Modified target).

        Returns:
            CommandResult: Success or failure.
        """
        try:
            # 1. Snapshot State for Undo
            self._previous_tags = copy.deepcopy(self.target.tags)
            self._previous_type = self.target.type

            # Smart snapshot: only backup attributes that might be touched
            # However, since 'overwrite' logic is inside manager,
            # we can just blindly backup keys present in template.
            self._previous_attributes = {}
            for key in self.template.attributes.keys():
                if key in self.target.attributes:
                    self._previous_attributes[key] = copy.deepcopy(
                        self.target.attributes[key]
                    )

            # 2. Apply Template (In Memory)
            # using manager to reuse variable resolution business logic
            self.manager.apply_template(
                self.target,
                self.template,
                overwrite=self.overwrite,
                variables=self.variables,
            )

            # 3. Persist Changes
            if isinstance(self.target, Entity):
                db_service.update_entity(self.target)
            elif isinstance(self.target, Event):
                db_service.update_event(self.target)

            self._is_executed = True

            return CommandResult(
                success=True,
                message=(
                    f"Applied template '{self.template.name}' to {self.target.name}"
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
            # 1. Restore Tags
            self.target.tags = self._previous_tags

            if self._previous_type is not None:
                self.target.type = self._previous_type

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
                    self.target.attributes[key] = self._previous_attributes[key]

            for key in keys_to_remove:
                self.target.attributes.pop(key, None)

            # 3. Persist Reversion
            if isinstance(self.target, Entity):
                db_service.update_entity(self.target)
            elif isinstance(self.target, Event):
                db_service.update_event(self.target)

            self._is_executed = False

        except Exception as e:
            # Log error but can't really fail an undo gracefully
            print(f"Undo failed: {e}")
