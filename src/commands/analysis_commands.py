"""Analysis commands for Tier 1 features.

These commands are read-only (no mutations, no undo history). They delegate
work to service-layer analyzers and return reports via :class:`CommandResult`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.commands.base_command import BaseCommand, CommandResult
from src.services.intelligence_analyzer import IntelligenceAnalyzer
from src.services.temporal_analyzer import TemporalAnalyzer
from src.services.world_validator import WorldValidator

if TYPE_CHECKING:
    from src.services.db_service import DatabaseService


class ReadOnlyAnalysisCommand(BaseCommand):
    """Base for analysis commands that perform no mutations.

    Overrides :attr:`has_history` to ``False`` and provides a no-op
    :meth:`undo` so concrete subclasses only need to implement
    :meth:`execute`, :meth:`to_dict`, and :meth:`from_dict`.
    """

    @property
    def has_history(self) -> bool:
        """Return False — read-only commands are never added to undo history.

        Returns:
            bool: Always False.
        """
        return False

    def undo(self, db_service: DatabaseService) -> None:
        """No-op — read-only commands make no changes to undo.

        Args:
            db_service: Unused.
        """


class ValidateWorldCommand(ReadOnlyAnalysisCommand):
    """Runs the full world consistency and completeness validation.

    The resulting :class:`~src.core.analysis.WorldValidationReport` is stored
    in ``result.data["report"]`` on success.
    """

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Run world validation and return a report.

        Args:
            db_service: A connected
                :class:`~src.services.db_service.DatabaseService` instance.

        Returns:
            CommandResult: ``success=True`` with ``data["report"]`` set to the
            :class:`~src.core.analysis.WorldValidationReport`, or
            ``success=False`` with an error message on failure.
        """
        try:
            validator = WorldValidator(db_service)
            report = validator.validate()
            return CommandResult(
                success=True,
                data={"report": report},
            )
        except Exception as exc:
            return CommandResult(
                success=False,
                errors={"validation": str(exc)},
            )

    def to_dict(self) -> dict:
        """Serialise the command to a plain dictionary.

        Returns:
            dict: Contains ``command_type`` key only (no mutable state).
        """
        return {"command_type": "ValidateWorldCommand"}

    @classmethod
    def from_dict(cls, data: dict) -> ValidateWorldCommand:
        """Deserialise a ValidateWorldCommand from a dictionary.

        Args:
            data: Dictionary produced by :meth:`to_dict`.

        Returns:
            ValidateWorldCommand: A fresh instance.
        """
        return cls()


class AnalyzeTemporalCommand(ReadOnlyAnalysisCommand):
    """Runs the full temporal analysis (gaps, conflicts, lifespans).

    The resulting :class:`~src.core.analysis.TemporalAnalysisReport` is
    stored in ``result.data["report"]`` on success.
    """

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Run temporal analysis and return a report.

        Args:
            db_service: A connected
                :class:`~src.services.db_service.DatabaseService` instance.

        Returns:
            CommandResult: ``success=True`` with ``data["report"]`` set to the
            :class:`~src.core.analysis.TemporalAnalysisReport`, or
            ``success=False`` with an error message on failure.
        """
        try:
            analyzer = TemporalAnalyzer(db_service)
            report = analyzer.analyze()
            return CommandResult(
                success=True,
                data={"report": report},
            )
        except Exception as exc:
            return CommandResult(
                success=False,
                errors={"temporal_analysis": str(exc)},
            )

    def to_dict(self) -> dict:
        """Serialise the command to a plain dictionary.

        Returns:
            dict: Contains ``command_type`` key only (no mutable state).
        """
        return {"command_type": "AnalyzeTemporalCommand"}

    @classmethod
    def from_dict(cls, data: dict) -> AnalyzeTemporalCommand:
        """Deserialise an AnalyzeTemporalCommand from a dictionary.

        Args:
            data: Dictionary produced by :meth:`to_dict`.

        Returns:
            AnalyzeTemporalCommand: A fresh instance.
        """
        return cls()


class RunIntelligenceAnalysisCommand(ReadOnlyAnalysisCommand):
    """Runs the AI-powered intelligence analysis (plot holes, relations, lore).

    The resulting :class:`~src.core.analysis.IntelligenceReport` is stored in
    ``result.data["report"]`` on success.
    """

    def __init__(self, analysis_type: str = "all") -> None:
        """Initialise the command with the requested analysis scope.

        Args:
            analysis_type: Scope for the intelligence analysis.  Defaults to
                ``"all"``.
        """
        super().__init__()
        self.analysis_type = analysis_type

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Run intelligence analysis and return a report.

        Args:
            db_service: A connected
                :class:`~src.services.db_service.DatabaseService` instance.

        Returns:
            CommandResult: ``success=True`` with ``data["report"]`` set to the
            :class:`~src.core.analysis.IntelligenceReport`, or
            ``success=False`` with an error message on failure.
        """
        try:
            analyzer = IntelligenceAnalyzer(db_service)
            report = analyzer.analyze(self.analysis_type)
            return CommandResult(
                success=True,
                data={"report": report},
            )
        except Exception as exc:
            return CommandResult(
                success=False,
                errors={"intelligence_analysis": str(exc)},
            )

    def to_dict(self) -> dict:
        """Serialise the command to a plain dictionary.

        Returns:
            dict: Contains ``command_type`` and ``analysis_type`` keys.
        """
        return {
            "command_type": "RunIntelligenceAnalysisCommand",
            "analysis_type": self.analysis_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RunIntelligenceAnalysisCommand:
        """Deserialise a RunIntelligenceAnalysisCommand from a dictionary.

        Args:
            data: Dictionary produced by :meth:`to_dict`.

        Returns:
            RunIntelligenceAnalysisCommand: A fresh instance with the stored
            ``analysis_type``.
        """
        return cls(analysis_type=data.get("analysis_type", "all"))
