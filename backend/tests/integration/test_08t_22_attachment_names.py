"""08 tam 1b r1 MAJOR-4: attachment file names are inside the personnel-data boundary.

A PRSIM attachment's shown name is `Ek <n>` (attachment row, silver heading, chunk breadcrumb);
in other sources the name goes through the text filter with `_`/`-` read as spaces. `raw_path`
stays the real file, byte for byte. Before: `Ayşe_Demir_izin.txt` reached silver, the breadcrumb
of every chunk (so the embedding and search results) unmasked.
"""

import json
from pathlib import Path

from ffcore.guardrails.findings import Finding
from ffcore.knowledge import ingest_mask
from tests.integration.test_04a_api import create_kb, queue, settings, world
from tests.integration.test_08t_21_text_filter_mismatch import _run

__all__ = ["queue", "settings", "world"]  # fixtures used by name below

NAME = "Ayşe Demir"
ATTACHMENT = "Ayşe_Demir_izin.txt"
ATTACHMENT_BODY = (
    "İzin formu\n\nPersonel yıllık izin talebini doldurdu ve yönetici onayına gönderdi. Talep "
    "insan kaynakları sisteminde kayda alındı, izin günleri bakiyeden düşüldü ve ilgili ekip "
    "bilgilendirildi. Dönüş tarihi takvime işlendi ve vekil personel atandı.\n"
)
BODY = (
    "# Yetki talebi\n\nBu talep, personelin raporlama uygulamasına erişebilmesi için açıldı ve "
    "bir gün içinde değerlendirildi. Yetki rolü tanımlandı, erişim test ortamında doğrulandı ve "
    "sonuç talep kaydına yazıldı. Talep, kullanıcı onayından sonra kapatıldı ve ilgili ekip "
    "bilgilendirildi.\n"
)


class FakeNer:
    model, revision = "acme/turkish-ner", "0123456789abcdef"

    async def find(self, text, categories):
        out, at = [], 0
        while (start := text.find(NAME, at)) != -1:
            out.append(Finding("PERSON", start, start + len(NAME), 0.97, "ner", NAME))
            at = start + 1
        return out


def _tree(tmp_path, source: str, item: str) -> Path:
    kind, space = source.split(":")
    tree = tmp_path / "raw"
    here = tree / kind / space / item
    here.mkdir(parents=True)
    (here / f"{item}.md").write_text(BODY, encoding="utf-8")
    (here / ATTACHMENT).write_text(ATTACHMENT_BODY, encoding="utf-8")
    meta = {
        "source": source,
        "source_item_id": f"{kind}:{item}",
        "title": item,
        "attachments": [ATTACHMENT],
    }
    (here / f"{item}.md.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return tree


def _stored(pg, kb_id):
    doc = pg.execute(
        "SELECT id, silver_path FROM documents WHERE kb_id = %s", (kb_id,)
    ).fetchone()
    attachments = pg.execute(
        "SELECT filename, raw_path FROM attachments WHERE document_id = %s", (doc[0],)
    ).fetchall()
    chunks = pg.execute(
        "SELECT breadcrumb, text FROM chunks WHERE document_id = %s", (doc[0],)
    ).fetchall()
    silver = Path(doc[1]).read_text(encoding="utf-8")
    return attachments, chunks, silver


def _assert_no_name(attachments, chunks, silver):
    for value in ("Ayşe", "Demir"):
        assert value not in silver
        assert all(value not in filename for filename, _ in attachments)
        assert all(value not in crumb and value not in text for crumb, text in chunks)
    # raw_path is the real file, unchanged
    assert [Path(raw).name for _, raw in attachments] == [ATTACHMENT]


def test_08t_22_prsim_attachment_is_ek_n(world, pg, settings, tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_mask, "ner_client", lambda: FakeNer())
    kb = create_kb(world, key="prsim-attachment")
    tree = _tree(tmp_path, "jira:PRSIM", "PRSIM-2")
    report = _run(
        settings, pg, world, kb["key"], tree, sources=["jira:PRSIM"], text_filter="pii_ner"
    )
    assert report.statuses == {"indexed": 1}, report.lines()
    attachments, chunks, silver = _stored(pg, kb["id"])
    _assert_no_name(attachments, chunks, silver)
    assert [filename for filename, _ in attachments] == ["Ek 1"]
    assert "# Ek: Ek 1" in silver
    assert any(crumb.endswith("Ek: Ek 1") for crumb, _ in chunks), chunks


def test_08t_22b_other_source_attachment_name_through_the_filter(
    world, pg, settings, tmp_path, monkeypatch
):
    monkeypatch.setattr(ingest_mask, "ner_client", lambda: FakeNer())
    kb = create_kb(world, key="demo-attachment")
    tree = _tree(tmp_path, "confluence:DEMO", "2001")
    report = _run(
        settings, pg, world, kb["key"], tree, sources=["confluence:DEMO"], text_filter="pii_ner"
    )
    assert report.statuses == {"indexed": 1}, report.lines()
    attachments, chunks, silver = _stored(pg, kb["id"])
    _assert_no_name(attachments, chunks, silver)
    assert [filename for filename, _ in attachments] == ["[PERSON] izin.txt"]
    assert report.masked["PERSON"] >= 1
