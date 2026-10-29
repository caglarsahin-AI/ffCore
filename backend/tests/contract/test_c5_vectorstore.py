"""CONTRACTS C5: the VectorStore method names and parameters are frozen; drivers implement all."""

import inspect

from ffcore.knowledge.vectorstore.base import FILTER_KEYS, VectorStore
from ffcore.knowledge.vectorstore.pgvector import PgVectorStore
from ffcore.knowledge.vectorstore.qdrant import QdrantStore

SIGNATURES = {
    "ensure_collection": ["self", "kb_id", "dim"],
    "upsert": ["self", "chunks"],
    "search": ["self", "kb_id", "query", "filters", "top_k"],
    "delete_by_document": ["self", "document_id"],
    "drop_collection": ["self", "kb_id"],
}


def test_c5_vectorstore_signature():
    for name, params in SIGNATURES.items():
        assert list(inspect.signature(getattr(VectorStore, name)).parameters) == params, name


def test_c5_filter_keys():
    assert FILTER_KEYS == {"document_ids", "acl_roles", "acl_users", "metadata"}


def test_c5_drivers_implement_every_method():
    for driver in (PgVectorStore, QdrantStore):
        assert not inspect.isabstract(driver), driver
        for name, params in SIGNATURES.items():
            assert list(inspect.signature(getattr(driver, name)).parameters) == params
