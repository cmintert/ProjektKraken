"""
Repository Module.

Provides specialized repository classes for different domain entities.
Each repository encapsulates CRUD operations for a specific entity type.
"""

from src.services.repositories.attachment_repository import AttachmentRepository
from src.services.repositories.calendar_repository import CalendarRepository
from src.services.repositories.entity_repository import EntityRepository
from src.services.repositories.event_repository import EventRepository
from src.services.repositories.map_repository import MapRepository
from src.services.repositories.relation_repository import RelationRepository

__all__ = [
    "EventRepository",
    "EntityRepository",
    "RelationRepository",
    "MapRepository",
    "CalendarRepository",
    "AttachmentRepository",
]
