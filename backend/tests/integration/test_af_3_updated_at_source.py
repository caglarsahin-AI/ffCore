"""FOLLOWUP-101: a document's source date (`updated_at_source`, used by newest-first ordering)
comes from an optional upload form field, stays NULL without it (no hidden default: K-AF-0002 S1
A), can be changed by PATCH, and the C6 entry point `ingest_from_raw` writes it to the column."""

import asyncio
import uuid

from ffcore.knowledge import ingest
from ffcore.knowledge.vectorstore.pgvector import PgVectorStore
from tests.converters import convert_without_weights
from tests.integration.conftest import audit_rows
from tests.integration.test_04a_api import create_kb, kb_url, queue, settings, upload, world

__all__ = ["queue", "settings", "world"]  # fixtures used by name below

PROSE = "Bu sözleşme hizmetin süresini ve fesih koşullarını düzenler. " * 20


def _document_url(world, kb_id, doc_id):
    return f"{kb_url(world, kb_id)}/documents/{doc_id}"


def _stored(pg, doc_id):
    return pg.execute(
        "SELECT updated_at_source FROM documents WHERE id = %s", (doc_id,)
    ).fetchone()[0]


def test_af_3_upload_sets_updated_at_source(world, pg):
    kb = create_kb(world)
    dated = upload(world, world["admin"], kb["id"], "v2.md", PROSE, updated_at_source="2025-09-01")
    assert dated.status_code == 202, dated.text
    doc = dated.json()["data"][0]["document"]
    assert doc["updated_at_source"].startswith("2025-09-01")
    assert _stored(pg, doc["id"]).isoformat().startswith("2025-09-01")

    plain = upload(world, world["admin"], kb["id"], "v1.md", PROSE + "v1")
    assert plain.json()["data"][0]["document"]["updated_at_source"] is None  # no hidden default

    bad = upload(world, world["admin"], kb["id"], "x.md", PROSE + "x", updated_at_source="dün")
    assert bad.status_code == 422, bad.text


def test_af_3b_patch_updated_at_source(world, pg):
    kb = create_kb(world, key=f"kb-{uuid.uuid4().hex[:6]}")
    doc = upload(world, world["admin"], kb["id"], "a.md", PROSE).json()["data"][0]["document"]
    url = _document_url(world, kb["id"], doc["id"])

    changed = world["admin"].patch(url, json={"updated_at_source": "2025-01-15T00:00:00+00:00"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["updated_at_source"].startswith("2025-01-15")
    assert _stored(pg, doc["id"]).isoformat().startswith("2025-01-15")
    rows = audit_rows(pg, "update_document", "success", project=world["project"])
    after = rows[-1][2]
    assert after["filename"] == "***" and after["updated_at_source"].startswith("2025-01-15")

    cleared = world["admin"].patch(url, json={"updated_at_source": None})
    assert cleared.status_code == 200 and cleared.json()["updated_at_source"] is None

    read_only = world["admin_read"].patch(url, json={"updated_at_source": None})
    assert read_only.status_code == 403
    outsider = world["stranger"].patch(url, json={"updated_at_source": None})
    assert outsider.status_code == 404
    unknown = world["admin"].patch(url, json={"updated_at_sourcex": None})
    assert unknown.status_code == 422
    missing = world["admin"].patch(_document_url(world, kb["id"], uuid.uuid4()), json={})
    assert missing.status_code in (404, 422)


def test_af_3c_ingest_from_raw_writes_the_date(world, pg, settings, tmp_path):
    kb = create_kb(world, key=f"kb-{uuid.uuid4().hex[:6]}")
    raw = tmp_path / "kaynak.md"
    raw.write_bytes(PROSE.encode())

    async def go():
        return await ingest.ingest_from_raw(
            str(raw),
            {"kb_id": kb["id"], "filename": "kaynak.md", "updated_at_source": "2025-03-04"},
            {"roles": ["analyst"], "users": []},
            settings=settings,
            store=PgVectorStore(),
            embed_client=ingest.LocalEmbedClient(settings),
            convert=convert_without_weights,
        )

    doc_id = asyncio.run(go())
    assert _stored(pg, doc_id).isoformat().startswith("2025-03-04")
