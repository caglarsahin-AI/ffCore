"""04b-1: the additive migration (`chunks.sparse`, branch label 04b on the single head) and the
optional, additive VectorStore methods (C5: "unsupported" by default)."""

import asyncio
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from ffcore.knowledge.vectorstore.base import VectorStore, VectorStoreError
from ffcore.models.knowledge import Chunk

BACKEND = Path(__file__).resolve().parents[2]


def _scripts() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_04b_1_migration_is_the_single_head_on_05b():
    scripts = _scripts()
    assert scripts.get_heads() == ["04b_0001"]
    revision = scripts.get_revision("04b_0001")
    assert revision.down_revision == "05b_0001"
    # Alembic spreads labels along the chain; the label this file declares is its own.
    assert revision.module.branch_labels == ("04b",)


def test_04b_1_chunk_model_has_nullable_sparse():
    column = Chunk.__table__.c.sparse
    assert column.nullable and column.type.__class__.__name__ == "JSONB"


class _Minimal(VectorStore):
    name = "minimal"

    async def ensure_collection(self, kb_id, dim): ...

    async def upsert(self, chunks): ...

    async def search(self, kb_id, query, filters, top_k): ...

    async def delete_by_document(self, document_id): ...

    async def drop_collection(self, kb_id): ...


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.count(uuid.uuid4()),
        lambda s: s.fetch_vectors(uuid.uuid4(), [uuid.uuid4()]),
    ],
)
def test_04b_1_new_store_methods_default_to_unsupported(call):
    with pytest.raises(VectorStoreError) as caught:
        asyncio.run(call(_Minimal()))
    assert caught.value.code == "unsupported"
