"""16-1 data source API: roles, the C5 path rule, the profile rule (OFFLINE), validation codes,
credential masking in responses, audit rows and logs, connection test, items and runs.

A driver with credentials does not exist before 16-2; the masking acceptance ("kaynak kimlik
bilgileri API cevaplarında ve loglarda maskelidir") is proved with a test driver registered for
the `confluence` kind through the registry, the same road a consumer's entry point takes (C14).
"""

import json
import logging

import pytest
from pydantic import BaseModel, ConfigDict

from ffcore.sources import registry
from ffcore.sources.fs import FsDriver
from tests.integration import sources_support
from tests.integration.conftest import audit_rows
from tests.integration.sources_support import (
    create_fs_source,
    drain,
    sources_url,
    sync,
    write_tree,
)

src_world = sources_support.src_world
TOKEN = "dummy-not-secret-confluence-pat-7Hq2"


def body(w, **extra):
    data = {
        "key": "paylasim",
        "name": "Paylaşım",
        "kb_id": w["kb"],
        "kind": "fs",
        "config": {"root": "paylasim"},
    }
    data.update(extra)
    return data


def error_code(response):
    return response.json()["error"]["code"]


def test_16_1_roles(src_world):
    w = src_world
    assert w["analyst"].get(sources_url(w)).status_code == 403
    assert w["analyst"].post(sources_url(w), json=body(w)).status_code == 403
    created = w["developer"].post(sources_url(w), json=body(w))
    assert created.status_code == 201, created.text
    source = created.json()
    assert source["created_by"] and source["status"] == "active" and source["items"] == 0
    # K-16-0003: the default is a daily run out of office hours (UTC).
    assert source["schedule"] == {"kind": "daily", "minute": None, "at": "02:00", "weekday": None}
    assert source["effective_prune_max_ratio"] == 0.2
    assert w["developer"].get(sources_url(w)).json()["data"][0]["key"] == "paylasim"
    # Deleting a source is the admin's.
    assert w["developer"].delete(sources_url(w, f"/{source['id']}")).status_code == 403
    assert w["admin"].delete(sources_url(w, f"/{source['id']}")).status_code == 204
    assert w["admin"].get(sources_url(w, f"/{source['id']}")).status_code == 404


def test_16_1_read_only_access_cannot_change_or_sync(src_world, make_user, client_factory):
    w = src_world
    source = create_fs_source(w)
    _, email = make_user(memberships={w["project"]: ("admin", "read")})
    reader = client_factory(email)
    assert reader.get(sources_url(w)).status_code == 200
    for method, suffix, payload in (
        ("post", "", body(w, key="baska")),
        ("patch", f"/{source['id']}", {"name": "x"}),
        ("post", f"/{source['id']}/sync", {}),
        ("post", f"/{source['id']}/test", None),
        ("put", f"/{source['id']}/acl-mappings", {"mappings": []}),
        ("delete", f"/{source['id']}", None),
    ):
        call = getattr(reader, method)
        response = (
            call(sources_url(w, suffix), json=payload)
            if payload is not None
            else call(sources_url(w, suffix))
        )
        assert response.status_code == 403, (method, suffix, response.text)


@pytest.mark.parametrize("root", ["/", "../..", "/etc", "paylasim/../../..", "~root"])
def test_16_1_root_outside_base_is_400(src_world, root):
    w = src_world
    response = w["admin"].post(sources_url(w), json=body(w, config={"root": root}))
    assert response.status_code == 400 and error_code(response) == "path_outside_base"


def test_16_1_root_through_a_symlink_is_400(src_world, tmp_path):
    w = src_world
    outside = tmp_path / "outside"
    outside.mkdir()
    (w["base"] / "kacis").symlink_to(outside, target_is_directory=True)
    response = w["admin"].post(sources_url(w), json=body(w, config={"root": "kacis"}))
    assert response.status_code == 400 and error_code(response) == "path_outside_base"


@pytest.mark.parametrize(
    ("extra", "code"),
    [
        ({"config": {"root": "yok"}}, "fs_root_missing"),
        ({"config": {"root": "paylasim", "extra": 1}}, "config_invalid"),
        ({"deployment": "cloud"}, "deployment_invalid"),
        ({"secret": {"token": "x"}}, "secret_unexpected"),
        ({"kind": "sharepoint"}, "source_kind_unavailable"),
        ({"config": {"root": "prsim"}}, "prsim_requires_ner"),
    ],
)
def test_16_1_validation_codes(src_world, extra, code):
    w = src_world
    (w["base"] / "prsim").mkdir()
    response = w["admin"].post(sources_url(w), json=body(w, **extra))
    assert response.status_code == 422, response.text
    assert error_code(response) == code


def test_16_1_schedule_and_key_rules(src_world):
    w = src_world
    bad = w["admin"].post(sources_url(w), json=body(w, schedule={"kind": "daily"}))
    assert bad.status_code == 422
    cron = w["admin"].post(sources_url(w), json=body(w, schedule={"kind": "cron", "at": "0 2"}))
    assert cron.status_code == 422
    ok = w["admin"].post(sources_url(w), json=body(w, schedule={"kind": "daily", "at": "02:30"}))
    assert ok.status_code == 201 and ok.json()["schedule"]["at"] == "02:30"
    taken = w["admin"].post(sources_url(w), json=body(w))
    assert taken.status_code == 409 and error_code(taken) == "data_source_key_taken"
    other_kb = w["admin"].post(
        sources_url(w), json=body(w, key="baska", kb_id="00000000-0000-0000-0000-000000000000")
    )
    assert other_kb.status_code == 404


def test_16_1_patch_pause_and_sync_refused_while_paused(src_world):
    w = src_world
    source = create_fs_source(w)
    patched = w["admin"].patch(
        sources_url(w, f"/{source['id']}"),
        json={
            "status": "paused",
            "prune_max_ratio": 0.5,
            "schedule": {"kind": "hourly", "minute": 5},
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["effective_prune_max_ratio"] == 0.5
    refused = w["admin"].post(sources_url(w, f"/{source['id']}/sync"), json={})
    assert refused.status_code == 409 and error_code(refused) == "data_source_paused"
    fixed = w["admin"].patch(sources_url(w, f"/{source['id']}"), json={"kind": "jira"})
    assert fixed.status_code == 422  # kind, deployment and knowledge base are fixed
    cleared = w["admin"].patch(
        sources_url(w, f"/{source['id']}"), json={"clear_prune_max_ratio": True, "status": "active"}
    )
    assert cleared.json()["prune_max_ratio"] is None


def test_16_1_test_connection_items_and_runs(src_world):
    w = src_world
    write_tree(w["root"], {"a.md": "# A\n\nmetin", "alt/b.md": "# B\n\nmetin"})
    source = create_fs_source(w)
    tested = w["developer"].post(sources_url(w, f"/{source['id']}/test")).json()
    assert tested == {"reachable": True, "count": 2, "error_code": None, "detail": None}
    run = sync(w, source["id"], client="developer")
    assert run["status"] == "queued" and run["trigger"] == "manual" and run["layer"] == "raw"
    drain(w)
    items = w["developer"].get(sources_url(w, f"/{source['id']}/items")).json()
    assert items["total"] == 2
    assert {i["external_id"] for i in items["data"]} == {"a.md", "alt/b.md"}
    assert all(i["document_id"] and i["state"] == "active" for i in items["data"])
    listed = w["developer"].get(sources_url(w, f"/{source['id']}/runs")).json()["data"]
    assert [r["layer"] for r in listed] == ["silver", "raw"]
    detail = w["developer"].get(sources_url(w, f"/{source['id']}/runs/{listed[1]['id']}")).json()
    assert detail["count_before"] == 2 and detail["count_after"] == 2
    # Deleting a source that still feeds documents is refused (no silent removal).
    deleted = w["admin"].delete(sources_url(w, f"/{source['id']}"))
    assert deleted.status_code == 409 and error_code(deleted) == "data_source_has_items"


class _Secret(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str


class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: str
    base_url: str


class SecretDriver(FsDriver):
    """A network-folder driver that also takes a credential: the credential path of 16-2's
    drivers (encrypt, mask, keep on ***, never log) without any network."""

    kind = "confluence"
    deployments = ("server", "cloud")
    internet_deployments = ("cloud",)
    config_model = _Config
    secret_model = _Secret
    seen_secrets: list = []

    def __init__(self, spec, secret, http, settings):
        SecretDriver.seen_secrets.append(secret)
        super().__init__(
            type(spec)(spec.id, "fs", None, {"root": spec.config["root"]}), None, http, settings
        )


@pytest.fixture
def secret_driver(monkeypatch):
    drivers = registry.build(registry.BUILTIN, [("test-confluence", SecretDriver)])
    monkeypatch.setattr(registry, "drivers", lambda: drivers)
    SecretDriver.seen_secrets.clear()
    return SecretDriver


def test_16_1_credentials_are_masked_everywhere(src_world, secret_driver, pg, caplog):
    w = src_world
    caplog.set_level(logging.DEBUG)
    created = w["admin"].post(
        sources_url(w),
        json=body(
            w,
            kind="confluence",
            deployment="server",
            config={"root": "paylasim", "base_url": "https://wiki.example.test"},
            secret={"token": TOKEN},
        ),
    )
    assert created.status_code == 201, created.text
    source = created.json()
    assert source["secret"] == {"token": "***"}
    assert TOKEN not in json.dumps(source)
    (stored,) = pg.execute(
        "SELECT secret_encrypted FROM data_sources WHERE id = %s", (source["id"],)
    ).fetchone()
    assert TOKEN.encode() not in bytes(stored)  # Fernet, not plain
    # *** sent back keeps the stored value; the driver receives the real one.
    patched = w["admin"].patch(
        sources_url(w, f"/{source['id']}"), json={"secret": {"token": "***"}, "name": "Wiki"}
    )
    assert patched.status_code == 200 and patched.json()["secret"] == {"token": "***"}
    w["admin"].post(sources_url(w, f"/{source['id']}/test"))
    assert secret_driver.seen_secrets[-1] == {"token": TOKEN}
    for listing in (
        w["admin"].get(sources_url(w)).text,
        w["admin"].get(sources_url(w, f"/{source['id']}")).text,
    ):
        assert TOKEN not in listing
    rows = audit_rows(pg, "create_data_source", "success", project=w["project"]) + audit_rows(
        pg, "update_data_source", "success", project=w["project"]
    )
    assert rows and all(TOKEN not in json.dumps(row, default=str) for row in rows)
    assert TOKEN not in caplog.text
    # The profile rule: the cloud deployment of an internet driver is refused offline (airgap).
    offline = w["settings"].model_copy(update={"offline": True})
    from ffcore.core.config import get_settings

    w["admin"].app.dependency_overrides[get_settings] = lambda: offline
    refused = w["admin"].post(
        sources_url(w),
        json=body(
            w,
            key="bulut",
            kind="confluence",
            deployment="cloud",
            config={"root": "paylasim", "base_url": "https://x.atlassian.net"},
            secret={"token": TOKEN},
        ),
    )
    assert refused.status_code == 422 and error_code(refused) == "source_kind_unavailable"
    assert TOKEN not in refused.text


def test_16_1_read_mode_get_parity(src_world, make_user, client_factory):
    """Read access sees exactly what edit access sees (03a rule) on every data source GET,
    masked credentials included; test_03a_2 exempts these single-source routes."""
    w = src_world
    write_tree(w["root"], {"a.md": "# A\n\nmetin"})
    source = create_fs_source(w)
    run = sync(w, source["id"])
    drain(w)
    _, email = make_user(memberships={w["project"]: ("admin", "read")})
    read = client_factory(email)
    base = sources_url(w, f"/{source['id']}")
    for url in (
        sources_url(w),
        base,
        base + "/runs",
        base + f"/runs/{run['id']}",
        base + "/items",
        base + "/acl-mappings",
    ):
        edit_answer, read_answer = w["admin"].get(url), read.get(url)
        assert edit_answer.status_code == 200, (url, edit_answer.text)
        assert (read_answer.status_code, read_answer.content) == (200, edit_answer.content), url
