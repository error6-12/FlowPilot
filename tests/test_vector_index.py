from services.vector_index import VersionedVectorIndex


def test_versioned_index_supports_incremental_upsert_and_delete():
    index = VersionedVectorIndex()
    index.build([(10, [1.0, 0.0]), (20, [0.0, 1.0])])
    assert index.status()["version"] == 1
    assert index.search([1.0, 0.0], 2)[1][0] == 10

    index.upsert(30, [0.9, 0.1])
    assert index.status()["version"] == 2
    assert index.status()["document_count"] == 3
    assert 30 in index.search([1.0, 0.0], 3)[1]

    assert index.delete(10) is True
    assert index.status()["version"] == 3
    assert 10 not in index.search([1.0, 0.0], 3)[1]


def test_upsert_replaces_existing_vector_without_duplicate_id():
    index = VersionedVectorIndex()
    index.build([(7, [1.0, 0.0])])
    index.upsert(7, [0.0, 1.0])
    assert index.status()["document_count"] == 1
    assert index.search([0.0, 1.0], 1)[1] == [7]


def test_index_rejects_embedding_dimension_mismatch():
    index = VersionedVectorIndex()
    index.build([(1, [1.0, 0.0])])
    try:
        index.upsert(2, [1.0, 0.0, 0.0])
    except ValueError as error:
        assert "dimension mismatch" in str(error)
    else:
        raise AssertionError("dimension mismatch should fail")
