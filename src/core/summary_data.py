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
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SummaryData":
        return cls(**data)
