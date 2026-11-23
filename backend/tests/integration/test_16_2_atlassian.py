"""16-2 acceptance: Confluence and Jira through the sync engine, against a fake Atlassian.

The fake (`tests/fakes/fake_atlassian.py`) runs in the test process on 127.0.0.1, an internal
host for these tests only (`allowed_internal_hosts`, as 06b-2's fake agent): no real Atlassian
address is contacted. Every request the drivers send is recorded, so a test proves what a run
asked for: a delta only the changed page, a silver or gold run nothing at all.
"""

import json
import threading
import urllib.request
from datetime import UTC, datetime, timedelta

import pytest

from ffcore.core.config import get_settings
from tests.fakes import fake_atlassian
from tests.integration import sources_support
from tests.integration.sources_support import documents, drain, found, runs, search, sources_url, sync

src_world = sources_support.src_world
PAT = "dummy-not-secret-pat-16-2-int"
OLD = (datetime.now(UTC) - timedelta(days=5)).isoformat()
PROSE = (
    "Ödeme geçidi zaman aşımı yaşandığında işlem kuyruğu yeniden denenir ve her denemenin "
    "sonucu kayıt altına alınır; operasyon ekibi gün sonunda kalan işlemleri tek tek inceler. "
)


@pytest.fixture
def atl(src_world):
    server = fake_atlassian.serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    w = src_world
    settings = w["settings"].model_copy(
        update={"allowed_internal_hosts": [*w["settings"].allowed_internal_hosts, "127.0.0.1"]}
    )
    w["settings"] = settings
    w["admin"].app.dependency_overrides[get_settings] = lambda: settings
    w["fake"] = f"http://127.0.0.1:{server.server_address[1]}"
    yield w
    server.shutdown()
    server.server_close()


def control(w, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(w["fake"] + path, data=data, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def asked(w):
    return [r["path"] for r in control(w, "/_requests")["requests"]]


def page(n, *, marker=None, when=OLD, **extra):
    text = f"<h2>Bölüm {n}</h2><p>{PROSE * 4}{marker or f'sayfaimi{n}'}</p>"
    return {"id": str(100 + n), "space": "OPS", "title": f"Sayfa {n}", "body": text, "when": when, **extra}


def state(pages, **extra):
    return {"auth": [f"Bearer {PAT}"], "confluence": {"spaces": {"OPS": {}}, "pages": pages}, **extra}


def create_source(w, kind="confluence", key="wiki", config=None, client="admin", **extra):
    body = {
        "key": key,
        "name": key,
        "kb_id": w["kb"],
        "kind": kind,
        "deployment": "server",
        "config": {"base_url": w["fake"], **(config or {})},
        "secret": {"token": PAT},
        "schedule": {"kind": "manual"},
    }
    body.update(extra)
    response = w[client].post(sources_url(w), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def open_to_analysts(w, source_id, group="*"):
    response = w["admin"].put(
        sources_url(w, f"/{source_id}/acl-mappings"),
        json={"mappings": [{"external_group": group, "role": "analyst"}]},
    )
    assert response.status_code == 200, response.text


def full(w, source_id, **extra):
    sync(w, source_id, mode="full", **extra)
    return drain(w)


def test_16_2_project_admin_registers_and_credentials_stay_masked(atl, pg):
    w = atl
    control(w, "/_state", state([page(1)]))
    source = create_source(w)  # Atlassian sources are the project admin's (16-1 r2 policy)
    assert source["secret"] == {"token": "***"} and PAT not in json.dumps(source)
    tested = w["admin"].post(sources_url(w, f"/{source['id']}/test"))
    assert tested.status_code == 200 and tested.json()["reachable"] is True
    assert tested.json()["count"] == 1
    # The credential must fit the deployment; a cloud source with a PAT is refused.
    refused = w["admin"].post(
        sources_url(w),
        json={
            "key": "bulut", "name": "b", "kb_id": w["kb"], "kind": "jira", "deployment": "cloud",
            "config": {"base_url": "https://ornek.atlassian.net"}, "secret": {"token": PAT},
        },
    )
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "secret_invalid"
    assert PAT not in refused.text
    # Wrong credentials: the connection test says so with a code, nothing else.
    control(w, "/_state", state([page(1)], auth=["Bearer another"]))
    failed = w["admin"].post(sources_url(w, f"/{source['id']}/test")).json()
    assert failed["reachable"] is False and failed["error_code"] == "source_auth_failed"


def test_16_2_confluence_full_then_delta_asks_only_for_the_changed_page(atl, pg):
    w = atl
    control(w, "/_state", state([page(n) for n in range(5)]))
    source = create_source(w, config={"space_keys": ["OPS"]})
    open_to_analysts(w, source["id"])
    raw, silver = full(w, source["id"])
    assert raw["status"] == "completed" and raw["added"] == 5 and silver["status"] == "completed"
    assert len(documents(pg, w["kb"])) == 5 and found(w, "analyst", "sayfaimi3")
    hit = next(h for h in search(w, "analyst", "sayfaimi3") if "sayfaimi3" in h["text"])
    assert hit["breadcrumb"].startswith("OPS › Sayfa 3")
    assert hit["source_url"] == f"{w['fake']}/spaces/OPS/pages/103"  # S4: the card's link
    # One page changes; the delta asks for that page's attachments and permissions only.
    pages = [page(n) for n in range(5)]
    pages[2] = page(2, marker="guncellenmis", when=datetime.now(UTC).isoformat())
    control(w, "/_state", state(pages))
    sync(w, source["id"], mode="delta")
    raw, silver = drain(w)
    assert raw["updated"] == 1 and raw["unchanged"] == 0 and raw["deleted"] == 0
    paths = asked(w)
    assert {p for p in paths if "/content/1" in p} == {
        "/rest/api/content/102/child/attachment",
        "/rest/api/content/102/restriction/byOperation/read",
    }
    assert found(w, "analyst", "guncellenmis") and not found(w, "analyst", "sayfaimi2")
    assert len(documents(pg, w["kb"])) == 5


def test_16_2_confluence_full_prunes_three_deleted_pages(atl, pg):
    w = atl
    control(w, "/_state", state([page(n) for n in range(30)]))
    source = create_source(w)
    open_to_analysts(w, source["id"])
    full(w, source["id"])
    control(w, "/_state", state([page(n) for n in range(30) if n not in (4, 9, 14)]))
    raw, _ = full(w, source["id"])
    assert raw["prune_decision"] == "done" and raw["deleted"] == 3
    assert len(documents(pg, w["kb"])) == 27
    assert not found(w, "analyst", "sayfaimi9") and found(w, "analyst", "sayfaimi10")


def test_16_2_lost_space_and_cut_listing_delete_nothing(atl, pg):
    w = atl
    two_spaces = [page(n) for n in range(10)] + [
        {**page(n), "id": str(500 + n), "space": "IK"} for n in range(20)
    ]
    data = state(two_spaces)
    data["confluence"]["spaces"]["IK"] = {}
    control(w, "/_state", data)
    source = create_source(w)
    full(w, source["id"])
    assert len(documents(pg, w["kb"])) == 30
    # The service account loses the IK space: 20 of 30 would go, over the ratio → refused.
    data["confluence"]["spaces"]["IK"] = {"permitted": False}
    control(w, "/_state", data)
    raw, *_ = full(w, source["id"])
    assert raw["prune_decision"] == "prune_refused" and raw["deleted"] == 0
    assert len(documents(pg, w["kb"])) == 30
    # The connection drops in the middle of the listing: nothing is deleted.
    data["confluence"]["spaces"]["IK"] = {}
    control(w, "/_state", data)
    control(w, "/_fault", {"cut_listing_after": 1})
    raw, *_ = full(w, source["id"])
    assert raw["status"] == "failed" and raw["prune_decision"] == "listing_failed"
    assert raw["deleted"] == 0 and len(documents(pg, w["kb"])) == 30


def test_16_2_silver_and_gold_never_ask_atlassian(atl, pg):
    w = atl
    control(w, "/_state", state([page(n) for n in range(3)]))
    source = create_source(w)
    full(w, source["id"])
    control(w, "/_reset", {})
    for layer in ("silver", "gold"):
        sync(w, source["id"], layer=layer, mode="full")
        results = drain(w)
        assert results and all(r["status"] == "completed" for r in results), results
    assert asked(w) == []
    gold = next(r for r in runs(w, source["id"]) if r["layer"] == "gold")
    assert gold["reused"] == 3


def test_16_2_restricted_page_is_not_opened_by_the_space_mapping(atl, pg):
    w = atl
    secret = page(1, marker="yonetimsirri", restrictions={"groups": ["Yonetim"]})
    control(w, "/_state", state([page(0), secret]))
    source = create_source(w)
    open_to_analysts(w, source["id"], group="space:OPS")
    full(w, source["id"])
    assert found(w, "analyst", "sayfaimi0")
    assert not found(w, "analyst", "yonetimsirri") and found(w, "admin", "yonetimsirri")
    # Mapping the restriction's group opens it, to that role.
    response = w["admin"].put(
        sources_url(w, f"/{source['id']}/acl-mappings"),
        json={"mappings": [
            {"external_group": "space:OPS", "role": "analyst"},
            {"external_group": "group:Yonetim", "role": "analyst"},
        ]},
    )
    assert response.status_code == 200, response.text
    sync(w, source["id"], mode="delta")
    drain(w)
    assert found(w, "analyst", "yonetimsirri")


def test_16_2_shared_attachment_is_downloaded_once_and_big_files_never(atl, pg):
    w = atl
    shared = {"title": "kilavuz.txt", "content": PROSE * 20}
    huge = {"title": "arsiv.zip", "content": "x", "size": 600 * 1024 * 1024}
    pages = [page(0, attachments=[shared, huge]), page(1, attachments=[shared])]
    control(w, "/_state", state(pages))
    source = create_source(w)
    open_to_analysts(w, source["id"])
    raw, _ = full(w, source["id"])
    assert raw["status"] == "completed"
    downloads = [p for p in asked(w) if p.startswith("/download/")]
    assert downloads == ["/download/attachments/100/kilavuz.txt"]
    rows = pg.execute(
        "SELECT a.name, a.gate0_status, a.gate0_reason, a.shared_from IS NOT NULL"
        " FROM source_attachments a JOIN source_items i ON i.id = a.source_item_id"
        " WHERE i.data_source_id = %s ORDER BY i.external_id, a.name",
        (source["id"],),
    ).fetchall()
    assert rows == [
        ("arsiv.zip", "skipped", "too_large", False),
        ("kilavuz.txt", "ok", None, False),
        ("kilavuz.txt", "ok", "shared_from", True),
    ]


def issue(n, **fields):
    base = {
        "summary": f"Konu {n}", "updated": OLD, "created": OLD, "project": {"key": "OPS"},
        "status": {"name": "Done"}, "issuetype": {"name": "Bug"},
        "assignee": {"displayName": "Ayşe Kaya"}, "reporter": {"displayName": "Mehmet Demir"},
        "description": f"{PROSE * 3} sorunkodu{n}",
        "comment": {"comments": [
            {"author": {"displayName": "Ayşe Kaya"}, "body": PROSE * 2, "created": OLD},
        ]},
    }
    return {"key": f"OPS-{n}", "fields": {**base, **fields}}


def test_16_2_jira_issues_become_documents_without_person_names(atl, pg):
    w = atl
    fix = issue(
        7,
        description=f"h2. Kök neden\n{PROSE * 3}\n{{code:java}}\nthrow new TimeoutException();\n{{code}}",
        resolution={"name": "Fixed", "description": f"{PROSE} Zaman aşımı otuz saniyeye çıkarıldı."},
    )
    secret = issue(8, security={"name": "Yonetim"}, description=f"{PROSE * 3} gizlisorun")
    control(w, "/_state", {
        "auth": [f"Bearer {PAT}"],
        "jira": {"projects": {"OPS": {}}, "issues": [issue(n) for n in range(5)] + [fix, secret]},
    })
    source = create_source(w, kind="jira", key="jira", config={"jql": "project = OPS"})
    open_to_analysts(w, source["id"], group="project:OPS")
    raw, _ = full(w, source["id"])
    assert raw["added"] == 7 and raw["count_before"] == 7 == raw["count_after"]
    hits = search(w, "analyst", "TimeoutException zaman aşımı nasıl çözüldü")
    hit = next(h for h in hits if h["document_name"].startswith("jira"))
    assert "OPS-7" in hit["breadcrumb"] and hit["source_url"] == f"{w['fake']}/browse/OPS-7"
    texts = pg.execute(
        "SELECT c.text FROM chunks c JOIN documents d ON d.id = c.document_id WHERE d.kb_id = %s",
        (w["kb"],),
    ).fetchall()
    assert texts and not any("Ayşe" in t or "Mehmet" in t for (t,) in texts)  # K-16-0009 S1
    # The security level narrows the project mapping: the analyst does not see that issue.
    assert not found(w, "analyst", "gizlisorun") and found(w, "admin", "gizlisorun")
