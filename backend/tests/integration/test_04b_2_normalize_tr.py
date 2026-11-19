"""04b-2 slice 3, D3 / brief acceptance K1: TEXT_NORMALIZE_TR cannot be switched on for queries
before silver is rebuilt. While an indexed document carries another normalizer_config_id the
search answers 409 `normalizer_config_mismatch` (no mixed-form results); a silver reindex under
the new setting writes the new id and the folded text, and the search works again."""

import asyncio
import uuid
from pathlib import Path

from ffcore.core.config import get_settings
from ffcore.knowledge import ingest
from ffcore.knowledge.vectorstore.pgvector import PgVectorStore
from tests.converters import convert_without_weights
from tests.integration import test_04a_api as kb_api
from tests.integration.test_04a_api import PROSE, create_kb, process_all, search, upload

queue = kb_api.queue
settings = kb_api.settings
world = kb_api.world

BODY = PROSE * 6 + "Şirketin kâr payı hâlâ ödenmedi. "


def _switch_on(app, settings):
    on = settings.model_copy(update={"text_normalize_tr": True})
    app.dependency_overrides[get_settings] = lambda: on
    return on


def test_04b_2_d3_switching_on_needs_silver_rebuild(app, world, settings, queue, pg):
    kb = create_kb(world)
    item = upload(world, world["admin"], kb["id"], "kar.md", BODY).json()["data"][0]
    process_all(settings, queue)
    doc_id = item["document"]["id"]
    assert search(world["admin"], world, kb["id"], "kâr payı").status_code == 200

    on = _switch_on(app, settings)
    refused = search(world["admin"], world, kb["id"], "kâr payı")
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "normalizer_config_mismatch"

    asyncio.run(
        ingest.reindex_silver(
            uuid.UUID(kb["id"]),
            full=True,
            settings=on,
            store=PgVectorStore(),
            embed_client=ingest.LocalEmbedClient(on),
            convert=convert_without_weights,
        )
    )
    normalizer_id, silver = pg.execute(
        "SELECT normalizer_config_id, silver_path FROM documents WHERE id = %s", (doc_id,)
    ).fetchone()
    assert normalizer_id == "format-v1+tr-a1"
    text = Path(silver).read_text(encoding="utf-8")
    assert "kar payı hala ödenmedi" in text and "normalizer_config_id: format-v1+tr-a1" in text

    answer = search(world["admin"], world, kb["id"], "kâr payı")
    assert answer.status_code == 200, answer.text
    assert answer.json()["normalizer_config_id"] == "format-v1+tr-a1"
    assert answer.json()["hits"]
    (logged,) = pg.execute(
        "SELECT normalizer_config_id FROM kb_queries WHERE id = %s", (answer.json()["query_id"],)
    ).fetchone()
    assert logged == "format-v1+tr-a1"


def test_04b_2_d3_new_kb_records_the_setting(app, world, settings, queue):
    _switch_on(app, settings)
    kb = create_kb(world, key="yeni")
    assert kb["normalizer_config_id"] == "format-v1+tr-a1"
