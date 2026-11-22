"""16-1 r2 (KARARLAR '16-1 r1 kararları'; review state/reviews/16-1-r1.md).

MAJOR-1 `fs-kok-proje-siniri-yok` (A): a network folder is installation-wide, so registering a
network-folder source and changing its root or filters is the superadmin's; project roles sync,
map, watch and read (S3: project B's developer or admin cannot index project A's share).
MINOR-1 `kb-silinince-kaynak-surer`: a knowledge base with a live source cannot be deleted (409
`knowledge_base_has_sources`); a raw run whose knowledge base is gone fails `kb_deleted` and
writes nothing (S8).
"""

from pathlib import Path

from tests.integration import sources_support
from tests.integration.conftest import audit_rows
from tests.integration.sources_support import (
    API,
    create_fs_source,
    document_text,
    documents,
    drain,
    found,
    sources_url,
    sync,
    write_tree,
)

src_world = sources_support.src_world


def fs_body(w, key="paylasim", root="paylasim", **extra):
    return {
        "key": key,
        "name": key,
        "kb_id": w["kb"],
        "kind": "fs",
        "config": {"root": root},
        **extra,
    }


def code(response):
    return response.json()["error"]["code"]


def test_16_1_r2_fs_registration_and_root_are_superadmin_only(src_world, pg):
    w = src_world
    write_tree(w["root"], {"a.md": document_text("A", "aaa1")})
    for client in ("developer", "admin"):
        refused = w[client].post(sources_url(w), json=fs_body(w))
        assert refused.status_code == 403, (client, refused.text)
        assert code(refused) == "fs_source_superadmin_only"
    created = w["super"].post(sources_url(w), json=fs_body(w))
    assert created.status_code == 201, created.text
    source = created.json()
    url = sources_url(w, f"/{source['id']}")
    for client in ("developer", "admin"):
        moved = w[client].patch(url, json={"config": {"root": "."}})
        assert moved.status_code == 403 and code(moved) == "fs_source_superadmin_only"
    assert (
        w["super"]
        .patch(url, json={"config": {"root": "paylasim", "include_globs": ["*.md"]}})
        .status_code
        == 200
    )
    # Project roles keep the rest: schedule and name, sync, mappings, reading.
    assert (
        w["developer"]
        .patch(url, json={"name": "Paylaşım", "schedule": {"kind": "manual"}})
        .status_code
        == 200
    )
    run = sync(w, source["id"], client="developer")
    assert run["status"] == "queued"
    drain(w)
    assert (
        w["admin"]
        .put(url + "/acl-mappings", json={"mappings": [{"external_group": "*", "role": "analyst"}]})
        .status_code
        == 200
    )
    assert w["developer"].get(url + "/items").status_code == 200
    denied = audit_rows(pg, "create_data_source", "denied") + audit_rows(
        pg, "update_data_source", "denied"
    )
    assert len(denied) >= 4  # every refusal is recorded (outcome denied)


def test_16_1_r2_project_b_cannot_index_project_a_share(
    src_world, make_user, make_project, client_factory
):
    """S3: the share holds project A's files; project B's developer and admin cannot register
    any root over it (".", the parent, the folder itself); only the superadmin decides which
    folder a project sees."""
    w = src_world
    write_tree(w["root"], {"ik/maas.md": document_text("Maaş tablosu", "maasgizli7")})
    a_source = create_fs_source(w, root="paylasim/ik")
    sync(w, a_source["id"])
    drain(w)
    other = make_project()
    _, b_dev = make_user(memberships={other: ("developer", "edit")})
    _, b_admin = make_user(memberships={other: ("admin", "edit")})
    b_developer, b_administrator = client_factory(b_dev), client_factory(b_admin)
    kb = b_administrator.post(
        f"{API}/projects/{other}/knowledge-bases", json={"key": "b-kb", "name": "B"}
    )
    assert kb.status_code == 201, kb.text
    for client in (b_developer, b_administrator):
        for root in (".", "paylasim", "paylasim/ik"):
            response = client.post(
                f"{API}/projects/{other}/data-sources",
                json={
                    "key": f"k{abs(hash(root)) % 1000}",
                    "name": "x",
                    "kb_id": kb.json()["id"],
                    "kind": "fs",
                    "config": {"root": root},
                },
            )
            assert response.status_code == 403, (root, response.text)
            assert code(response) == "fs_source_superadmin_only"
    assert b_developer.get(f"{API}/projects/{other}/data-sources").json()["data"] == []
    hits = b_administrator.post(
        f"{API}/projects/{other}/knowledge-bases/{kb.json()['id']}/search",
        json={"query": "maasgizli7"},
    ).json()["hits"]
    assert not any("maasgizli7" in h["text"] for h in hits)
    assert found(w, "admin", "maasgizli7")  # project A (admin-only default) still has it


def test_16_1_r2_knowledge_base_with_a_live_source(src_world, pg):
    """S8: deleting the knowledge base under a live source is refused; once the source is
    paused the knowledge base may go, and a later raw run fails `kb_deleted` without writing."""
    w = src_world
    write_tree(w["root"], {"a.md": document_text("A", "kbsil1")})
    source = create_fs_source(w)
    sync(w, source["id"])
    drain(w)
    kb_url = f"{API}/projects/{w['project']}/knowledge-bases/{w['kb']}"
    refused = w["admin"].delete(kb_url)
    assert refused.status_code == 409 and code(refused) == "knowledge_base_has_sources"
    assert w["admin"].get(kb_url).status_code == 200
    url = sources_url(w, f"/{source['id']}")
    assert w["admin"].patch(url, json={"status": "paused"}).status_code == 200
    assert w["admin"].delete(kb_url).status_code == 204
    # Someone activates the source again: its run must not feed the deleted knowledge base.
    assert w["admin"].patch(url, json={"status": "active"}).status_code == 200
    write_tree(w["root"], {"b.md": document_text("B", "kbsil2")})
    sync(w, source["id"], mode="full")
    (raw,) = drain(w)
    assert raw["status"] == "failed" and raw["error"] == "kb_deleted"
    run = w["admin"].get(url + "/runs").json()["data"][0]
    assert (run["status"], run["error"], run["added"]) == ("failed", "kb_deleted", 0)
    assert [d for d in documents(pg, w["kb"]) if d[1].endswith("b.md")] == []
    storage = Path(w["settings"].knowledge_storage_dir)
    assert [p for p in storage.rglob("*") if "b.md" in p.name] == []  # no raw, no silver
