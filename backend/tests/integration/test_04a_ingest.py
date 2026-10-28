"""04a slice 6: the ingest pipeline raw → silver → gold against the real database (fake models)."""

import asyncio
import uuid
from pathlib import Path

import pytest

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge import ingest
from ffcore.knowledge.embed import FakeEmbedder
from ffcore.knowledge.vectorstore.pgvector import PgVectorStore
from tests.dummy import EMBED_DIM, SETTINGS_03A

PROSE = (
    "Bu sözleşme kapsamında yüklenici bakım hizmetini aylık olarak verir ve her ziyaret için "
    "bir rapor düzenler. Taraflar arasında çıkan anlaşmazlıklar önce uzlaşma ile çözülür. "
)
SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples" / "contracts"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token="dummy-not-secret-service-token-0123456789",
        obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
        fake_embed=True,
        knowledge_storage_dir=str(tmp_path / "storage"),
        convert_timeout_seconds=120,
        **SETTINGS_03A,
    )


@pytest.fixture(autouse=True)
def configured_db(database_url):
    db.configure(database_url, pooled=False)
    yield
    db.reset()


class CountingEmbedder(FakeEmbedder):
    def __init__(self):
        super().__init__("BAAI/bge-m3", EMBED_DIM)
        self.texts = 0

    def encode(self, texts):
        self.texts += len(texts)
        return super().encode(texts)


def run(coro):
    return asyncio.run(coro)


def make_kb(pg, project_id) -> uuid.UUID:
    kb_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO knowledge_bases (id, project_id, key, name, embed_model, embed_dim,"
        " chunk_size, chunk_overlap, hybrid, rerank, rerank_model, default_top_k,"
        " normalizer_config_id, created_by) VALUES (%s, %s, %s, 'Sözleşmeler', 'BAAI/bge-m3',"
        " %s, 400, 0, true, true, 'BAAI/bge-reranker-v2-m3', 5, 'format-v1', 'test')",
        (kb_id, project_id, f"kb-{kb_id.hex[:8]}", EMBED_DIM),
    )
    return kb_id


def upload(settings, kb_id, filename, data: bytes, acl_roles=("analyst",)):
    async def go():
        async with db.session_scope() as session:
            document, outcome = await ingest.register_upload(
                session,
                kb_id,
                filename=filename,
                data=data,
                acl_roles=list(acl_roles),
                acl_users=[],
                created_by="test",
                settings=settings,
            )
            await session.commit()
            return document.id, outcome

    return run(go())


def process(settings, document_id, embedder=None, convert=ingest.convert_inline):
    # Inline conversion keeps the suite fast; the bounded worker path has its own test below.
    return run(
        ingest.ingest_document(
            document_id,
            settings=settings,
            store=PgVectorStore(),
            embed_client=ingest.LocalEmbedClient(settings, embedder),
            convert=convert,
        )
    )


def doc_row(pg, document_id):
    return pg.execute(
        "SELECT status, gate0_status, gate0_reason, gate1_status, gate1_reason, gate2_status,"
        " gate2_reason, duplicate_of, convert_engine, silver_path, version, error,"
        " normalizer_config_id FROM documents WHERE id = %s",
        (document_id,),
    ).fetchone()


def chunk_rows(pg, document_id):
    return pg.execute(
        "SELECT text, breadcrumb, chunk_status, chunk_reason, embedding IS NOT NULL,"
        " char_count FROM chunks WHERE document_id = %s ORDER BY ordinal",
        (document_id,),
    ).fetchall()


def markdown(*sections):
    return "\n\n".join(f"## Madde {i}\n\n{PROSE * 6}" for i in sections).encode()


def test_04a_ingest_markdown_end_to_end(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    doc_id, outcome = upload(settings, kb_id, "bakim.md", markdown(1, 2, 3))
    assert outcome == "created"
    report = process(settings, doc_id)
    row = doc_row(pg, doc_id)
    assert row[0] == "indexed" and row[1] == row[3] == row[5] == "ok"
    assert row[8].startswith("docling@") and Path(row[9]).exists()
    assert row[12] == "format-v1"
    chunks = chunk_rows(pg, doc_id)
    assert chunks and all(c[4] for c in chunks)  # every chunk has a vector
    assert report.embedded == len(chunks) and report.reused == 0


def test_04a_11a_breadcrumb_starts_every_embedded_text(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    doc_id, _ = upload(settings, kb_id, "bakim.md", markdown(1, 2))
    process(settings, doc_id)
    for text, breadcrumb, *_ in chunk_rows(pg, doc_id):
        assert breadcrumb.startswith("Sözleşmeler › bakim.md")
        assert text.startswith(breadcrumb + "\n\n")


def test_04a_4_reupload_bumps_version_without_new_record(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    first, _ = upload(settings, kb_id, "a.md", markdown(1))
    same, outcome = upload(settings, kb_id, "a.md", markdown(1))
    changed, outcome2 = upload(settings, kb_id, "a.md", markdown(1, 2))
    assert first == same == changed and (outcome, outcome2) == ("unchanged", "new_version")
    assert doc_row(pg, first)[10] == 3


def test_04a_8a_navigation_page_is_skipped_boilerplate(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    nav = "\n".join(f"- [Alt sayfa {i}](https://wiki.example.test/p/{i})" for i in range(40))
    doc_id, _ = upload(settings, kb_id, "ana-sayfa.md", nav.encode())
    process(settings, doc_id)
    row = doc_row(pg, doc_id)
    assert row[0] == "skipped" and (row[5], row[6]) == ("skipped", "boilerplate")
    assert chunk_rows(pg, doc_id) == []


def test_04a_8c_duplicate_owner_is_stable(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    owner, _ = upload(settings, kb_id, "asil.md", markdown(1, 2))
    copy, _ = upload(settings, kb_id, "kopya.md", markdown(1, 2))
    process(settings, owner)
    process(settings, copy)
    assert doc_row(pg, copy)[4] == f"duplicate_of:{owner}"
    # A later run of the owner does not move ownership to the copy.
    process(settings, owner)
    process(settings, copy)
    assert doc_row(pg, owner)[0] == "indexed"
    assert doc_row(pg, copy)[7] == owner


def test_04a_8b_log_attachment_is_data_dump_document_indexed(pg, make_project, settings, tmp_path):
    kb_id = make_kb(pg, make_project())
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "rapor.md").write_bytes(markdown(1, 2))
    log = "\n".join(f"2026-10-01 10:00:{i % 60:02d} INFO job={i} ok" for i in range(10_000))
    (raw / "job.log").write_text(log, encoding="utf-8")
    doc_id = run(
        ingest.ingest_from_raw(
            str(raw / "rapor.md"),
            {"kb_id": str(kb_id), "filename": "rapor.md", "attachments": ["job.log"]},
            {"roles": ["analyst"], "users": []},
            settings=settings,
            store=PgVectorStore(),
            embed_client=ingest.LocalEmbedClient(settings),
            convert=ingest.convert_inline,
        )
    )
    assert doc_row(pg, doc_id)[0] == "indexed"
    (att,) = pg.execute(
        "SELECT gate2_status, gate2_reason FROM attachments WHERE document_id = %s", (doc_id,)
    ).fetchall()
    assert att == ("skipped", "data_dump:log")
    assert not any("job=" in c[0] for c in chunk_rows(pg, doc_id))


def test_04a_8d_gate_stats_totals_equal_documents(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    for name, data in [("a.md", markdown(1)), ("b.md", b"kisa"), ("c.exe", b"MZ" + bytes(10))]:
        doc_id, _ = upload(settings, kb_id, name, data)
        process(settings, doc_id)
    rows = pg.execute(
        "SELECT gate, sum(documents) FROM ingest_gate_stats WHERE kb_id = %s GROUP BY gate",
        (kb_id,),
    ).fetchall()
    assert dict(rows) == {"gate0": 3, "gate1": 3, "gate2": 3}


def test_04a_gate0_binary_is_skipped_with_reason(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    doc_id, _ = upload(settings, kb_id, "tool.exe", b"MZ" + bytes(100))
    process(settings, doc_id)
    row = doc_row(pg, doc_id)
    assert row[0] == "skipped" and (row[1], row[2]) == ("skipped", "binary")


def test_04a_9b_undecodable_file_fails_with_code(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    doc_id, _ = upload(settings, kb_id, "bozuk.txt", b"ok\n\x81\x8d bozuk\n" + b"x" * 100)
    process(settings, doc_id)
    row = doc_row(pg, doc_id)
    assert row[0] == "failed" and row[11].startswith("encoding_undecodable")


def test_04a_10a_gold_reindex_reuses_vectors(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    doc_id, _ = upload(settings, kb_id, "a.md", markdown(1, 2, 3))
    process(settings, doc_id)
    counter = CountingEmbedder()
    report = run(
        ingest.reindex_gold(
            kb_id,
            full=True,
            settings=settings,
            store=PgVectorStore(),
            embed_client=ingest.LocalEmbedClient(settings, counter),
        )
    )
    assert counter.texts == 0 and report.reused == len(chunk_rows(pg, doc_id))
    assert report.embedded == 0


def test_04a_10b_model_change_reembeds(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    doc_id, _ = upload(settings, kb_id, "a.md", markdown(1, 2))
    process(settings, doc_id)
    other = settings.model_copy(update={"embed_model": "intfloat/multilingual-e5-large"})
    counter = CountingEmbedder()
    counter.model = other.embed_model
    report = run(
        ingest.reindex_gold(
            kb_id,
            full=True,
            settings=other,
            store=PgVectorStore(),
            embed_client=ingest.LocalEmbedClient(other, counter),
        )
    )
    assert report.reused == 0 and counter.texts == len(chunk_rows(pg, doc_id))


def test_04a_ingest_13a_contract_docx(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    name = "SZL-2025-003_temizlik-hizmet.docx"
    doc_id, _ = upload(settings, kb_id, name, (SAMPLES / name).read_bytes())
    # The worker's real path: conversion in a bounded worker process.
    process(settings, doc_id, convert=ingest.convert_bounded)
    row = doc_row(pg, doc_id)
    assert row[0] == "indexed", row
    assert any("Madde" in c[0] for c in chunk_rows(pg, doc_id))
