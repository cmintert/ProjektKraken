"""Summary Data Module.

Defines data structure for storing AI-generated summaries with metadata.
"""

from dataclasses import dataclass, asdict
from typing import Optional, Any, Dict
import time


@dataclass
class SummaryData:
    """Data structure for storing item summaries and metadata."""

    text: str
    hash: str
    timestamp: float
    model: str
    detail_level: str = "standard"

    def to_dict(self) -> Dict[str, Any]:
        """Converts to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation of the summary data.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SummaryData":
        """Creates SummaryData from a dictionary.

        Args:
            data: Dictionary containing summary data fields.

        Returns:
            SummaryData: New instance populated with the provided data.
        """
        return cls(**data)
