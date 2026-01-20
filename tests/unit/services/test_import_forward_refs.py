from src.services.import_service import ImportService


def test_cyclic_dependency_import(db_service):
    """Test importing two entities that reference each other (forward ref)."""
    # Setup
    import_service = ImportService(db_service)

    data = {
        "entities": [
            {
                "name": "Entity A",
                "type": "character",
                "relations": [{"target_name": "Entity B", "rel_type": "references"}],
            },
            {
                "name": "Entity B",
                "type": "character",
                "relations": [
                    {"target_name": "Entity A", "rel_type": "references_back"}
                ],
            },
        ]
    }

    # Execute
    result = import_service.import_batch(data)

    # Verify
    assert result.success is True
    assert len(result.created_entities) == 2

    # Verify specific connections
    # We don't have get_entity_by_name, so we use IDs from result or search
    assert len(result.created_entities) == 2

    entities = [db_service.get_entity(eid) for eid in result.created_entities]
    entity_a = next(e for e in entities if e.name == "Entity A")
    entity_b = next(e for e in entities if e.name == "Entity B")

    assert entity_a is not None
    assert entity_b is not None

    rels_from_a = db_service.get_relations(entity_a.id)
    rels_from_b = db_service.get_relations(entity_b.id)

    # In single pass, A->B fails because B exists after A in list
    assert len(rels_from_a) == 1
    assert rels_from_a[0]["target_id"] == entity_b.id

    assert len(rels_from_b) == 1
    assert rels_from_b[0]["target_id"] == entity_a.id
