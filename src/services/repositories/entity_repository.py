"""
Entity Repository Module.

Handles CRUD operations for Entity entities in the database.
"""

import logging
from typing import List, Optional

from src.core.entities import Entity
from src.services.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class EntityRepository(BaseRepository):
    """
    Repository for Entity entities.
    
    Provides specialized methods for creating, reading, updating,
    and deleting entities from the database.
    """

    def insert(self, entity: Entity) -> None:
        """
        Insert a new entity or update an existing one (Upsert).
        
        Args:
            entity: The entity domain object to persist.
            
        Raises:
            sqlite3.Error: If the database operation fails.
        """
        sql = """
            INSERT INTO entities (id, type, name, description,
                                  attributes, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type=excluded.type,
                name=excluded.name,
                description=excluded.description,
                attributes=excluded.attributes,
                modified_at=excluded.modified_at;
        """
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    entity.id,
                    entity.type,
                    entity.name,
                    entity.description,
                    self._serialize_json(entity.attributes),
                    entity.created_at,
                    entity.modified_at,
                ),
            )

    def get(self, entity_id: str) -> Optional[Entity]:
        """
        Retrieve a single entity by its UUID.
        
        Args:
            entity_id: The unique identifier of the entity.
            
        Returns:
            The Entity object if found, else None.
        """
        sql = "SELECT * FROM entities WHERE id = ?"
        
        if not self._connection:
            raise RuntimeError("Database connection not initialized")
        
        cursor = self._connection.execute(sql, (entity_id,))
        row = cursor.fetchone()
        
        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            return Entity.from_dict(data)
        return None

    def get_all(self) -> List[Entity]:
        """
        Retrieve all entities from the database, sorted by name.
        
        Returns:
            List of all Entity objects in the database.
        """
        sql = "SELECT * FROM entities ORDER BY name ASC"
        
        if not self._connection:
            raise RuntimeError("Database connection not initialized")
        
        cursor = self._connection.execute(sql)
        entities = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            entities.append(Entity.from_dict(data))
        return entities

    def delete(self, entity_id: str) -> None:
        """
        Delete an entity permanently.
        
        Args:
            entity_id: The unique identifier of the entity to delete.
            
        Raises:
            sqlite3.Error: If the database operation fails.
        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))

    def insert_bulk(self, entities: List[Entity]) -> None:
        """
        Insert multiple entities in a single transaction.
        
        Args:
            entities: List of entity objects to persist.
            
        Raises:
            sqlite3.Error: If the database operation fails.
        """
        sql = """
            INSERT INTO entities (id, type, name, description,
                                  attributes, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type=excluded.type,
                name=excluded.name,
                description=excluded.description,
                attributes=excluded.attributes,
                modified_at=excluded.modified_at;
        """
        
        data = [
            (
                entity.id,
                entity.type,
                entity.name,
                entity.description,
                self._serialize_json(entity.attributes),
                entity.created_at,
                entity.modified_at,
            )
            for entity in entities
        ]
        
        with self.transaction() as conn:
            conn.executemany(sql, data)

    def get_by_type(self, entity_type: str) -> List[Entity]:
        """
        Retrieve entities by type.
        
        Args:
            entity_type: The type of entities to retrieve.
            
        Returns:
            List of Entity objects of the specified type.
        """
        sql = "SELECT * FROM entities WHERE type = ? ORDER BY name ASC"
        
        if not self._connection:
            raise RuntimeError("Database connection not initialized")
        
        cursor = self._connection.execute(sql, (entity_type,))
        entities = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            entities.append(Entity.from_dict(data))
        return entities

    def search_by_name(self, search_term: str) -> List[Entity]:
        """
        Search entities by name (case-insensitive partial match).
        
        Args:
            search_term: The search term to match against entity names.
            
        Returns:
            List of Entity objects matching the search term.
        """
        sql = """
            SELECT * FROM entities 
            WHERE name LIKE ? 
            ORDER BY name ASC
        """
        
        if not self._connection:
            raise RuntimeError("Database connection not initialized")
        
        search_pattern = f"%{search_term}%"
        cursor = self._connection.execute(sql, (search_pattern,))
        entities = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            entities.append(Entity.from_dict(data))
        return entities
