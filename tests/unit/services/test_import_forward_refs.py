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


def test_cross_batch_forward_ref(db_service):
    """Pass 4 retry resolves relations whose target was created in a prior batch."""
    import_service = ImportService(db_service)

    # Batch 1: create Entity A only
    batch1 = {"entities": [{"name": "Entity Alpha", "type": "character"}]}
    result1 = import_service.import_batch(batch1)
    assert result1.success
    assert len(result1.created_entities) == 1

    # Batch 2: create Entity Beta with a relation pointing to Alpha (already in DB)
    batch2 = {
        "entities": [
            {
                "name": "Entity Beta",
                "type": "character",
                "relations": [
                    {"target_name": "Entity Alpha", "rel_type": "knows"}
                ],
            }
        ]
    }
    result2 = import_service.import_batch(batch2)

    assert result2.success
    assert len(result2.created_entities) == 1
    # Pass 4 should have resolved and created the relation
    assert len(result2.created_relations) == 1

    beta = db_service.get_entity(result2.created_entities[0])
    alpha_rels = db_service.get_relations(beta.id)
    assert len(alpha_rels) == 1
    assert alpha_rels[0]["rel_type"] == "knows"


def test_unresolvable_relation_warns_after_retry(db_service):
    """A relation pointing to a nonexistent entity should warn after Pass 4 retry."""
    import_service = ImportService(db_service)

    data = {
        "entities": [
            {
                "name": "Lone Entity",
                "type": "character",
                "relations": [
                    {"target_name": "Ghost Entity", "rel_type": "linked_to"}
                ],
            }
        ]
    }
    result = import_service.import_batch(data)

    assert result.success
    assert len(result.created_entities) == 1
    assert len(result.created_relations) == 0
    # Should have a warning about the unresolved forward reference
    assert any("Ghost Entity" in w or "unresolved" in w.lower() for w in result.warnings)
