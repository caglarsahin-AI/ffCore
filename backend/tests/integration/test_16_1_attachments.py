"""16-1 Kapı 0 for attachments in the engine (PayCore D1, D2): decided from the listing before
any download, recorded in `source_attachments`; a downloaded attachment goes through 04's
pipeline with its page (a 10,000-line log is `data_dump:log`, the page is still indexed); the
same name and size on a second item is downloaded once (`shared_from`); when the owner item is
deleted its file moves to the borrower instead of being removed.

The source is an in-process test driver registered for the `jira` kind (C14 road); the real
Confluence/Jira drivers and their fake servers are 16-2.
"""

import json
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from ffcore.core.config import get_settings
from ffcore.sources import registry
from ffcore.sources.base import (
    AttachmentRef,
    ConnectionTest,
    ItemRef,
    RawPayload,
    Rendered,
    SourceAcl,
)
from tests.integration import sources_support
from tests.integration.sources_support import document_text, documents, drain, sources_url, sync

src_world = sources_support.src_world
MB = 1024 * 1024
LOG = "\n".join(
    f"2026-03-0{1 + n % 9} 10:{n % 60:02d}:00 ERROR payment-service timeout id={n}"
    for n in range(10_000)
)
SHARED = document_text("Ortak ek", "ortakek5")
GUIDE = document_text("Rehber", "rehberek5")


class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = "OPS"


class FakeIssues:
    """Issues and attachments held in memory; counts every download."""

    kind = "jira"
    tombstones = False
    internet_deployments = ()
    deployments = ("server", "cloud")
    config_model = _Config
    secret_model = None
    pages: dict[str, dict] = {}
    downloads: list[str] = []

    def __init__(self, spec, secret, http, settings):
        pass

    async def test_connection(self):
        return ConnectionTest(reachable=True, count=len(self.pages))

    async def count(self):
        return len(self.pages)

    async def list_changes(self, since):
        for key in sorted(self.pages):
            yield ItemRef(external_id=key, title=self.pages[key]["title"], space="OPS")

    async def fetch_raw(self, item):
        page = self.pages[item.external_id]
        payload = {"key": item.external_id, "title": page["title"], "body": page["body"]}
        return RawPayload(content=json.dumps(payload, sort_keys=True).encode(), ext="json")

    async def list_attachments(self, item, raw):
        for name, (_content, size, when) in sorted(self.pages[item.external_id]["files"].items()):
            yield AttachmentRef(
                name=name, size=size, modified_at=when, ref=f"{item.external_id}/{name}"
            )

    @asynccontextmanager
    async def fetch_attachment(self, item, attachment):
        FakeIssues.downloads.append(attachment.ref)
        content = self.pages[item.external_id]["files"][attachment.name][0]

        async def chunks():
            yield content

        yield chunks()

    async def acl(self, item, raw):
        return SourceAcl(groups=("jira-users",))

    def render(self, item, raw):
        payload = json.loads(raw.content)
        return Rendered(
            content=f"# {payload['title']}\n\n{payload['body']}".encode(),
            filename=f"{payload['key']}.md",
            breadcrumb=("OPS", payload["key"]),
        )

    async def aclose(self):
        return None


def files(**entries):
    return {
        name: (content, len(content) if size is None else size, when)
        for name, (content, size, when) in entries.items()
    }


RECENT = datetime(2025, 6, 1, tzinfo=UTC)


@pytest.fixture
def issues(monkeypatch):
    drivers = registry.build(registry.BUILTIN, [("test-jira", FakeIssues)])
    monkeypatch.setattr(registry, "drivers", lambda: drivers)
    FakeIssues.downloads = []
    FakeIssues.pages = {
        "OPS-1": {
            "title": "Ödeme zaman aşımı",
            "body": document_text("Ödeme zaman aşımı", "ops1govde"),
            "files": files(
                **{
                    "ekran.png": (b"\x89PNG", None, RECENT),
                    "buyuk.pdf": (b"%PDF", 600 * MB, RECENT),
                    "uygulama.log": (LOG.encode(), None, RECENT),
                    "rehber.md": (GUIDE.encode(), None, RECENT),
                    "ortak.md": (SHARED.encode(), None, RECENT),
                }
            ),
        },
        "OPS-2": {
            "title": "Mutabakat farkı",
            "body": document_text("Mutabakat farkı", "ops2govde"),
            "files": files(
                **{
                    "ortak.md": (SHARED.encode(), None, RECENT),
                    "eski.md": (GUIDE.encode(), None, datetime(2019, 3, 1, tzinfo=UTC)),
                }
            ),
        },
    }
    return FakeIssues


def ledger(pg, source_id):
    rows = pg.execute(
        "SELECT i.external_id, a.name, a.gate0_status, a.gate0_reason, a.raw_path,"
        " a.shared_from IS NOT NULL FROM source_attachments a"
        " JOIN source_items i ON i.id = a.source_item_id WHERE i.data_source_id = %s",
        (source_id,),
    ).fetchall()
    return {(r[0], r[1]): r[2:] for r in rows}


def test_16_1_attachments_gate0_shared_and_data_dump(src_world, issues, pg):
    w = src_world
    w["settings"] = w["settings"].model_copy(update={"attachment_min_date": date(2021, 1, 1)})
    w["admin"].app.dependency_overrides[get_settings] = lambda: w["settings"]
    source = (
        w["admin"]
        .post(
            sources_url(w),
            json={
                "key": "ops",
                "name": "OPS",
                "kb_id": w["kb"],
                "kind": "jira",
                "deployment": "server",
                "config": {"project": "OPS"},
            },
        )
        .json()
    )
    sync(w, source["id"])
    raw, silver = drain(w)
    assert raw["added"] == 2 and silver["added"] == 2, (raw, silver)

    book = ledger(pg, source["id"])
    assert book[("OPS-1", "ekran.png")][:2] == ("skipped", "out_of_scope")
    assert book[("OPS-1", "buyuk.pdf")][:2] == ("skipped", "too_large")
    assert book[("OPS-2", "eski.md")][:2] == ("skipped", "stale")
    assert book[("OPS-1", "ortak.md")][:2] == ("ok", None)
    assert (
        book[("OPS-2", "ortak.md")][:2] == ("ok", "shared_from") and book[("OPS-2", "ortak.md")][3]
    )
    assert book[("OPS-2", "ortak.md")][2] == book[("OPS-1", "ortak.md")][2]  # one file
    # Nothing Kapı 0 refused was downloaded; the shared one was downloaded once.
    assert sorted(issues.downloads) == ["OPS-1/ortak.md", "OPS-1/rehber.md", "OPS-1/uygulama.log"]

    (ops1,) = [d for d in documents(pg, w["kb"]) if d[1] == "ops/OPS-1.md"]
    assert ops1[3] == "indexed"  # the page is indexed, its log attachment is not
    attachments = dict(
        pg.execute(
            "SELECT filename, gate2_status || ':' || coalesce(gate2_reason, '')"
            " FROM attachments WHERE document_id = %s",
            (ops1[0],),
        ).fetchall()
    )
    assert attachments["uygulama.log"] == "skipped:data_dump:log"
    assert attachments["rehber.md"].startswith(("ok:", "flagged:"))
    assert sources_support.found(w, "admin", "rehberek5")

    # The owner of the shared file goes (ratio 1/1: this source allows it); the borrower keeps it.
    w["admin"].patch(sources_url(w, f"/{source['id']}"), json={"prune_max_ratio": 1.0})
    del issues.pages["OPS-1"]
    sync(w, source["id"], mode="full")
    raw, silver = drain(w)
    assert raw["prune_decision"] == "done" and raw["deleted"] == 1
    assert silver["listed"] == 1  # the heir waits for silver again
    book = ledger(pg, source["id"])
    status, reason, path, shared = book[("OPS-2", "ortak.md")]
    assert (status, reason, shared) == ("ok", None, False)
    assert Path(path).is_file() and "OPS-2" in path
    assert sources_support.found(w, "admin", "ortakek5")
    (ops2,) = [d for d in documents(pg, w["kb"]) if d[1] == "ops/OPS-2.md"]
    names = {
        r[0]
        for r in pg.execute(
            "SELECT filename FROM attachments WHERE document_id = %s", (ops2[0],)
        ).fetchall()
    }
    assert "ortak.md" in names


def test_16_1_attachment_without_size_is_bounded_while_streaming(
    src_world, issues, pg, monkeypatch
):
    w = src_world
    monkeypatch.setattr("ffcore.sources.gate0.max_bytes", lambda name: 1024)
    issues.pages = {
        "OPS-9": {
            "title": "Büyük ek",
            "body": document_text("Büyük ek", "ops9"),
            "files": {"dokum.md": (b"x" * 4096, None, RECENT)},  # the listing gives no size
        }
    }
    source = (
        w["admin"]
        .post(
            sources_url(w),
            json={
                "key": "ops",
                "name": "OPS",
                "kb_id": w["kb"],
                "kind": "jira",
                "deployment": "server",
            },
        )
        .json()
    )
    sync(w, source["id"])
    drain(w)
    status, reason, path, _ = ledger(pg, source["id"])[("OPS-9", "dokum.md")]
    assert (status, reason, path) == ("skipped", "too_large", None)
    item_dirs = list(Path(w["settings"].knowledge_storage_dir).rglob("dokum.md*"))
    assert item_dirs == []  # the partial download was removed
